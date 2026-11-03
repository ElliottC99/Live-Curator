# Live Curator Engine Implementation Plan

> Created: 2026-11-03  
> Status: Ready for Review  
> Exploration Ref: [docs/explorations/live-curator-engine-20261103.md](../docs/explorations/live-curator-engine-20261103.md)  
> Architectural Decision: [docs/decisions/001-engine-architecture-and-data-ingestion.md](../docs/decisions/001-engine-architecture-and-data-ingestion.md)

---

## Summary
The **Live Curator Engine** is a modular Python application that automates monthly gig and comedy discovery across 9 East London grassroots venues ticketed on Dice.fm. It cross-references scraped line-ups against Elliott and Chloe's combined Spotify taste profiles (Saved Tracks, Playlists, Top Artists, Discover Weekly) and 7 British music publications' critical reviews (4★+ or 7.5+), categorizes events into a 3-tier hierarchy, and dispatches a responsive HTML email digest on the 1st of each month via local macOS cron or launchd.

---

## Problem Statement
Grassroots venues across Dalston and East London (The Shacklewell Arms, MOTH Club, Oslo, The Waiting Room, etc.) host hundreds of events monthly. Manually checking 9 distinct DICE venue listings, researching unfamiliar acts against personal taste, cross-referencing critical reception across UK music journalism, and coordinating event calendars takes hours every month. DICE protects its site behind Cloudflare Turnstile, making standard HTTP scrapers ineffective. Furthermore, Spotify deprecated its public recommendations endpoint in late 2024, requiring an updated discovery strategy.

---

## Prior Solutions

| Solution | Relevance | Action |
|----------|-----------|--------|
| [Live Curator Engine: Architectural & Feasibility Exploration](docs/explorations/live-curator-engine-20261103.md) | ⭐️ Core Exploration | Referencing |
| [ADR-001: Live Curator Engine Architecture and Ingestion Strategy](docs/decisions/001-engine-architecture-and-data-ingestion.md) | ⭐️ Core Decision | Referencing |

Usage update command:
```bash
./scripts/update-solution-ref.sh docs/explorations/live-curator-engine-20261103.md docs/decisions/001-engine-architecture-and-data-ingestion.md
```

---

## Research Findings

### 1. Dice.fm Anti-Bot & Data Extraction
- **Cloudflare WAF / Turnstile:** Standard `requests` or `httpx` receive 403 Forbidden. Using `playwright` with `playwright-stealth` in headless Chromium successfully resolves the Cloudflare challenge.
- **Data Stability:** Instead of fragile CSS class names (`.event-card__title--xyz`), DICE renders standard schema.org structured data (`<script type="application/ld+json">`) and React hydrated state on venue and event pages containing `MusicEvent`, `performer`, `startDate`, `location`, and ticket URLs.
- **Venues Config:** Target venues are externally defined in `config/venues.yaml` with names, DICE slugs, and neighborhoods.

### 2. Spotify API Taste Profiling & Late-2024 Deprecation
- **Deprecation:** On November 27, 2024, Spotify permanently disabled `GET /v1/recommendations` and `GET /v1/artists/{id}/related-artists` for third-party developer apps in Development Mode.
- **Discovery Solution:** Spotify automatically curates personalized discovery playlists inside each user's account: **"Discover Weekly"** and **"Release Radar"**. The engine reads tracks from these playlists via standard `/v1/playlists/{id}/tracks`, directly capturing Spotify's recommendation output.
- **Direct Matches:** Standard endpoints (`/v1/me/tracks`, `/v1/me/playlists`, `/v1/me/top/artists`) remain fully operational.
- **Dual-User Headless OAuth:** Script `scripts/auth_spotify.py` handles one-time interactive browser login for Elliott and Chloe, saving long-lived `refresh_token`s into `.env`. The monthly headless run programmatically exchanges refresh tokens for fresh access tokens.

### 3. Critical Review Aggregation
- **The Guardian:** Open Platform Content API (free 5,000 requests/day, returns star ratings in metadata) + `/music/reviews/rss`.
- **AnyDecentMusic?:** Scrapes recent releases table and filters for aggregate scores $\ge 7.5$.
- **DIY Magazine, Dork, The Line of Best Fit, NME, Loud & Quiet:** RSS feeds and review archives with rating extractors.
- **Local SQLite Cache:** `data/cache/reviews.sqlite` caches parsed reviews to prevent redundant requests and build a cumulative critical consensus.

---

## Architectural Decisions: ADR-001

Reference: [ADR-001](../docs/decisions/001-engine-architecture-and-data-ingestion.md)
1. **Playwright + Stealth** with JSON-LD extraction for Dice scraping.
2. **Discover Weekly / Release Radar + Top Artists + Critical Reviews** for Tier 2 discovery (avoiding deprecated Spotify recommendations API).
3. **Dual Refresh Tokens in `.env`** for zero-intervention monthly runs.
4. **Local SQLite Cache** for review deduplication.
5. **Decoupled Mailer Adapter** supporting standard Gmail SMTP App Password and SendGrid.

---

## Proposed Solution & Architecture

```text
Live Curator Engine
├── config/
│   ├── venues.yaml           # Seed venues list (Shacklewell Arms, MOTH Club, Oslo, etc.)
│   └── settings.yaml         # Publication score thresholds, comedy keywords, email config
├── src/
│   ├── core/
│   │   ├── config.py         # Strongly-typed configuration loader (Pydantic / dataclasses)
│   │   ├── models.py         # Domain entities: Event, Artist, Review, TierCategory
│   │   └── normalizer.py     # String unidecode, lineup splitting ("+ / w / feat"), fuzzy matching
│   ├── ingestion/
│   │   ├── dice_scraper.py   # Playwright stealth scraper for 9 Dice.fm venue pages
│   │   ├── spotify_engine.py # Dual-user Spotify OAuth & taste profiling
│   │   └── review_parser.py  # Aggregator for Guardian, ADM, DIY, Dork, TLOBF, NME, L&Q
│   ├── processing/
│   │   └── tier_classifier.py# 3-tier categorization engine
│   └── delivery/
│       ├── template_engine.py# Jinja2 responsive HTML email renderer
│       └── digest_mailer.py  # Gmail SMTP App Password & SendGrid dispatcher
├── templates/
│   ├── digest.html           # Responsive, mobile-first HTML email template
│   └── digest.txt            # Plain-text email fallback
├── scripts/
│   ├── auth_spotify.py       # One-time interactive OAuth setup for Elliott & Chloe
│   ├── test_dice_scraper.py  # Standalone dry-run scraper CLI
│   └── setup_cron.sh         # Installs local macOS launchd / cron job
├── tests/                    # Comprehensive unit tests
├── main.py                   # Master pipeline runner with CLI flags (--dry-run, --preview)
├── requirements.txt          # Python dependencies
└── README.md                 # Complete operational instructions
```

---

## 3-Tier Categorization Logic

| Tier | Name | Matching Rules |
|------|------|----------------|
| **Tier 1** | **Direct Matches** | Performer explicitly in Elliott's OR Chloe's Spotify Saved Tracks, user playlists, or top artists. |
| **Tier 2** | **Discovery Matches** | Performer in Elliott's or Chloe's Discover Weekly / Release Radar OR has a review with score $\ge 4\star$ / $\ge 7.5$ in tracked publications. |
| **Tier 3** | **Comedy & Alternative** | Event title, genre tags, or description matches comedy/alternative keywords (`stand-up`, `comedy`, `improv`, `cabaret`, `fringe`). |

---

## Acceptance Criteria

### Ingestion Modules
- [ ] `venues.yaml` contains all 9 seed venues:
  1. The Shacklewell Arms
  2. Oslo Hackney
  3. The Waiting Room
  4. MOTH Club
  5. The Victoria
  6. The George Tavern
  7. Hand of Glory
  8. EartH
  9. Next Door Records Two
- [ ] `dice_scraper.py` successfully navigates to all 9 venue pages using `playwright` + `playwright-stealth`, extracts upcoming monthly events (title, date/time, performers, ticket link, price) without Cloudflare 403 blocks.
- [ ] `spotify_engine.py` authenticates both Elliott and Chloe via stored refresh tokens, extracting:
  - Saved Tracks / Liked Songs
  - Custom Playlist tracks
  - Top Artists
  - Discover Weekly & Release Radar tracks
- [ ] `review_parser.py` ingests recent reviews from:
  - The Guardian (API/RSS)
  - AnyDecentMusic? ($\ge 7.5$)
  - DIY Magazine
  - Dork
  - The Line of Best Fit
  - Loud & Quiet
  - NME
  and stores them in `data/cache/reviews.sqlite`.

### Processing & Classification
- [ ] `normalizer.py` cleans artist strings, strips leading articles ("The "), strips accents ("Beyoncé" $\rightarrow$ "beyonce"), and accurately splits co-bills (`"Pond + Warmduscher"` $\rightarrow$ `["Pond", "Warmduscher"]`).
- [ ] `tier_classifier.py` classifies every scraped event into Tier 1, Tier 2, or Tier 3 (or unclassified).

### Delivery & Automation
- [ ] `template_engine.py` generates a clean, mobile-responsive HTML email digest grouped by Tier 1, Tier 2, and Tier 3 with date, venue, direct ticket links, and match rationale (e.g., *"In Chloe's Liked Songs"*, *"4★ Guardian Review"*).
- [ ] `digest_mailer.py` delivers the email via Gmail SMTP App Password or SendGrid.
- [ ] `main.py` provides `--dry-run` and `--preview-html` flags to inspect output locally without sending real emails.
- [ ] macOS scheduling script (`setup_cron.sh`) creates a working `launchd` plist / `cron` entry for monthly execution.

---

## Technical Considerations

### Dependencies
- Python 3.10+
- `playwright`, `playwright-stealth`: Browser automation & anti-bot evasion.
- `beautifulsoup4`, `lxml`: HTML and RSS feed parsing.
- `spotipy`: Spotify Web API client.
- `jinja2`: HTML email templating.
- `pydantic` & `pyyaml`: Configuration and domain model validation.
- `pytest`: Automated test suite.

### Edge Cases & Failure Modes
1. **Cloudflare IP Flagging:** If residential IP triggers a challenge, Playwright stealth waits up to 10s for Turnstile auto-solve before failing gracefully per venue.
2. **Missing Venue Slugs:** If a venue page slug changes or is inactive, the scraper logs a warning and continues with the remaining venues rather than crashing the pipeline.
3. **Spotify OAuth Token Expiry:** Refresh token exchange happens automatically on every run. If refresh token is revoked, the engine sends an alert email or raises an explicit error.
4. **Machine Sleep at 9:00 AM on the 1st:** Standard `cron` skips jobs if the machine is asleep. Providing a macOS `launchd` agent ensures the job triggers as soon as the Mac wakes up on the 1st of the month.

---

## Phased Implementation Plan

### Phase 1: Environment, Configuration & Domain Models
- Set up project structure, `requirements.txt`, and Python virtualenv.
- Install Playwright and browser binaries (`playwright install chromium`).
- Create `config/venues.yaml` with the 9 seed venues and DICE slugs.
- Create `config/settings.yaml` and `.env.example`.
- Implement `src/core/models.py` (`Event`, `Artist`, `Review`, `TierCategory`).
- Implement `src/core/normalizer.py` (act splitting, diacritics stripping, fuzzy matching) with unit tests in `tests/test_normalizer.py`.

### Phase 2: Dice.fm Stealth Scraper
- Implement `src/ingestion/dice_scraper.py` using Playwright Chromium + stealth.
- Extract structured JSON-LD and event card metadata.
- Implement pagination / "Load More" scrolling to capture the full upcoming calendar month.
- Implement polite scraping delays (2–4 seconds) and error recovery.
- Create `scripts/test_dice_scraper.py` dry-run CLI to verify against all 9 venues.

### Phase 3: Dual-User Spotify Engine
- Implement `src/ingestion/spotify_engine.py` with multi-user token refresh.
- Implement ingestion for:
  - Saved Tracks (`/v1/me/tracks`)
  - User Playlists (`/v1/me/playlists` + `/v1/playlists/{id}/tracks`)
  - Top Artists (`/v1/me/top/artists`)
  - Discover Weekly / Release Radar playlists
- Implement `scripts/auth_spotify.py` to easily authorize Elliott and Chloe interactively and write refresh tokens to `.env`.
- Add unit/mock tests in `tests/test_spotify_engine.py`.

### Phase 4: Critical Review Parser & SQLite Cache
- Implement `src/ingestion/review_parser.py`.
- Connect to The Guardian Content API / RSS.
- Implement scrapers/feed parsers for AnyDecentMusic?, DIY Magazine, Dork, The Line of Best Fit, NME, and Loud & Quiet.
- Store extracted reviews in `data/cache/reviews.sqlite` with artist name, score, source, and date.
- Add unit tests with mock HTML/RSS fixtures in `tests/test_review_parser.py`.

### Phase 5: 3-Tier Categorization Engine
- Implement `src/processing/tier_classifier.py`.
- Match Dice acts against Spotify direct taste (Tier 1).
- Match remaining acts against Spotify discovery & review scores (Tier 2).
- Filter event titles/descriptions for comedy/alternative keywords (Tier 3).
- Attach match rationale to each event for clear email display.
- Add unit tests in `tests/test_tier_classifier.py`.

### Phase 6: HTML Digest Templating & Mailer
- Design mobile-responsive email template `templates/digest.html` with inline styling.
- Implement `src/delivery/template_engine.py` using Jinja2.
- Implement `src/delivery/digest_mailer.py` supporting Gmail SMTP (App Password) and SendGrid.
- Add plain-text fallback generator `templates/digest.txt`.

### Phase 7: Orchestration CLI, macOS Automation & Verification
- Implement `main.py` tying all modules into an atomic pipeline:
  - CLI flags: `--dry-run`, `--preview-html`, `--venues-file`, `--force-refresh`.
- Create `scripts/setup_cron.sh` generating `~/Library/LaunchAgents/com.livecurator.monthly.plist` and `crontab` instructions.
- Create comprehensive `README.md` with setup walkthrough.
- Run complete dry-run validation.

---

## Next Steps
1. Review and approve plan.
2. Execute with **/work**.
