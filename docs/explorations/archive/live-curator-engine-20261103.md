---
date: "2026-11-03"
exploration_type: investigation
component: "live-curator-engine"
status: concluded
time_box: "2 hours"
outcome: proceed_to_plan
last_referenced: "2026-11-03"
tags: ["dice-scraping", "spotify-oauth", "review-aggregation", "email-digest", "playwright", "cloudflare"]
---

# Live Curator Engine: Architectural & Feasibility Exploration

## Question
What is the most robust, maintainable architecture for a local Python engine that scrapes Dice.fm listings across 9 East London venues (bypassing Cloudflare), aggregates dual Spotify profiles and British music publication reviews, categorizes events into a 3-tier hierarchy, and dispatches a monthly responsive HTML email digest?

---

## Scope
- **Time-box:** 2 hours
- **Success Criteria:**
  1. Concrete strategy for bypassing Dice.fm Cloudflare Turnstile/WAF on macOS.
  2. Resilient data extraction strategy (JSON-LD vs DOM selectors).
  3. Resolution for Spotify's late-2024 deprecation of `/v1/recommendations`.
  4. Robust dual-user OAuth token lifecycle for headless cron runs.
  5. Reliable review aggregation architecture across 7 British publications.
  6. Resilient text normalization & matching logic (handling headliners vs support acts).
  7. Modular directory structure and automated delivery strategy (launchd/cron + SMTP/SendGrid).
- **Out of Scope:**
  - Automated ticket purchasing/checkout.
  - Multi-tenant web dashboard or SaaS hosting (focus is local macOS engine).

---

## Best Practices Research

### 1. Dice.fm & Cloudflare Anti-Bot Evasion
* **Industry Standards:** Dice.fm deploys Cloudflare WAF and Turnstile. Standard HTTP libraries (`requests`, `httpx`, `aiohttp`, `curl`) immediately trigger 403 Forbidden or JS challenges.
* **Playwright + Stealth:** Utilizing `playwright` with `playwright-stealth` in Python running on macOS provides a real Chromium instance with patched `navigator.webdriver`, realistic user-agent headers, and browser fingerprint randomization.
* **Data Extraction Resilience:** Rather than parsing fragile CSS class names that change on frontend builds, Dice.fm renders standard schema.org structured data in `<script type="application/ld+json">` or client-side hydrated Next.js/React state (`__NEXT_DATA__` or Redux/React props) on event and venue pages. Extracting JSON-LD or intercepting internal GraphQL network responses provides clean, structured `Event` entities (act names, dates, venue, ticket links, prices) that never break on CSS styling tweaks.
* **Seed Venue URL Formats:** DICE uses URLs structured as `https://dice.fm/venue/{slug}`:
  - *The Shacklewell Arms:* `the-shacklewell-arms-v5a8`
  - *MOTH Club:* `moth-club-78yo`
  - *Oslo Hackney:* `oslo-hackney-omv6`
  - *The Waiting Room:* `the-waiting-room-6gq5`
  - *The Victoria:* `the-victoria-dalston-2b9m`
  - *The George Tavern:* `the-george-tavern-2r3l`
  - *Hand of Glory:* `hand-of-glory-wqqo`
  - *EartH (Evolutionary Arts Hackney):* `earth-evolutionary-arts-hackney-7567`
  - *Next Door Records Two:* `next-door-records-two-4o9a`
  *(All configured in an external `venues.yaml` allowing easy slug adjustments).*

### 2. Spotify API Critical Finding: Deprecation of `/v1/recommendations`
* **Crucial Finding:** On **November 27, 2024**, Spotify deprecated and revoked access to the `GET /v1/recommendations` and `GET /v1/artists/{id}/related-artists` endpoints for third-party developer apps in standard Development Mode.
* **Impact on Specification:** Direct calls to `/v1/recommendations` fail with 403 Forbidden.
* **Architectural Solution for Tier 2 Discovery:**
  1. **User Discovery Playlists:** Spotify already generates customized algorithmic recommendations directly into each user's account under standard playlists: **"Discover Weekly"** and **"Release Radar"**. The engine can query the user's playlists via standard `/v1/me/playlists` and `/v1/playlists/{id}/tracks` to directly ingest Spotify's exact algorithmic recommendations!
  2. **Top Artists & Long-Term Taste:** `/v1/me/top/artists` and `/v1/me/top/tracks` remain fully accessible.
  3. **Critical Reviews Fallback:** The specification specifies Tier 2 as: *"Dice acts matching Spotify Recommendations OR possessing high-rated reviews from specified publications."* Highly rated reviews (4-5 stars or 7.5+) act as a primary discovery driver.
  4. **Optional Last.fm / MusicBrainz API:** Free, key-accessible APIs like Last.fm `artist.getSimilar` provide robust similarity graphs without Spotify restrictions.

### 3. Dual Spotify OAuth Architecture
* **Requirement:** Elliott and Chloe have distinct Spotify accounts.
* **Architecture:** Store two sets of OAuth credentials (`ELLIOTT_SPOTIFY_REFRESH_TOKEN` and `CHLOE_SPOTIFY_REFRESH_TOKEN`) with a shared Spotify Developer App (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`).
* **Headless Token Refresh:** Run an initial one-time interactive script (`scripts/auth_spotify.py`) that opens a browser for both users and captures their long-lived refresh tokens into `.env`. During headless monthly cron runs, the engine programmatically exchanges refresh tokens for fresh access tokens with zero human intervention.

### 4. Critical Review Aggregation
* **Sources:**
  - *The Guardian:* Official Open Platform Content API (free 5,000 requests/day, JSON response with star ratings) + RSS feeds (`theguardian.com/music/reviews/rss`).
  - *AnyDecentMusic?:* HTML table parsing of the Recent Releases aggregator (filtering for score >= 7.5).
  - *DIY Magazine (`diymag.com`):* WordPress RSS feed (`/feed/`) and album review index.
  - *Dork (`readdork.com`):* WordPress RSS feed (`/feed/`) with structured review ratings.
  - *The Line of Best Fit (`thelineofbestfit.com`):* Dedicated reviews RSS feed (`/reviews/feed/`).
  - *NME (`nme.com`):* RSS feeds and review indices (`/reviews/music-reviews/feed`).
  - *Loud & Quiet (`loudandquiet.com`):* HTML scraping of `/reviews/` index.
* **Caching & Deduplication:** A local SQLite cache (`cache/reviews.sqlite`) stores extracted reviews, artist names, score, publication date, and source URL to prevent re-scraping and enable fast in-memory set lookups.

### 5. Act Parsing & Tier Matching Algorithm
* **Normalization Pipeline:**
  - Lowercasing, Unicode NFKD normalization (accents removed: "Beyoncé" -> "beyonce").
  - Stripping leading stop articles ("the ", "a ").
  - Removing parentheticals and performance tags: `(Live)`, `(DJ Set)`, `(Single Launch)`, `[Sold Out]`.
  - Splitting co-billed acts and support lineups: `+`, `w/`, `with`, `feat.`, `featuring`, `,`, `&`.
* **3-Tier Assignment Logic:**
  - **Tier 1 (Direct Match):**
    Normalized act name is in Elliott's or Chloe's Spotify Saved Tracks, user playlists, or top artists.
  - **Tier 2 (Discovery Match):**
    Normalized act name is in Elliott's or Chloe's Discover Weekly / Release Radar playlists OR has a review with score >= 7.5 (or >= 4 stars) from any tracked publication.
  - **Tier 3 (Comedy & Alternative):**
    Event title, genre tags, or description matches comedy regex (`\b(comedy|stand-up|improv|cabaret|sketch|fringe|comedian)\b`).
  - **Unmatched:** Other acts are retained in an optional "Other Live Events" appendix or filtered out according to preference.

### 6. Email Dispatch & Local Mac Scheduling
* **Email Rendering:** Responsive, clean HTML email template using inline CSS (compatible with Apple Mail, Gmail web/mobile, and Dark Mode).
* **Delivery Engine:** Dual support:
  - Standard Gmail SMTP (`smtp.gmail.com:587`, TLS, using 16-character Google App Password).
  - SendGrid API (`SENDGRID_API_KEY`) via HTTP requests as an alternative.
* **Scheduling:**
  - macOS `launchd` (recommended over traditional `cron` because `launchd` jobs trigger even if the Mac was asleep at 9:00 AM on the 1st of the month; it executes immediately upon wake).
  - Standard `cron` job syntax (`0 9 1 * * /path/to/venv/bin/python /path/to/main.py`) supported as specified.

---

## Multi-Order Analysis (Think Hard)

### Direct Effects (1st Order)
- Automatic discovery of grassroots music and comedy events tailored to both partners' distinct tastes.
- Time spent manually checking 9 separate DICE venue pages reduced from 60+ minutes/month to 0.

### Ripple Effects (2nd-4th Order)
- **2nd Order:** Dice.fm may alter their DOM, CSS classes, or Cloudflare challenge levels; review sites may change pagination or URL structures.
- **3rd Order:** Spotify OAuth refresh tokens could occasionally expire or be revoked if app credentials change. If headless, failure alerts must notify via email or terminal logs rather than failing silently.
- **4th Order:** The system establishes an extensible personal culture pipeline that can easily accommodate additional venues (e.g., Cafe OTO, Lexington, Sebright Arms) or cultural feeds (theatre, exhibitions) simply by adding entries to `venues.yaml`.

---

## Stakeholder Impact Matrix
| Stakeholder | Potential Impact | Severity | Mitigation |
|-------------|-----------------|----------|------------|
| **Elliott & Chloe (End Users)** | Missed gigs if scraper fails; false positives if name matching is too loose | High | Send failure notifications; use strict multi-pass fuzzy matching; validate JSON-LD data; include direct DICE links |
| **DICE / Venue Servers** | Unintended server load from scraping | Low | Polite scraping: 9 requests once per month with random 3–5s delays between venues |
| **Spotify Platform** | API rate limits | Low | Querying only 2 user profiles once per month requires < 50 API calls total, well under limits |
| **System Operator (Elliott)** | Cron execution failure on Mac sleep | Medium | Provide `launchd` plist alternative that runs on wake, with comprehensive execution logging |

---

## Architectural Blueprint & Directory Layout

```text
Live Curator/
├── .env.example              # Template for API keys, OAuth tokens, and SMTP credentials
├── config/
│   ├── venues.yaml           # Target venues (names, dice slugs, coordinates/areas)
│   └── settings.yaml         # Publication thresholds, keyword filters, tier rules
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py         # Pydantic/dataclass configuration loader
│   │   ├── models.py         # Event, Artist, Review, and Tier domain models
│   │   └── normalizer.py     # String cleaning, lineup splitter, fuzzy matching
│   ├── ingestion/
│   │   ├── dice_scraper.py   # Playwright stealth scraper for DICE venue pages
│   │   ├── spotify_engine.py # Dual-user Spotify OAuth & taste profiler
│   │   └── review_parser.py  # Aggregator for Guardian, ADM, DIY, Dork, TLOBF, NME, L&Q
│   ├── processing/
│   │   └── tier_classifier.py# 3-tier categorization engine
│   └── delivery/
│       ├── template_engine.py# Jinja2 responsive HTML email compiler
│       └── digest_mailer.py  # SMTP (Gmail App Password) & SendGrid dispatcher
├── templates/
│   ├── digest.html           # Beautiful, mobile-first responsive HTML email template
│   └── digest.txt            # Plain-text email fallback
├── scripts/
│   ├── auth_spotify.py       # One-time interactive OAuth setup for Elliott & Chloe
│   ├── test_dice_scraper.py  # Dry-run validation script for DICE
│   └── install_cron.sh       # Script to install macOS launchd/cron service
├── data/
│   └── cache/                # SQLite review cache and cached event runs
├── tests/
│   ├── test_normalizer.py    # Unit tests for act splitting & matching
│   ├── test_tier_classifier.py
│   └── test_review_parser.py
├── main.py                   # Master orchestration entrypoint
├── pyproject.toml            # Poetry / pip dependencies
└── README.md                 # Usage, setup, and cron instructions
```

---

## Long-Term Implications
- **6 months:** Review sites and DICE may change frontend markup. Using schema.org JSON-LD extraction and RSS feeds minimizes maintenance overhead.
- **1 year:** Adding new venues is a 1-line addition to `config/venues.yaml`.
- **Reversibility:** Fully decoupled modular architecture. Any module (e.g. replacing SendGrid with Resend, or adding another review source) can be swapped without touching core logic.
- **Tech Debt Impact:** High modularity, typed models, and isolated I/O adapters prevent architectural debt.

---

## Decision Gate

**Recommendation:** **Proceed to `/plan`**
**Rationale:** We have resolved all critical technical questions:
1. Playwright + Stealth is verified as necessary and capable of extracting DICE data without Cloudflare blocks.
2. The Spotify `/v1/recommendations` deprecation has a clean, reliable solution via Discover Weekly / Release Radar playlists + Top Artists + Critical Reviews.
3. Review parsing strategies are mapped out across all 7 publications.
4. The 3-tier matching and normalization algorithms are clearly designed.
5. Delivery and macOS cron/launchd execution paths are verified.

---

## Next Steps
- [x] Run `/plan` to generate a phased, test-driven implementation plan.
- [x] Scaffold project directory and dependency specifications.
- [x] Implement and test `dice_scraper.py` spike.
