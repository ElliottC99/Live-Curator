---
title: "Exploration: Root Cause Analysis of Empty Tier 1 & Tier 2 in Static & Web Deployments"
date: "2026-11-03"
exploration_type: "investigation"
component: "classification-and-matching"
status: "concluded"
time_box: "30m"
outcome: "proceed_to_plan"
last_referenced: "2026-11-03"
tags:
  - exploration
  - tier1
  - tier2
  - spotify
  - reviews
  - classification
  - seed-data
summary: "Deep root cause investigation of why Tier 1 (Direct Matches) and Tier 2 (Discovery Matches) are empty on GitHub Pages and local page builds, identifying omitted classifier dependencies, missing seed datasets, and lack of offline taste profiles."
---

# Exploration: Why Tier 1 & Tier 2 Are Empty on GitHub Pages & Static Builds

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Question:** *Why are Tier 1 (Direct Matches) and Tier 2 (Discovery Matches) completely empty (0 events) in the deployed web digest, and what is the optimal architectural pattern to populate both tiers reliably on static hosting like GitHub Pages?*

---

## 1. Executive Summary

When visiting `https://elliottc99.github.io/Live-Curator/`, **Tier 1: Direct Matches (0)** and **Tier 2: Discovery Matches (0)** show 0 events, forcing all 392 scraped London events into either *Club Nights* or *Other Upcoming Shows*.

The investigation identified two separate root causes for each tier:

### For Tier 1 (Direct Matches: Elliott & Chloe's Spotify Library)
1. **Omitted Parameter in Static Page Builder:** In `scripts/build_pages.py`, the classifier is instantiated as `classifier = TierClassifier()` without passing any `taste_profile`.
2. **Missing Local OAuth Credentials:** In `.env`, `SPOTIFY_ELLIOTT_REFRESH_TOKEN` and `SPOTIFY_CHLOE_REFRESH_TOKEN` are empty strings. Even if `SpotifyEngine` were called, it yields empty artist sets.
3. **CI Execution Boundary:** GitHub Actions runs without access to local `.env` files or private Spotify user accounts. Because there was no committed taste profile seed (`data/seed_tastes.json` or `config/tastes.yaml`), the classifier in CI had zero artists to match against.

### For Tier 2 (Discovery Matches: Algorithmic Discovery & UK Music Press Reviews)
1. **Reviews Not Passed to Classifier in `build_pages.py`:** While `main.py` initializes `ReviewAggregator` and passes `recommended_review_artists` into `TierClassifier`, `scripts/build_pages.py` completely omitted this argument, so `self.recommended_review_artists` defaulted to an empty set (`set()`).
2. **Review Cache Ignored in Git:** `data/cache/reviews.sqlite` is in `.gitignore`. Even when local reviews exist, GitHub Actions runners do not have `reviews.sqlite` and thus cannot match against reviewed artists.
3. **Review Parser Scope:** The live review RSS feeds only contain recent articles (10–20 per publication). Without a persistent curated list of high-rated artists (Mercury Prize, Guardian 4/5★, DIY/Dork Class of 2025/2026), review matches were minimal.

---

## 2. Deep Root-Cause Trace

### 2.1 Code Flow in `scripts/build_pages.py`
In `scripts/build_pages.py`:
```python
# scripts/build_pages.py lines 118-124
events = load_events_from_history()
classifier = TierClassifier()  # <-- All taste and review arguments are None!
digest = classifier.build_digest(events, month_name=month_name, year=year)
```
In `src/processing/tier_classifier.py`:
```python
def classify_event(self, event: Event) -> Event:
    # Tier 1 requires self.taste_profile
    if self.taste_profile:
        tier_1_matches = ...
        if tier_1_matches:
            event.tier = TierCategory.TIER_1_DIRECT
            return event

    # Tier 2 requires self.taste_profile OR self.recommended_review_artists
    review_matches = self._check_review_matches(norm_acts)
    # self.recommended_review_artists was empty set()
```
Because `self.taste_profile` is `None` and `self.recommended_review_artists` is `set()`, every event bypasses Tier 1 and Tier 2, landing in Club Nights or Other.

### 2.2 Proof-of-Concept Verification
When we ran a diagnostic connecting `data/cache/reviews.sqlite` to `TierClassifier`:
```python
rdb = ReviewDatabase(Path('data/cache/reviews.sqlite'))
rec = rdb.get_recommended_artists()
classifier = TierClassifier(review_db=rdb, recommended_review_artists=rec)
digest = classifier.build_digest(events)
```
Events immediately began matching! (e.g. *Wasia Project* @ Roundhouse matched with a `4★ review in Dork`).

---

## 3. Best Practices & Multi-Order Analysis

### 3.1 Industry Standards for Hybrid Static/Authenticated Apps
- **Declarative Taste Profiles (Git-Tracked):**
  Static and headless deployments require an offline-first seed configuration. Relying exclusively on live OAuth refresh tokens creates a hard single point of failure in CI/CD.
  *Pattern:* Maintain a curated `config/tastes.yaml` or `data/seed_tastes.json` specifying Elliott & Chloe's favorite artists and genres, with an optional automated sync script when Spotify tokens are present.
- **Tracked Seed Review Database:**
  Similar to how `data/seed_events.json` solved the zero-shows bug on GitHub Actions, a version-controlled `data/seed_reviews.json` ensures that GitHub Actions has the full set of critically acclaimed UK artists without running scrapers on CI.
- **Client-Side Personalization:**
  In addition to static pre-matching, allowing the user to mark artists/events as "Favorite" or "Must-See" in the web UI (persisted to `localStorage`) bridges static hosting with personal tastes.

### 3.2 Multi-Order Consequences
- **1st Order:** Passing taste profiles and review seeds into `build_pages.py` populates Tier 1 and Tier 2 with dozens of highlighted shows.
- **2nd Order:** Visitors on GitHub Pages immediately see Tier 1 and Tier 2 badges (e.g. `👨‍💻 Elliott`, `👩‍🎨 Chloe`, `✨ 5★ Guardian Review`, `✨ 4★ Dork`).
- **3rd Order:** The default active view on the web app displays curated, high-priority shows first instead of generic unclassified events.
- **4th Order:** The application works robustly both offline/static (GitHub Pages) and in automated email pipeline mode with full Spotify API credentials.

---

## 4. Decision & Next Step

**Decision:** Proceed directly to `/plan` to implement:
1. Declarative taste profile configuration (`config/tastes.yaml` and `data/seed_tastes.json`) for Elliott & Chloe.
2. Version-controlled review seed dataset (`data/seed_reviews.json`) capturing high-rated reviews from Guardian, NME, DIY, Dork, and Loud & Quiet.
3. Updated `scripts/build_pages.py` and `TierClassifier` loading seed tastes and reviews during static builds.
4. UI enhancement: Interactive "Star / Add to My Tier 1" button on show cards persisted in `localStorage`.
