---
date: 2026-11-03
problem_type: integration_issue
component: database_migration
severity: high
symptoms:
  - "Ticket prices and sold-out states scraped from DICE, Songkick, and Ticketmaster were dropped before reaching GitHub Pages."
  - "SQLite seen_events schema lacked price_str and is_sold_out columns, causing prices to be lost across pipeline runs."
  - "Club Nights & DJs (Tier 4) lacked musical taste intelligence, hiding artist tribute nights and preferred dance genres."
  - "Naive substring matching against event descriptions triggered false positive artist matches on short token names like 'Air' and 'Keo'."
  - "Application version was hardcoded as v0.0.1 across code, models, and UI templates despite major architectural upgrades."
root_cause: wrong_assumption
tags:
  - ticket-pricing
  - sold-out-ingestion
  - sqlite-migration
  - club-night-taste
  - regex-word-boundaries
  - version-bumping
related_issues: []
related_solutions:
  - "docs/solutions/integration_issue/live-curator-engine-architecture.md"
last_referenced: "2026-11-03"
---

# Ticket Pricing, Sold-Out Persistence & Club Night Taste Tagging

## Problem Statement

**What happened:**
While Live Curator scraped 680+ events across 51 London venues and stadiums, users were unable to view ticket prices (e.g., £15.00 vs £95.00) or identify if popular shows were sold out. Furthermore, late-night events in Tier 4 (*Club Nights & DJs*) only displayed generic heuristic labels (`Late Night Party (≥22:00)`), even when the event description explicitly featured artists from Elliott and Chloe's libraries or played their favorite genres (*post-punk, nu-disco, techno, house, shoegaze*).

**Impact:**
1. High-demand gigs (such as Keo at O2 Academy Brixton or Fontaines D.C. at Finsbury Park) appeared as standard available shows without warning that tickets were sold out.
2. Users had to open every external ticket link to check pricing.
3. Relevant club nights featuring their favorite artists went unnoticed in Tier 4.

---

## Symptoms

1. **Missing Ticket Metadata in Web UI:**
   Event cards rendered date, venue, and area, but ticket price pills were absent and sold-out events still showed green "Get Tickets" buttons.
2. **Data Pipeline Dropping Fields:**
   `scripts/build_pages.py` queried `SELECT event_id, title, venue_name, venue_area, start_time, ticket_url, platform FROM seen_events`, discarding `price_str` and omitting `is_sold_out`.
3. **Club Night Blindspot:**
   Club nights mentioning artists like Fontaines D.C. or genres like post-punk received no taste badges.

---

## Investigation Steps

### What Was Tried

| Attempt | Hypothesis | Result |
|---|---|---|
| 1. Query `price_str` from SQLite directly | Expected price to be already stored | ❌ `sqlite3.OperationalError: no such column: price_str` — `seen_events` table was created with an old schema. |
| 2. Re-create `seen_events` table | Drop and recreate table | ❌ Would destroy historical first-seen timestamps, corrupting "Just Announced" diff tracking. |
| 3. Raw `ALTER TABLE` in initialization | Run `ALTER TABLE seen_events ADD COLUMN price_str TEXT` | ❌ Crashes with `duplicate column name` on subsequent runs unless guarded. |
| 4. Substring search for club night artists | Use `artist.lower() in text.lower()` | ❌ Created false positives: "airport" matched artist "Air", "takeoff" matched "Keo", "sixteen feet" matched "Feet". |
| 5. Word boundary regex + PRAGMA column check | Inspect `PRAGMA table_info` before migration, and use `\b{norm_artist}\b` over raw & unidecode text | ✅ Safe idempotent migration, zero false positives, and 100% accurate price/sold-out ingestion. |

---

## Root Cause Analysis

1. **Database Schema Divergence:**
   `EventDiffEngine._init_db()` created `seen_events` during initial project setup without `price_str` or `is_sold_out`. Because SQLite `CREATE TABLE IF NOT EXISTS` is a no-op when the table already exists, newer models fields were never persisted.
2. **Punctuation Mismatch in Artist Libraries:**
   Artists in Spotify profiles are normalized (e.g. `'fontaines dc'` without punctuation), whereas event titles and descriptions contain punctuated variants (e.g. `'Fontaines D.C.'`). Searching strictly for raw strings missed punctuation variants.
3. **Short Token Collisions:**
   Artist names with 3–4 letters easily collisioned with regular English vocabulary unless protected by word boundaries (`\b`).

---

## Working Solution

### 1. Idempotent SQLite Migration (`src/processing/event_diff_engine.py`)

```python
def _init_db(self):
    with self._get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                venue_name TEXT NOT NULL,
                venue_area TEXT NOT NULL,
                start_time TEXT,
                ticket_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                first_digest_label TEXT NOT NULL,
                price_str TEXT,
                is_sold_out INTEGER DEFAULT 0
            )
            """
        )
        # Idempotent migration for pre-existing databases
        cursor = conn.execute("PRAGMA table_info(seen_events)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "price_str" not in existing_cols:
            conn.execute("ALTER TABLE seen_events ADD COLUMN price_str TEXT")
        if "is_sold_out" not in existing_cols:
            conn.execute("ALTER TABLE seen_events ADD COLUMN is_sold_out INTEGER DEFAULT 0")

        conn.commit()
```

### 2. Multi-Platform Price & Sold-Out Ingestion

- **Songkick JSON-LD (`src/ingestion/songkick_engine.py`):**
  Handles Schema.org `Offer` and `AggregateOffer` (`lowPrice`, `highPrice`), and extracts `SoldOut` / `LimitedAvailability` availability statuses.
- **DICE (`src/ingestion/dice_scraper.py`):**
  Parses `status in ['sold-out', 'off-sale']`, `waiting_list_enabled == True`, and converts cents to pounds (`amount / 100`).
- **Ticketmaster (`src/ingestion/ticketmaster_engine.py`):**
  Parses `dates.status.code in ['soldout', 'offsale']` and formats `priceRanges`.

### 3. Musical Intelligence for Club Nights (`src/processing/tier_classifier.py`)

```python
def _check_club_night_taste_matches(self, event: Event) -> List[MatchRationale]:
    matches: List[MatchRationale] = []
    text_to_search = f"{event.title} {event.description or ''}"
    if not text_to_search.strip():
        return matches

    # Normalized version with punctuation stripped for robust token matching
    norm_text = re.sub(r"[^\w\s]", "", unidecode(text_to_search).lower())
    norm_text = re.sub(r"\s+", " ", norm_text).strip()

    matched_artists_seen: Set[str] = set()

    if self.taste_profile:
        elliott_artists = self.taste_profile.elliott.all_direct_artists
        chloe_artists = self.taste_profile.chloe.all_direct_artists
        all_artists = elliott_artists | chloe_artists

        # Longest names first to prevent sub-string shadowing
        sorted_artists = sorted(all_artists, key=len, reverse=True)

        for raw_artist in sorted_artists:
            norm_artist = normalize_artist_name(raw_artist)
            if not norm_artist or len(norm_artist) < 3 or norm_artist in matched_artists_seen:
                continue

            pattern_raw = rf"\b{re.escape(raw_artist)}\b"
            pattern_norm = rf"\b{re.escape(norm_artist)}\b"

            matched = bool(re.search(pattern_raw, text_to_search, re.IGNORECASE)) or bool(
                re.search(pattern_norm, norm_text, re.IGNORECASE)
            )

            if matched:
                matched_artists_seen.add(norm_artist)
                in_elliott = (norm_artist in elliott_artists) or (raw_artist in elliott_artists)
                in_chloe = (norm_artist in chloe_artists) or (raw_artist in chloe_artists)
                display_name = raw_artist.title() if raw_artist.islower() else raw_artist

                if in_elliott and in_chloe:
                    desc = f"🎧 Features mutual artist: {display_name}"
                    user = "Mutual"
                elif in_elliott:
                    desc = f"🎧 Features Elliott's favorite artist: {display_name}"
                    user = "Elliott"
                else:
                    desc = f"🎧 Features Chloe's favorite artist: {display_name}"
                    user = "Chloe"

                matches.append(MatchRationale(
                    tier=TierCategory.CLUB_NIGHT,
                    source=MatchSource.CLUB_TASTE_MATCH,
                    matched_act=display_name,
                    user=user,
                    description=desc,
                ))
                if len(matches) >= 3:
                    break

    # Preferred genre matching
    genre_count = 0
    for genre in self.preferred_genres:
        if re.search(rf"\b{re.escape(genre)}\b", text_to_search, re.IGNORECASE):
            matches.append(MatchRationale(
                tier=TierCategory.CLUB_NIGHT,
                source=MatchSource.GENRE_MATCH,
                matched_act=genre,
                description=f"🎧 Genre: {genre}",
            ))
            genre_count += 1
            if genre_count >= 3:
                break

    return matches
```

### 4. UI Rendering & Availability Filter (`templates/digest.html`)

- Render `🚫 SOLD OUT` badge and `💰 £XX.XX` / `💰 Free` pills.
- Replaced CTA button text on sold-out shows with dark-red `Sold Out • View →`.
- Added interactive toolbar filter:
  - `All Availability`
  - `Tickets Available Only`
  - `Sold Out Only`
- Bumped version identifier to `v0.0.2`.

---

## Prevention Strategies

1. **Schema Evolution Pattern:**
   Never assume SQLite tables match the latest Pydantic model. Always inspect `PRAGMA table_info` during startup and apply non-destructive `ALTER TABLE` additions.
2. **Dual-Text Normalization Pattern:**
   When searching arbitrary text for artist names:
   - Match raw text to preserve full strings.
   - Match punctuation-stripped `unidecode` text to catch dot/hyphen variants.
   - Always wrap with word boundary `\b` and ignore names under 3 characters.
3. **Automated Round-Trip Migration Tests:**
   Maintain unit tests (e.g. `test_idempotent_schema_migration_for_price_and_sold_out`) that deliberately construct legacy database tables and verify that upgrade routines succeed without crashing or data loss.

---

## Verification & Impact

- 77 automated tests passing in 0.47s.
- `data/cache/digest_history.sqlite` migrated with 741 events and 0 data loss.
- `public/index.html` rebuilt with 682 deduplicated events, `v0.0.2` badge, sold out tags, price pills, and genre/taste badges.
- Live deployment committed and pushed to `main`.
