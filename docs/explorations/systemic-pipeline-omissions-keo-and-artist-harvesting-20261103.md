---
title: "Exploration: Systemic Pipeline Omissions — Keo, O2 Academy Brixton, & Spotify Taste Decoupling"
date: "2026-11-03"
exploration_type: "investigation"
component: "ingestion-and-taste-matching"
status: "concluded"
time_box: "45m"
outcome: "proceed_to_plan"
last_referenced: "2026-11-03"
tags:
  - exploration
  - systemic-analysis
  - keo
  - o2-academy-brixton
  - songkick-pagination
  - spotify-live-sync
  - venue-filters
summary: "Investigation into why Keo's upcoming headline tour show at O2 Academy Brixton was missing despite being in Elliott's playlists. Uncovered four major systemic architectural bottlenecks across venue platform routing, Songkick pagination, missing venue calendars, and taste profile decoupling."
---

# Exploration: Systemic Pipeline Omissions — Keo, O2 Academy Brixton, & Spotify Taste Decoupling

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Core Question:** *Why was Keo on tour missing from the Live Curator digest despite being in Elliott's playlists? Is this a one-off bug or a systemic failure across data collection and taste matching?*

---

## 1. Executive Summary

The user's intuition was **100% correct**: the omission of **Keo** is the direct result of **four interconnected systemic failures** in the architecture, rather than an isolated glitch:

1. **Silent Dropping of Multi-Platform Venues (`platform: "both"`):** In [`config/venues.yaml`](file:///Users/elliottcallender/Downloads/Live%20Curator/config/venues.yaml), venues like `O2 Academy Brixton`, `Alexandra Palace`, and `Troxy` were assigned `platform: "both"`. In [`main.py`](file:///Users/elliottcallender/Downloads/Live%20Curator/main.py#L161-L182), the ingestion routing specifically did:
   ```python
   dice_venues = [v for v in target_venues if v.platform == "dice"]
   tm_venues = [v for v in target_venues if v.platform == "ticketmaster"]
   ```
   Because `platform == "both"`, these marquee venues matched neither category and were **silently discarded from event scraping**.
2. **Missing Songkick Integration on Mid-Size Landmarks:** O2 Academy Brixton is heavily covered by Songkick (`https://www.songkick.com/venues/17522-o2-academy-brixton/calendar`), but was missing `songkick_url` in [`config/venues.yaml`](file:///Users/elliottcallender/Downloads/Live%20Curator/config/venues.yaml).
3. **Songkick Single-Page Truncation:** Even when a venue had a `songkick_url`, the [`SongkickEngine`](file:///Users/elliottcallender/Downloads/Live%20Curator/src/ingestion/songkick_engine.py) only scraped the root overview page (which limits to ~9-10 immediate shows) without appending `/calendar` or paginating. Brixton Academy currently has **76+ future concerts** (50 on page 1 of `/calendar`, and 26 on page 2). **Keo @ O2 Academy Brixton (Fri 12 Mar 2027)** sits on `/calendar?page=2`, so any single-page scraper inevitably misses upcoming tours.
4. **Decoupling of Live Spotify OAuth from Seed/Build Pipeline:** Both Elliott and Chloe possess active, working OAuth refresh tokens in `.env` (Elliott has **538 playlist artists** including `keo`, and Chloe has **815 playlist artists**). However, [`scripts/build_pages.py`](file:///Users/elliottcallender/Downloads/Live%20Curator/scripts/build_pages.py#L127) only reads from [`data/seed_tastes.json`](file:///Users/elliottcallender/Downloads/Live%20Curator/data/seed_tastes.json), which held an obsolete 32-artist mock dataset because live tastes were never flushed into the repository's static seed.

---

## 2. Scope & Time-box

- **Time-box:** 45 minutes
- **Success Criteria:**
  1. Determine where Keo is performing in London and verify exact concert metadata.
  2. Inspect live Spotify libraries for both Elliott and Chloe to verify whether Keo is present.
  3. Identify every systemic defect in the data harvesting and taste-matching pipeline that caused this omission.
  4. Formulate an actionable plan to resolve the root causes across all venues and artists.

---

## 3. Best Practices & Industry Standards

### 3.1 Concert Discovery Aggregation
- **Multi-Platform Fallback:** Venues in major metropolitan hubs rarely adhere to a single ticketing provider. An O2 Academy hosts events ticketed across Ticketmaster, Live Nation, DICE, and See Tickets. Platforms like Songkick or Bandsintown serve as the industry standard aggregation layer because they normalize multi-vendor schedules.
- **Full Horizon Pagination:** Tour announcements for major artists span 6 to 18 months ahead. Limiting scrapers to the first 10-20 items or omitting pagination systematically filters out all medium/long-range tour dates. Venues with active concert calendars require scraping the full `/calendar` trajectory.

### 3.2 Dual-Tier Taste Profile Persistence
- **CI/CD vs Local Runtime:** GitHub Actions runs without access to personal local `.env` OAuth credentials. When static builds run on GitHub Pages, they must rely on committed state.
- **Export On Sync Pattern:** Whenever `main.py` runs with live Spotify credentials, it should atomically persist the harvested direct, playlist, and top artists into `data/seed_tastes.json`. This ensures both offline runs and GitHub Actions static builds reflect the user's authentic library.

---

## 4. Multi-Order Systematic Analysis

### Direct Effects (1st Order)
- Keo @ O2 Academy Brixton is scraped and accurately matched to Elliott's tastes into Tier 1 (`👨‍💻 In Elliott's Playlists`).
- Hundreds of other missing shows at O2 Academy Brixton, Alexandra Palace, and Troxy become visible in the curator.

### Ripple Effects (2nd to 4th Order)
- **2nd Order:** Expanding O2 Academy Brixton, Alexandra Palace, Troxy, and paginated Songkick venues will increase the total harvested event catalogue from ~396 to over 600-800 events.
- **3rd Order:** Tier 1 and Tier 2 match counts will naturally grow as Elliott and Chloe's real combined library (>1,200 unique artists) is matched against the broader concert catalog.
- **4th Order:** The system evolves from an East London club-focused preview into a truly comprehensive London-wide live curator spanning indie basements to iconic concert halls.

### Stakeholder Impact Matrix
| Stakeholder | Potential Impact | Severity |
|-------------|-----------------|----------|
| **Elliott & Chloe** | Will see concerts for bands they actually listen to (like Keo) across major London venues. | High |
| **Pipeline Scrapers** | Paginated requests to Songkick require polite rate limiting (1.5-2s delays) to prevent 429 rate limiting. | Medium |
| **GitHub Pages** | Static index size will increase slightly (~2MB -> ~3MB), fully within web performance budgets. | Low |

---

## 5. Empirical Evidence

### 5.1 Verifying Keo in Elliott's Live Spotify Library
Running an authenticated query using Elliott's live refresh token from `.env`:
```python
# Live Spotify Query
Saved artists count: 0
Top artists count: 84
Playlist artists count: 538
Keo matches in Elliott live profile: ['keo']
```
*Result:* `keo` is confirmed present in Elliott's live Spotify playlist library.

### 5.2 Verifying Keo @ O2 Academy Brixton on Songkick
Songkick concert JSON-LD record:
```json
{
  "@type": "MusicEvent",
  "name": "Keo @ O2 Academy Brixton",
  "url": "https://www.songkick.com/concerts/43393372-keo-at-o2-academy-brixton",
  "startDate": "2027-03-12T19:00:00",
  "location": {
    "name": "O2 Academy Brixton",
    "streetAddress": "211 Stockwell Road",
    "postalCode": "SW9 9SL"
  },
  "performer": [
    {
      "@type": "MusicGroup",
      "name": "Keo"
    }
  ]
}
```
*Result:* Keo is confirmed performing at O2 Academy Brixton on Friday, 12 March 2027.

### 5.3 Verifying Songkick Pagination
- `https://www.songkick.com/venues/17522-o2-academy-brixton` (Overview page) -> Only shows 9 events.
- `https://www.songkick.com/venues/17522-o2-academy-brixton/calendar` (Page 1) -> 50 events (Nov 2026 - Mar 5, 2027).
- `https://www.songkick.com/venues/17522-o2-academy-brixton/calendar?page=2` (Page 2) -> 26 events (Mar 7, 2027 - Jun 2027), including:
  ```text
  2027-03-12T19:00:00 - Keo @ O2 Academy Brixton
  ```

---

## 6. Systemic Defect Analysis

### Defect 1: Platform Routing Logic in `main.py`
```python
# BROKEN LOGIC in main.py:
dice_venues = [v for v in target_venues if v.platform == "dice"]
tm_venues = [v for v in target_venues if v.platform == "ticketmaster"]
```
When `v.platform == "both"`, it is excluded by both checks.  
**Fix:**
```python
dice_venues = [v for v in target_venues if v.platform in ("dice", "both")]
tm_venues = [v for v in target_venues if v.platform in ("ticketmaster", "both")]
```
Additionally, allow venues to declare `songkick_url` regardless of platform so keyless Songkick scraping is always leveraged if available.

### Defect 2: Songkick Engine Missing `/calendar` & Pagination
`SongkickEngine.fetch_venue_events(venue)` currently queries only `venue.songkick_url`.  
**Fix:**
- Normalise the URL to ensure it targets `/calendar`.
- Loop through `?page=1`, `?page=2`, etc., until no further events are returned (with polite sleep and a safety cap of 5 pages).

### Defect 3: Taste Syncing to Seed File
Currently, `data/seed_tastes.json` is static and holds only 32 mock artists.  
**Fix:**
- Provide a dedicated sync script (`scripts/sync_spotify_tastes.py`) or trigger it on every `main.py` execution to export both users' full live libraries (top, saved, and playlist artists) directly into `data/seed_tastes.json`.
- Commit the comprehensive `data/seed_tastes.json` so GitHub Pages static builds match against all ~1,200 real artists.

### Defect 4: Venue Configuration Updates
In `config/venues.yaml`:
- Add `songkick_url: "https://www.songkick.com/venues/17522-o2-academy-brixton"` to `O2 Academy Brixton`.
- Add active Songkick URLs for other major multi-platform venues (e.g. Troxy, Alexandra Palace).

---

## 7. Decision Gate & Next Steps

**Gate Decision:** **Proceed to `/plan`**

### Plan Objectives:
1. Fix venue platform routing in `main.py` so `platform: "both"` venues are properly scraped.
2. Upgrade `SongkickEngine` to scrape the `/calendar` endpoint with multi-page traversal (up to 5 pages per venue).
3. Update `config/venues.yaml` with Songkick URLs for `O2 Academy Brixton`, `Alexandra Palace`, and `Troxy`.
4. Ingest live Spotify taste profiles for Elliott & Chloe, populating all 538+ playlist artists (including `keo`) into `data/seed_tastes.json`.
5. Run the harvester, regenerate static distribution (`scripts/build_pages.py`), verify that Keo appears in Tier 1, and deploy to GitHub Pages.
