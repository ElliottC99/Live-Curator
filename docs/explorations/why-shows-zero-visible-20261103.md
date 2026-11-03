---
title: "Exploration: Root Cause Analysis of '0 Shows Visible' on Initial Load"
date: "2026-11-03"
status: "completed"
tags:
  - exploration
  - ui
  - github-pages
  - filtering
  - tier-cycling
summary: "Deep root cause investigation of why the Live Curator web digest displays '0 shows visible' on initial page load, and architectural design to guarantee immediate visibility of all curated events."
---

# Exploration: Root Cause Analysis of "0 Shows Visible" on Initial Load

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Investigation Question:** *Why does the Live Curator web application / digest display "0 shows visible" upon initial load, and what is the optimal pattern to ensure all curated shows are immediately visible?*

---

## 1. Executive Summary

When opening the Live Curator web app on GitHub Pages or locally, the top counter pill displays **`0 shows visible`**, and the content area presents an empty box reading *"No Tier 1 Direct Matches found for this month yet"*, despite **33+ curated shows** being fully loaded in the page DOM.

The investigation identified two interlocking root causes:
1. **Hardcoded Tier 1 Active Tab Default:** In `templates/digest.html`, `<a href="#tier-1" class="tab-btn btn-t1 active">` is statically hardcoded with the `active` class. When users view the public GitHub Pages site (where no personal Spotify OAuth session exists), `Tier 1: Direct Matches` naturally contains 0 items.
2. **Client-Side Initialization Fallback Flaw:** In `initInteractiveControls()`, if no URL hash exists and `newCount == 0` and `t1Count == 0`, the tier fallback logic fell into `switchTier('club')` or remained anchored to the hardcoded `active` Tier 1 tab. When filtering against `cardTier === 'tier1'`, the visible count computed to `0`, setting `#filter-count` to `0 shows visible`.
3. **Sandbox Dry-Run Artifact Drift:** An earlier test run executed inside a network-isolated sandbox produced an `output/preview.html` with 0 newly harvested events, which caused confusion if previewing that local file instead of `public/index.html`.

---

## 2. Deep Root-Cause Analysis

### Cause 1: Tier 1 Direct Match Pre-Selection
In `templates/digest.html`:
```html
<a href="#tier-1" class="tab-btn btn-t1 active" id="btn-tier1" onclick="switchTier('tier1'); return false;">
  🔥 Tier 1: Direct ({{ digest.tier_1_events|length }})
</a>
```
- Tier 1 represents **direct Spotify matches** (artists in Elliott or Chloe's Liked Songs, Top Artists, or Personal Playlists).
- On a public deployment like GitHub Pages, visitors do not have Elliott & Chloe's Spotify auth tokens. If a digest is generated without private Spotify credentials, `digest.tier_1_events` is `0`.
- Because `btn-t1 active` is baked into the initial HTML, the browser displays the Tier 1 container:
  ```html
  <div id="section-tier1" class="tier-section">
    <div style="...">No Tier 1 Direct Matches found for this month yet.</div>
  </div>
  ```
- All other 33+ shows located in Tier 3 (Comedy), Club Nights, and General Lineup are hidden inside non-active sections (`display: none`).

### Cause 2: Filter Counter Zeroing
In `applyFiltersAndSort()`:
```javascript
cards.forEach(function(card) {
  var cardTier = card.getAttribute('data-tier');
  if (currentTier === 'tier1') {
    matchTier = (cardTier === 'tier1');
  }
  if (matchTier) {
    visibleCount++;
  }
});
counter.textContent = visibleCount + ' shows visible';
```
When `currentTier` is `'tier1'` and there are 0 cards with `data-tier="tier1"`, `visibleCount = 0`. The counter dutifully reports `0 shows visible`.

### Cause 3: Hash Normalization Mismatch
In `templates/digest.html`, the button links use `href="#tier-1"` and `href="#tier-all"`, but `switchTier()` expects keys `'tier1'` and `'all'`. If a user visited a bookmarked URL with `#tier-1`, `hash.replace('#', '')` became `'tier-1'`, failing the strict equality check `hash === 'tier1'`.

---

## 3. Multi-Order Impact Analysis

### 1st Order (Immediate Impact)
- Any visitor to `https://elliottc99.github.io/Live-Curator/` immediately sees all curated shows (Tier 1, Tier 2, Comedy, Club Nights, and general lineups) without having to manually click around.
- The counter badge displays `33 shows visible` (or `600+ shows visible` on full scrape).

### 2nd Order (User Experience & Discovery)
- Users can still click `[🔥 Tier 1: Direct]`, `[🎭 Comedy]`, or `[🎧 Club Nights]` to isolate specific subsets, but the default landing state is welcoming, rich with content, and immediately useful.

### 3rd Order (Maintenance & Portability)
- Decouples public viewing from private Spotify authentication state. Whether viewing on mobile, desktop, local file preview, or GitHub Pages, the UI adapts gracefully.

---

## 4. Proposed Solution & Architecture

### Step 1: Default to "All Shows" When Tier 1 is Empty
In `templates/digest.html`:
- If `digest.tier_1_events` has items: Tier 1 is active.
- If `digest.tier_1_events` is empty: **`[📋 All Shows (N)]`** is active by default.
- In Jinja2:
  ```jinja2
  <a href="#tier-all" class="tab-btn btn-all {% if not digest.tier_1_events and not digest.new_announcements %}active{% endif %}" id="btn-all" onclick="switchTier('all'); return false;">
    📋 All Shows ({{ digest.total_events_scraped }})
  </a>
  <a href="#tier-1" class="tab-btn btn-t1 {% if digest.tier_1_events %}active{% endif %}" id="btn-tier1" onclick="switchTier('tier1'); return false;">
    🔥 Tier 1: Direct ({{ digest.tier_1_events|length }})
  </a>
  ```

### Step 2: Resilient Client-Side Tier Initialization
In `initInteractiveControls()`:
```javascript
var hash = window.location.hash.replace('#', '').toLowerCase().replace('-', '');
if (['new', 'tier1', 'tier2', 'tier3', 'club', 'all'].includes(hash)) {
  switchTier(hash);
} else if (newCount > 0) {
  switchTier('new');
} else if (t1Count > 0) {
  switchTier('tier1');
} else {
  switchTier('all'); // Show all shows immediately!
}
```

### Step 3: Hash Normalization
In `switchTier(tierKey)`:
- Support both `'tier1'` and `'tier-1'`, `'all'` and `'tier-all'`, `'new'` and `'tier-new'`.

### Step 4: Re-Run `build_pages.py` and Push
- Rebuild `public/index.html` and `docs/index.html`.
- Push to GitHub so GitHub Pages updates automatically.

---

## 5. Decision Gate

- **Verdict:** Proceed directly to execution via `/work` (small targeted fix, no extensive spec needed).
- **Files Affected:** `templates/digest.html`, `public/index.html`, `docs/index.html`.
