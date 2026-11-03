---
title: "Exploration: Root Cause Analysis of 'Only MOTH Club and 33 Shows' on GitHub Pages"
date: "2026-11-03"
exploration_type: "investigation"
component: "ingestion-and-deployment"
status: "concluded"
time_box: "30m"
outcome: "proceed_to_plan"
last_referenced: "2026-11-03"
tags:
  - exploration
  - scraping
  - data-pipeline
  - github-pages
  - multi-venue
  - seed-data
summary: "Investigation into why the live GitHub Pages site displays only MOTH Club and 33 total shows instead of all 51 configured London venues, and the multi-venue harvesting solution to populate all venues."
---

# Exploration: Why GitHub Pages Displays Only MOTH Club and 33 Shows

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Question:** *Why does the Live Curator deployment on GitHub Pages only display MOTH Club and 33 shows, and how do we ensure all 51 configured London venues and their hundreds of live shows are populated and deployed?*

---

## 1. Executive Summary

When inspecting `https://elliottc99.github.io/Live-Curator/`, the application displays exactly 33 shows, 32 of which are from **MOTH Club** in Hackney (and 1 from Wembley Stadium). The remaining 50 venues configured in `config/venues.yaml` (spanning Dalston, Camden, Islington, Brixton, Stoke Newington, Shoreditch, Peckham, and London's major stadiums/arenas) are missing from the deployed site.

The root cause is a **data lineage disconnect between local single-venue test runs and the version-controlled seed data used by GitHub Actions**:
1. During local test cycles, `main.py` was executed with `--venue "MOTH Club"` to avoid long multi-venue scrape runs during test iterations.
2. The SQLite database at `data/cache/digest_history.sqlite` was thus populated solely with events from MOTH Club (32 rows) and 1 Wembley Stadium test row.
3. When `data/seed_events.json` was introduced (to bypass GitHub Actions' lack of SQLite database access), it was generated directly from `digest_history.sqlite`. It captured only that 33-event subset.
4. GitHub Actions does not run live web scrapers during CI deployment—it executes `scripts/build_pages.py`, which loads `data/seed_events.json`. Because `seed_events.json` contained only 33 MOTH Club shows, the resulting static site deployed to GitHub Pages only contained those 33 shows.

To solve this completely, we must execute a comprehensive multi-venue harvest across all 51 venues in `config/venues.yaml`, populate `data/seed_events.json` with all hundreds of active shows across London, rebuild the static assets, and push to GitHub.

---

## 2. Deep Root-Cause Trace

### 2.1 The Multi-Venue Architecture
`config/venues.yaml` defines 51 venues across London:
- **DICE Platforms (31 venues):**
  - *Hackney:* MOTH Club, Oslo Hackney, Paper Dress Vintage, Night Tales, Hackney Church
  - *Dalston:* The Shacklewell Arms, The Victoria, EartH, Cafe OTO, SJQ, The Jago
  - *Camden:* Camden Assembly, Underworld, Electric Ballroom, Koko, Dingwalls, Roundhouse
  - *Islington:* The Lexington, The Garage, Union Chapel, Hope & Anchor, Old Queens Head
  - *Stoke Newington:* The Waiting Room, The Rose & Crown
  - *Brixton:* Brixton Windmill, Electric Brixton, O2 Academy Brixton, Hootananny Brixton
  - *Peckham:* CLF Art Lounge, Peckham Audio
- **Songkick Platforms (16 venues):**
  - Wembley Stadium, Tottenham Hotspur Stadium, The O2 Arena, Alexandra Palace, Royal Albert Hall, Drumsheds, etc.

### 2.2 Where the Data Truncation Occurred
1. **Targeted CLI Testing:**
   In early development, running the entire scraper across 51 venues takes several minutes. Developers ran:
   ```bash
   python3 main.py --venue "MOTH Club"
   ```
   This created table `seen_events` in `data/cache/digest_history.sqlite` with only 32 MOTH Club rows.

2. **The SQLite `.gitignore` Problem:**
   `data/cache/*.sqlite` is correctly ignored in `.gitignore` (as SQLite binaries should not be checked into Git).

3. **The Seed File Creation:**
   In `scripts/build_pages.py`:
   ```python
   def load_events_from_history() -> list[Event]:
       db_path = PROJECT_ROOT / "data" / "cache" / "digest_history.sqlite"
       if db_path.exists():
           # Exports whatever is in seen_events into data/seed_events.json
   ```
   Because `digest_history.sqlite` had only 33 rows, `data/seed_events.json` was populated with only 33 rows!

4. **GitHub Actions Workflow:**
   In `.github/workflows/deploy-pages.yml`:
   ```bash
   python3 scripts/build_pages.py
   ```
   The GitHub runner has no local SQLite cache. It falls back to reading `data/seed_events.json`. Because that file only had 33 MOTH Club events, GitHub Pages rendered only 33 shows.

---

## 3. Best Practices & Multi-Order Analysis

### 3.1 Industry Standards for Static CI Site Generation with Dynamic Data
- **Static Site Generators (SSGs) with Pre-built Seed Datasets:**
  In headless static deployments (GitHub Pages, Vercel, Netlify), CI runners should not perform uncontrolled, heavy external web scraping against dozens of third-party domains (risk of rate-limiting, IP blocking, flaky CI timeouts).
- **Scheduled Content Harvesting & Git-Tracked Datasets:**
  A scheduled GitHub Action (e.g., cron every Monday morning) or local automated job scrapes fresh listings, commits an updated `data/seed_events.json`, and triggers the Pages build.

### 3.2 Multi-Order Consequences
- **1st Order:** Running a full scrape populates 300–600+ events across all 51 venues into `data/seed_events.json`.
- **2nd Order:** `build_pages.py` embeds all 51 venues into `public/index.html` and `public/venues.html`. The neighbourhood dropdown filter now allows users to filter by Dalston, Camden, Islington, Brixton, Wembley, etc.
- **3rd Order:** Git-tracking `data/seed_events.json` gives full reproducibility: anyone cloning the repository or running CI builds the exact full catalogue without needing network or API keys.

---

## 4. Verification of Live Scrapers

Before performing the full harvest, we verified that all platform scrapers function reliably:
1. **Songkick Scraper (`src/ingestion/songkick_engine.py`):**
   - Tested Wembley Stadium: returned 3 upcoming stadium shows.
   - Tested The O2 Arena: returned 8 upcoming arena shows.
2. **DICE Scraper (`src/ingestion/dice_scraper.py`):**
   - Tested The Shacklewell Arms (Dalston): returned 30 upcoming shows.
   - Tested MOTH Club: returned 32 upcoming shows.

All scrapers return normalized `Event` dataclass models ready for storage in SQLite and `data/seed_events.json`.

---

## 5. Solution & Execution Plan

1. **Harvest Script (`scripts/harvest_all_venues.py`):**
   Create a dedicated, robust harvester that iterates over all 51 venues in `config/venues.yaml` (DICE + Songkick):
   - Scrapes upcoming concerts, club nights, and events.
   - Writes directly to `data/cache/digest_history.sqlite` (`seen_events` table).
   - Exports the full, unified catalogue into `data/seed_events.json`.
2. **Run Harvesting with Network Bypass:**
   Execute `scripts/harvest_all_venues.py` with `BypassSandbox: true` to scrape DICE and Songkick.
3. **Rebuild Static Site:**
   Run `scripts/build_pages.py` to regenerate `public/index.html` and `docs/index.html` with the full 300–600+ event dataset.
4. **Deploy:**
   Commit `data/seed_events.json`, `public/index.html`, and `docs/` and push to GitHub.
