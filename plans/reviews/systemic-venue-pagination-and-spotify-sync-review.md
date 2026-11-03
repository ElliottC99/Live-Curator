# Plan Review: Systemic Venue Pagination, Multi-Platform Routing & Comprehensive Spotify Taste Sync

> **Review Date:** 2026-11-03  
> **Workflow:** `/plan-review`  
> **Target Plan:** [`plans/systemic-venue-pagination-and-spotify-sync.md`](file:///Users/elliottcallender/Downloads/Live%20Curator/plans/systemic-venue-pagination-and-spotify-sync.md)  
> **Reviewer:** Antigravity Engineering Agent  
> **Verdict:** **Approved (Ready for `/work`)**

---

## 1. Executive Assessment

The plan directly targets the root causes identified in [`docs/explorations/systemic-pipeline-omissions-keo-and-artist-harvesting-20261103.md`](file:///Users/elliottcallender/Downloads/Live%20Curator/docs/explorations/systemic-pipeline-omissions-keo-and-artist-harvesting-20261103.md). It addresses:
1. Multi-platform routing in `main.py` where `platform: "both"` silently dropped venues like O2 Academy Brixton, Troxy, and Alexandra Palace.
2. Songkick scraper single-page truncation by targeting `/calendar` and paginating pages 1–3.
3. Marquee venue coverage in `config/venues.yaml`.
4. Taste synchronization bridging live Spotify OAuth tokens and versioned seed data for GitHub Actions.

---

## 2. Dynamic Monthly Refresh Verification (User Clarification)

### *Will this be refreshed each month before the digest is sent?*

**YES — with architectural guarantees across both delivery modes:**

```
[Monthly Email Digest via `main.py`]
  1. At session/cron start, Step 1/5 runs:
     `spotify_engine.get_combined_taste_profile()`
  2. Queries Spotify OAuth API live for:
     - Liked Songs (Saved Tracks)
     - Top Artists (rolling short/medium/long term)
     - Active Playlists
  3. Automatically updates `data/seed_tastes.json` on disk with any new artists.
  4. Classifies upcoming events against the FRESH taste profile.
  5. Renders & dispatches the monthly email digest to Elliott & Chloe.

[GitHub Pages Web App Deployment]
  - Because GitHub Actions CI runs in a headless environment without user credentials,
    it reads from `data/seed_tastes.json`.
  - By establishing `scripts/sync_spotify_tastes.py`, every run of the sync or monthly
    dispatch keeps `data/seed_tastes.json` updated with your live libraries.
```

**Recommendation added to implementation:**
Ensure `scripts/sync_spotify_tastes.py` has a dedicated test and can be triggered on demand or as a pre-build hook so the web app and email digest are always in complete lockstep.

---

## 3. Completeness & Gap Analysis

### 3.1 Rate Limiting & Exhaustive Calendar Traversal
- **Review Finding & Amendment:** A fixed page cap (e.g. 3 pages) would leave late-announced concerts or venues with 5+ pages truncated.
- **Enhanced Design:** 
  - `SongkickEngine` now follows Songkick's `<a rel="next">` DOM tag dynamically until it is `None` (exhausting all listings to the very end of each venue's schedule).
  - Employs duplicate signature checking (to stop if Songkick loops back to root).
  - Safety circuit-breaker capped at 20 pages per venue.
  - Strict polite delay of 1.2–1.5s between page fetches to protect against 429 rate limits.

### 3.2 Spotify Ingestion 403 / Forbidden Playlists
- **Review Finding:** During exploration, one playlist returned `HTTP 403 Forbidden` (`playlists/01HJSqKR3LnvYJ0O2qXXob/items` - private or collaborative playlist without explicit read scope).
- **Mitigation:** In `SpotifyEngine._fetch_playlist_and_discovery_artists`, ensure each playlist fetch is wrapped in a granular `try...except` block so one private or restricted playlist does not abort the remaining public playlists.

### 3.3 Event Deduplication & Cumulative Multi-Tagging
- **Review Finding & Amendment:** 
  1. `TierClassifier` short-circuited with `elif` in `_check_user_direct_match` and returned early in `classify_event` as soon as Tier 1 matched. This artificially caused multi-affinity artists like **Blondshell** to display only one single tag, omitting co-occurring tags and critical press review badges (e.g. 5★ review in The Guardian).
  2. The classifier has been redesigned to be **cumulative**: an event card will proudly display ALL earned badges:
     - `🔥 Both of You • 🔥 MUTUAL MATCH`
     - Personal user badges (`Liked Songs`, `Playlists`, `Top Artists`)
     - Publication review stars (`5★ review in The Guardian`, `4★ review in DIY`, etc.)
  3. `main.py` and `scripts/build_pages.py` deduplicate cross-platform events on composite key `(normalized_headliner, date, venue_name)`.

---

## 4. Acceptance Criteria Validation

- [x] Clear, measurable criteria defined.
- [x] Test coverage planned (`test_songkick_engine.py`, `test_spotify_engine.py`, `test_main_pipeline.py`).
- [x] End-to-end verification via `Keo @ O2 Academy Brixton` in Tier 1.
- [x] No breaking schema or UI regressions.

---

## 5. Review Verdict

**VERDICT: APPROVED ✓**

Proceed immediately to **/work** to execute the plan.
