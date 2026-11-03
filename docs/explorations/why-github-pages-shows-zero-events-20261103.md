---
title: "Exploration: Root Cause of Zero Events on GitHub Pages Deployment"
date: "2026-11-03"
status: "completed"
tags:
  - exploration
  - github-actions
  - gitignore
  - data-persistence
  - github-pages
summary: "Investigation into why GitHub Pages displays 0 shows visible despite local database having 33 events. Identifies .gitignore exclusion of SQLite cache from GitHub Actions CI runner."
---

# Exploration: Root Cause of Zero Events on GitHub Pages Deployment

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Investigation Question:** *Why does the deployed GitHub Pages site show '0 upcoming events' and '0 shows visible' even after pushing commits?*

---

## 1. Executive Summary

The investigation revealed the **primary root cause**:
The local event cache resides in `data/cache/digest_history.sqlite`. However, `.gitignore` explicitly excludes all SQLite files:
```gitignore
data/cache/*.sqlite
data/cache/*.db
```
Because `data/cache/digest_history.sqlite` is never committed to Git, when the **GitHub Actions CI/CD runner** runs `scripts/build_pages.py` in the cloud:
1. `digest_history.sqlite` does not exist on the Ubuntu runner.
2. `scripts/build_pages.py` falls back to an empty list `events = []`.
3. It overwrites `public/index.html` with an empty **0-event digest**.
4. The empty artifact is deployed to GitHub Pages, wiping out all shows.

Additionally:
- When viewing "All Shows", empty sections (`Tier 1` and `Tier 2`) displayed dashed placeholder warning boxes at the top of the feed even when other shows were present below.

---

## 2. Evidence & Verification

1. **Checking `.gitignore`:**
   ```gitignore
   Line 16: data/cache/*.sqlite
   Line 17: data/cache/*.db
   ```
2. **Checking Git Tracking:**
   `git ls-files data/` returns zero files. The database that holds all 33 curated shows exists ONLY on Elliott's local machine, never on GitHub.
3. **Checking GitHub Actions Workflow:**
   In `.github/workflows/deploy-pages.yml`:
   ```yaml
   - name: Build static pages
     run: python3 scripts/build_pages.py
   ```
   On every push, GitHub Actions runs `build_pages.py` on a clean virtual machine with no SQLite database, generating a 0-event site.

---

## 3. Architecture Solution

### 1. Track Event Data via Git-Friendly JSON (`data/seed_events.json`)
- Export all curated events from `digest_history.sqlite` into `data/seed_events.json`.
- Unlike binary SQLite files, JSON is text-based, version-controllable, diffable, and tracked by Git.
- Update `scripts/build_pages.py` to load from `data/seed_events.json` when running in CI or when SQLite is unavailable.

### 2. Auto-Sync on Every Local Run
- Update `main.py` and `build_pages.py` to auto-export discovered events to `data/seed_events.json`.
- Whenever new events are scraped locally, `seed_events.json` updates and commits with the repo.

### 3. Hide Empty Placeholders in "All Shows" View
- When `currentTier === 'all'`, if a section contains no `.event-card` elements (e.g. empty Tier 1 or Tier 2), set `display: none` so empty dashed alert boxes do not push real events off-screen.

---

## 4. Multi-Order Impact Analysis

- **1st Order:** GitHub Actions runner immediately has access to all curated events from `data/seed_events.json`. The generated GitHub Pages site will display all shows.
- **2nd Order:** No external database dependencies needed for the GitHub Actions runner.
- **3rd Order:** Future contributors or clones immediately have a working static catalog out of the box.

---

## 5. Decision Gate

- **Verdict:** Proceed to implementation immediately.
- **Action Items:**
  1. Export `data/cache/digest_history.sqlite` to `data/seed_events.json`.
  2. Update `scripts/build_pages.py` to consume `data/seed_events.json`.
  3. Update `templates/digest.html` to hide empty tier boxes in "All Shows" mode.
  4. Run `build_pages.py`, commit `data/seed_events.json`, `public/`, and `docs/`.
