---
date: "2026-11-03"
exploration_type: research
component: "curator-architecture-and-ingestion"
status: concluded
time_box: "45m"
outcome: proceed_to_plan
last_referenced: "2026-11-03"
tags:
  - event-cap-analysis
  - semver-git-tagging
  - club-nights-category
  - songkick-stadium-ingestion
  - ticketmaster-alternatives
---

# Exploration: Event Limits, GitHub Versioning, Club Night Categorization & Ticketmaster Alternative

## Questions
1. Why did the previous test run top out at 30 events—was that because it was a preview or single venue?
2. Is it worth hosting the repository on GitHub with an auto-updating version tag starting at `v0.0.1` in the header?
3. How should the app support "Club Nights" as a separate, distinct category alongside Live Music and Comedy, including user-driven tagging memory?
4. Since the Ticketmaster developer portal is blocked or missing "My Apps", what is a superior, keyless alternative to ingest London stadium and arena concerts?

---

## Findings & Deep Research

### 1. Why Did the Event Count Top Out at 30?
- **Root Cause:**
  1. **Venue Filtering Flag:** The test command was executed with `--venue "MOTH Club"`. This instructed the engine to scrape **only 1 venue** (MOTH Club), skipping the other 49 configured venues.
  2. **DICE Initial Page Payload:** DICE embeds upcoming events inside Next.js SSR hydration data (`#__NEXT_DATA__`). For any single venue page, DICE's initial HTML payload returns **exactly 30 events**.
  3. **Multi-Venue Scalability:** When running across all venues (or by neighbourhood, e.g. `--area "dalston"`), the engine harvests hundreds of events (e.g. 50 venues $\times \sim 20\text{--}30 = 600\text{--}1,000+$ shows).
  4. **Pagination Beyond 30:** If an individual venue has more than 30 upcoming shows on DICE, those additional events are loaded dynamically on the web via client-side infinite scroll. We can easily add a scroll/load-more loop in Playwright to fetch all 60+ shows if desired.

---

### 2. GitHub Hosting & Dynamic Semantic Versioning (`v0.0.1`)
- **Current State:**
  - The repository is already a full Git repo with structured commit history.
  - Its current remote points to `origin https://github.com/salavender/antigravity-compound-engineering-plugin.git`.
- **Recommendation:**
  - Push to Elliott's personal GitHub repo (e.g. `git remote set-url origin https://github.com/elliottcallender/live-curator.git`).
  - Implement a centralized version module: `src/__version__.py` initialized at `__version__ = "0.0.1"`.
  - Display `v0.0.1` prominently in:
    1. The Digest HTML email header: `LIVE CURATOR // LONDON — v0.0.1`
    2. The in-app Venue Manager dashboard header.
    3. The CLI help and banner output.
  - Implement a simple automated version bumper (`scripts/bump_version.py` or GitHub Action) that increments patch versions (`v0.0.1` $\rightarrow$ `v0.0.2` $\rightarrow$ `v0.1.0`) on releases or new feature milestones.

---

### 3. Club Nights as a 4th Distinct Category
- **The Problem:**
  - London nightlife has a fundamental cultural difference between:
    1. **Live Music / Gigs:** Bands, singers, indie, jazz, acoustic (typically 19:00 - 23:00).
    2. **Comedy:** Stand-up, improv, work-in-progress (typically 19:30 - 22:00).
    3. **Club Nights & Electronic Parties:** DJ sets, dance, disco, queer line dancing, club nights (typically starting at 22:00 or 23:00 and running late into the night).
  - Mixing club nights into live music confuses users who want to see concerts, and buries late-night parties for users who want to go clubbing.
- **Proposed Architecture:**
  - Add `TierCategory.TIER_CLUB_NIGHT` (or `event.category = "live_music" | "comedy" | "club_night"`).
  - **Automated Detection Heuristics:**
    - **Start Time:** Events starting at $\ge \text{22:00}$ (10:00 PM).
    - **Keywords:** `club`, `dj set`, `disco`, `party`, `rave`, `dance`, `house`, `techno`, `club night`, `afterparty`, `all-nighter`.
    - **Venue Genres:** Venues with primary focus `["club", "djs", "electronic"]` (e.g. Drumsheds, Village Underground late sessions).
  - **User-Driven Tagging & Persistent Memory:**
    - Provide a one-click button in the preview and Venue Manager: `[🎧 Tag as Club Night]` or `[🎸 Tag as Gig]`.
    - Persist user tag overrides in SQLite (`data/cache/user_event_tags.sqlite`).
    - The engine remembers user classifications permanently across all future runs.
  - **Digest UI Representation:**
    - Dedicated tab pill in the sticky header: `[🎧 Club Nights & DJs (N)]` alongside `[🔥 Tier 1]`, `[✨ Tier 2]`, `[🎭 Tier 3]`, and `[🆕 New Announcements]`.

---

### 4. Keyless Ticketmaster Alternative: Songkick Stadium & Arena Ingestion
- **The Problem with Ticketmaster:**
  - Ticketmaster's developer portal frequently causes login loops, 404s, or blocks developer app registration depending on region, ad-blockers, and account types.
  - Requiring a manual API key is a significant point of friction.
- **The Solution: Songkick Public Stadium & Arena Ingestion:**
  - **How it Works:**
    - Songkick maintains publicly accessible, complete concert calendars for every major London stadium and arena:
      - Wembley Stadium (`songkick.com/venues/33134-wembley-stadium`)
      - Tottenham Hotspur Stadium (`songkick.com/venues/3983276-tottenham-hotspur-stadium`)
      - London Stadium (`songkick.com/venues/1817448-london-stadium-queen-elizabeth-olympic-park`)
      - The O2 Arena (`songkick.com/venues/17522-the-o2-arena`)
      - Alexandra Palace, Royal Albert Hall, Finsbury Park, Drumsheds, etc.
    - Songkick embeds **standard Schema.org `MusicEvent` JSON-LD** in the page HTML.
    - We can ingest 100% of stadium headliners using clean Python HTTP requests (`requests` + `json` or `playwright`).
  - **Benefits:**
    - ✅ **Zero API keys required.**
    - ✅ **Zero developer registration or portal logins.**
    - ✅ Exclusively lists music concerts (automatically sports-free).
    - ✅ Includes verified headliners, dates, start times, and direct ticket links.
    - ✅ Ticketmaster can remain as an optional fallback for those who have a key.

---

## Multi-Order Analysis (Think Hard)

### Direct Effects (1st Order)
- Users can ingest stadium concerts immediately without an API key via Songkick.
- Events $\ge \text{22:00}$ or matching club keywords are grouped into `Club Nights`, cleaning up the Live Music listings.
- Version `v0.0.1` appears in headers, providing clear build traceability.

### Ripple Effects (2nd-4th Order)
- **2nd Order:** With club nights separated, live music fans see much higher match density in Tier 1 and Tier 2, while clubbers can jump directly to the `[🎧 Club Nights]` tab.
- **3rd Order:** Persistent user tagging in SQLite allows the app to learn Elliott & Chloe's specific classification preferences over time.
- **4th Order:** The engine becomes an all-in-one London cultural guide covering live bands, comedy, clubbing, and stadium tours with zero external API key friction.

---

## Stakeholder Impact Matrix

| Stakeholder | Impact | Severity |
|-------------|--------|----------|
| Elliott & Chloe | Immediate stadium coverage with zero setup friction; clean separation between gigs and late-night clubs | High Positive |
| Maintainer | Versioned releases and automated JSON-LD ingestion require zero key management | High Positive |
| App Stability | Decoupled from Ticketmaster API developer portal availability | High Positive |

---

## Decision & Next Steps
- **Verdict:** Proceed to `/plan` to implement:
  1. **Songkick Keyless Stadium Ingestion Engine:** Automatic JSON-LD concert ingestion for all major London stadiums/arenas without requiring any API key.
  2. **Club Nights Category & Interactive Tagging:** 4th tier/category for events starting $\ge \text{22:00}$ or matching DJ/club keywords, with SQLite memory for user tags.
  3. **Version Tagging (`v0.0.1`):** Centralized version module in `src/__version__.py` displayed in digest and UI headers.
  4. **Multi-Page Ingestion:** Support pagination on DICE venue pages so venues with $>30$ events are captured completely.

---

## References
- [ADR-001: Architecture Decision](docs/decisions/001-engine-architecture-and-data-ingestion.md)
- [ADR-002: Ticketmaster Ingestion and Single-Page Tier Cycling](docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)
- [Schema.org MusicEvent Specification](https://schema.org/MusicEvent)
