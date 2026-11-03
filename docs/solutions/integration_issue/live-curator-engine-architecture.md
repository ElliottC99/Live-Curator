---
date: 2026-11-03
problem_type: integration_issue
severity: high
symptoms:
  - "DICE.fm venue event extraction blocked by Cloudflare Turnstile bot detection with 403 Forbidden on standard HTTP libraries."
  - "Spotify public recommendations API returned 404/403 due to permanent deprecation on Nov 27, 2024."
  - "WordPress review RSS feeds crashed standard xml.etree.ElementTree due to undeclared namespace prefixes."
  - "Need sleep-safe recurring monthly execution on macOS without missed cron jobs."
root_cause:
  - "Modern event ticketing platforms utilize dynamic browser fingerprinting and client hydration (Next.js __NEXT_DATA__) requiring genuine browser rendering."
  - "Spotify deprecated seed-based algorithmic recommendation endpoints for standard apps, requiring library and playlist ingestion instead."
  - "ElementTree is strict and fails on unmapped XML namespaces; BeautifulSoup with lxml is namespace-resilient."
tags:
  - dice-scraping
  - playwright-stealth
  - spotify-oauth
  - music-reviews
  - tier-classification
  - macos-launchd
---

# Live Curator Engine — Architecture, Ingestion & Categorization

## Problem Overview
Grassroots venues across East London (The Shacklewell Arms, MOTH Club, Oslo Hackney, The Waiting Room, etc.) host hundreds of events each month ticketed via DICE.fm. Manual curation required hours of checking separate venue pages, manually reviewing unfamiliar artists against personal Spotify taste, searching UK music journalism (The Guardian, NME, DIY, Dork, Loud & Quiet), and compiling event listings.

Key architectural hurdles:
1. **DICE Anti-Bot Protection**: Cloudflare Turnstile actively blocks `requests`, `urllib`, and standard HTTP scrapers.
2. **Spotify Recommendations Deprecation**: Spotify deprecated `/v1/recommendations` on Nov 27, 2024.
3. **Lineup Delimiters & Name Normalization**: DICE listings format lineups with complex separators (`+`, `w/`, `feat.`, `b2b`) and accented artist names requiring resilient fuzzy and accent-stripped matching.
4. **Feed Ingestion Quirks**: UK music publications employ varied markup (WordPress feeds with XML namespaces, card HTML with class-based star ratings, and server connection resets).

---

## Solved Architecture & Key Implementations

### 1. DICE.fm Stealth Scraper (`src/ingestion/dice_scraper.py`)
- Used `playwright` with `playwright-stealth`.
- Configured Chromium with `--disable-blink-features=AutomationControlled` and `--no-sandbox`.
- Extracted structured Next.js `#__NEXT_DATA__` server-side rendered state directly from DOM:
  - Bypasses Cloudflare Turnstile instantly (~1.2s per venue).
  - Extracts full event payload: title, acts, price, venue, start time, and ticket URL.
  - Active venue slug format reverse-engineered: e.g. `the-shacklewell-arms-z82z`, `moth-club-43ox`, `oslo-hackney-je6z`, `the-waiting-room-jxea`, `earth-76a7`.

### 2. Dual-User Spotify Ingestion (`src/ingestion/spotify_engine.py`)
- Implemented headless OAuth token lifecycle using long-lived refresh tokens stored in `.env`.
- Solved Spotify recommendations deprecation by ingesting:
  - All user-created and followed playlists (e.g. 27 playlists yielding 557 unique direct artists).
  - Liked Songs / Saved Tracks (`/v1/me/tracks`).
  - Top Artists across short/medium/long terms (`/v1/me/top/artists`).
  - Algorithmic discovery playlists ("Discover Weekly" & "Release Radar").
- Handled Spotify API schema variation where track objects appear under key `item` instead of `track`.

### 3. Critical Music Review Aggregator (`src/ingestion/review_parser.py`)
- Ingested 7 British music publications: The Guardian, DIY Magazine, Dork, NME, Loud & Quiet, AnyDecentMusic?.
- Replaced `xml.etree.ElementTree` with `BeautifulSoup(content, 'xml')` to eliminate namespace crashes.
- Extracted exact star ratings (`stars-5`, `stars-4`, `stars-4-5`) and 10-point scales.
- Cached in SQLite database (`data/cache/reviews.sqlite`) with fast indexed lookups by normalized artist name.

### 4. 3-Tier Categorization Engine (`src/processing/tier_classifier.py`)
- **Tier 1 (Direct Matches)**: Matches acts against Elliott or Chloe's Spotify library, attaching rationales like `In Elliott's Playlists` or `In Chloe's Liked Songs`.
- **Tier 2 (Discovery Matches)**: Matches acts against Discover Weekly / Release Radar or $\ge 4\star$ / $\ge 7.5/10$ critical reviews (e.g. `4★ review in Dork`).
- **Tier 3 (Comedy & Alternative)**: Matches event title/description against word-boundary keywords (`comedy`, `stand-up`, `improv`, `fringe`, `wip`).

### 5. Responsive HTML Email & Delivery (`src/delivery/`)
- Mobile-first, dark-aesthetic responsive email template (`templates/digest.html`) using inline CSS and table layout.
- Jinja2 template compiler and multi-channel dispatcher supporting Gmail SMTP (`smtp.gmail.com:587`, TLS, App Password) and SendGrid API.

### 6. Sleep-Resilient Scheduling on macOS (`scripts/setup_cron.sh`)
- Generates `~/Library/LaunchAgents/com.livecurator.monthly.plist` scheduled for Day 1 of every month at 09:00 AM.
- Unlike traditional `cron` which misses triggers if the Mac is asleep, `launchd` catches up immediately upon wake.

---

## Verification
- 47 automated tests passing in `tests/` (`test_config`, `test_dice_scraper`, `test_normalizer`, `test_review_parser`, `test_spotify_engine`, `test_tier_classifier`, `test_delivery`).
- Live e2e validation performed:
  - MOTH Club: 30 events scraped, 5 Tier 3 comedy events categorized (Jamali Maddix, Ivo Graham, Harry Hill WIP).
  - The Shacklewell Arms: 30 events scraped, 1 Tier 1 direct match identified (`Martial Arts` in Elliott's playlists).
  - Rendered HTML preview generated and verified in browser at `output/preview.html`.
