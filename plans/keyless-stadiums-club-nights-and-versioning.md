# Plan: Keyless Stadium Discovery, Club Night Categorization, GitHub Setup & Versioning

> Created: 2026-11-03  
> Status: Draft  
> Exploration Ref: [docs/explorations/preview-cap-versioning-clubnights-ticketmaster-20261103.md](../docs/explorations/preview-cap-versioning-clubnights-ticketmaster-20261103.md)  
> Architectural Decisions: [docs/decisions/001-engine-architecture-and-data-ingestion.md](../docs/decisions/001-engine-architecture-and-data-ingestion.md), [docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md](../docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)

---

## Summary
Expand and streamline the **Live Curator Engine** across four high-value capabilities:
1. **Keyless Stadium & Arena Ingestion (Songkick Engine):** Eliminate the Ticketmaster Developer API key requirement completely by ingesting major London stadium and arena concert calendars (Wembley, Tottenham Hotspur Stadium, London Stadium, The O2 Arena, etc.) using public Schema.org `MusicEvent` JSON-LD structured data—zero API keys, zero accounts, and 100% sports-free.
2. **Club Nights as a 4th Distinct Category:** Separate late-night electronic DJ sets, disco parties, and dance club nights from live music and comedy (auto-detected via start time $\ge \text{22:00}$ and club keywords), featuring persistent user-tagging memory in SQLite and a dedicated `[🎧 Club Nights & DJs]` tab pill.
3. **Dynamic Semantic Versioning (`v0.0.1`) & GitHub Setup:** Introduce centralized version tracking (`src/__version__.py`), displaying `v0.0.1` prominently across the digest and UI headers, with an automated release bump utility and step-by-step GitHub repository publishing workflow.
4. **DICE Multi-Page Ingestion:** Support automated pagination on DICE venue pages to pull all upcoming events beyond the initial 30-event Next.js SSR payload.

---

## Problem Statement
1. **Ticketmaster Developer Friction:** The Ticketmaster Developer Portal frequently results in 404 errors, login loops, or inaccessible app registration pages. Requiring an external API key creates an unnecessary hurdle for stadium concert discovery.
2. **Club Night vs. Gig Confusion:** In London nightlife, live gigs (19:00–23:00) and late-night club nights / DJ parties (22:00–04:00) serve different moods. Mixing DJ parties into live music clutters band listings and buries club nights. Users need automated separation and persistent custom tagging.
3. **Single-Page DICE Cap:** DICE's initial Next.js SSR payload embeds 30 events per venue. High-volume venues (like MOTH Club or EartH) have dozens more future dates that should be captured.
4. **Version Traceability & GitHub Origin:** The project needs a clean version tag (`v0.0.1`) across all UI headers and clear instructions/scripts to host the repo cleanly on Elliott's GitHub.

---

## Prior Solutions

| Solution | Relevance | Action |
|----------|-----------|--------|
| [ADR-001: Live Curator Engine Architecture](docs/decisions/001-engine-architecture-and-data-ingestion.md) | ⭐️ Core Decision | Referencing |
| [ADR-002: Ticketmaster Ingestion and Single-Page Tier Cycling](docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md) | ⭐️ Core Decision | Extending |
| [Exploration: Preview Cap, Versioning, Club Nights & Songkick](docs/explorations/preview-cap-versioning-clubnights-ticketmaster-20261103.md) | ⭐️ Core Exploration | Implementing |
| [Pattern #09: Rigorous Planning (Multi-Order Thinking)](docs/solutions/patterns/individual/pattern-09-rigorous-planning-multi-order-thinking.md) | ⭐️ Best Practice | Following |
| [Pattern #24: Batch Resource Operations](docs/solutions/patterns/individual/pattern-24-batch-resource-operations.md) | ⭐️ Performance | Reusing |

---

## Proposed Architecture

### 1. Keyless Stadium Discovery Engine (`src/ingestion/songkick_engine.py`)
- Target venues:
  - Wembley Stadium (`https://www.songkick.com/venues/33134-wembley-stadium`)
  - Tottenham Hotspur Stadium (`https://www.songkick.com/venues/3983276-tottenham-hotspur-stadium`)
  - London Stadium (`https://www.songkick.com/venues/1817448-london-stadium-queen-elizabeth-olympic-park`)
  - The O2 Arena (`https://www.songkick.com/venues/17522-the-o2-arena`)
  - OVO Arena Wembley, Alexandra Palace, Royal Albert Hall, Finsbury Park, Drumsheds, etc.
- Mechanism:
  - Fetch public venue HTML via `requests` or `playwright`.
  - Extract `<script type="application/ld+json">` containing Schema.org `MusicEvent` objects.
  - Parse `name`, `startDate`, `performer`, `offers.url`, and map directly to `Event` domain models.
  - Zero API keys required; 100% sports-free.

### 2. Club Nights Category & Interactive Tagging Memory
- **Domain Model:**
  - Add `club_night_events: List[Event] = Field(default_factory=list)` to `MonthlyDigest`.
  - Add `is_club_night: bool = False` to `Event`.
- **Classification:**
  - Auto-classify as Club Night if:
    - Event start time $\ge \text{22:00}$ (10:00 PM), OR
    - Title or description matches club keywords (`club`, `dj set`, `disco`, `party`, `rave`, `dance`, `house`, `techno`, `club night`, `afterparty`, `all-nighter`).
- **Persistent User Tagging:**
  - SQLite database `data/cache/user_event_tags.sqlite`.
  - Schema: `CREATE TABLE IF NOT EXISTS user_tags (event_id TEXT PRIMARY KEY, category TEXT, tagged_at TIMESTAMP)`.
  - If a user tags an event as Club Night or Gig in the UI, that tag overrides automated heuristics permanently.
- **UI:**
  - Dedicated tab: `[🎧 Club Nights & DJs (N)]` in sticky navigation.
  - One-click tag buttons on event cards.

### 3. Dynamic Semantic Versioning (`v0.0.1`) & GitHub Setup
- `src/__version__.py` with `__version__ = "0.0.1"`.
- Display version in:
  - Digest header: `LIVE CURATOR // LONDON — v0.0.1`
  - Venue Manager UI header: `LIVE CURATOR // CONTROL PANEL — v0.0.1`
  - CLI banner: `LIVE CURATOR ENGINE // LONDON — v0.0.1`
- Version bump script: `scripts/bump_version.py` supporting `--patch`, `--minor`, `--major`.
- GitHub script: `scripts/setup_github.sh` guiding remote setup and push to Elliott's personal GitHub repository.

### 4. Multi-Page DICE Ingestion Loop
- In `src/ingestion/dice_scraper.py`:
  - Enhance `scrape_venue` to scroll down up to 3 times or until no new items are appended, harvesting all upcoming shows for high-volume venues.

---

## Acceptance Criteria

### Keyless Stadium Ingestion
- [ ] `src/ingestion/songkick_engine.py` implemented:
  - Ingests concerts from major London stadiums/arenas via public Schema.org JSON-LD.
  - Extracts title, lineup, dates, start times, and ticket URLs without requiring any API key or login.
  - Filters out sports fixtures automatically.
- [ ] Venues in `config/venues.yaml` updated with `songkick_url` and `platform: "songkick"`.
- [ ] Unit tests in `tests/test_songkick_engine.py`.

### Club Nights Category & User Tagging
- [ ] `TierClassifier` automatically detects club nights (start time $\ge \text{22:00}$ or club keywords).
- [ ] SQLite user tag storage (`data/cache/user_event_tags.sqlite`) remembers custom user categorizations.
- [ ] `MonthlyDigest` includes `club_night_events`.
- [ ] `templates/digest.html` displays:
  - `[🎧 Club Nights & DJs (N)]` interactive tab pill.
  - Distinct styling for club nights.
  - Quick action to toggle/tag events as Club Night or Live Gig.

### Semantic Versioning & GitHub Setup
- [ ] `src/__version__.py` created with `__version__ = "0.0.1"`.
- [ ] Version tag displayed in:
  - Digest header banner.
  - Venue Manager UI header banner.
  - CLI banner and `--help`.
- [ ] `scripts/bump_version.py` utility increments versions cleanly.
- [ ] `scripts/setup_github.sh` utility configures GitHub remote and pushes code.

### DICE Multi-Page Ingestion
- [ ] `DiceScraper` scrolls/paginates to collect more than the default 30 events on high-volume venue pages.

---

## Implementation Phases

### Phase 1: Dynamic Versioning (`v0.0.1`) & GitHub Setup
1. Create `src/__version__.py`.
2. Connect version to `main.py`, `templates/digest.html`, and `src/ui/venue_manager.py`.
3. Create `scripts/bump_version.py` and `scripts/setup_github.sh`.

### Phase 2: Keyless Stadium Ingestion (Songkick Engine)
1. Implement `src/ingestion/songkick_engine.py` using BeautifulSoup + JSON-LD `MusicEvent` parsing.
2. Update `config/venues.yaml` with Songkick URLs for Wembley, Tottenham, London Stadium, The O2, etc.
3. Ingest Songkick events into `run_pipeline()` alongside DICE.
4. Create unit tests in `tests/test_songkick_engine.py`.

### Phase 3: Club Nights Category & Tagging Memory
1. Update `Event` and `MonthlyDigest` models in `src/core/models.py`.
2. Implement club night classification heuristics in `src/processing/tier_classifier.py`.
3. Implement SQLite tagging persistence in `src/processing/user_tag_engine.py`.
4. Update `templates/digest.html` with `[🎧 Club Nights & DJs (N)]` tab and styling.

### Phase 4: DICE Multi-Page Ingestion
1. Update `src/ingestion/dice_scraper.py` with Playwright scroll pagination loop.
2. Update unit tests in `tests/test_dice_scraper.py`.

### Phase 5: Verification & Quality Assurance
1. Run full test suite with pytest (65+ tests).
2. Run end-to-end dry-run with browser preview.
3. Validate compound system and housekeeping.

---

## References
- [Exploration Document](docs/explorations/preview-cap-versioning-clubnights-ticketmaster-20261103.md)
- [ADR-001: Architecture Decision](docs/decisions/001-engine-architecture-and-data-ingestion.md)
- [Schema.org MusicEvent Specification](https://schema.org/MusicEvent)
