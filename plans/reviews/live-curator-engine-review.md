# Plan Review: Live Curator Engine

> Date: 2026-11-03  
> Plan: [plans/live-curator-engine.md](../live-curator-engine.md)  
> Reviewer: Compound Engineering Quality Gate  
> Verdict: **APPROVED (Ready for Execution ✓)**

---

## Executive Summary

The plan for the **Live Curator Engine** has undergone comprehensive quality review against system requirements, compound patterns, architectural decisions (ADR-001), and multi-order edge case analysis. 

The plan demonstrates exceptional depth, directly addressing the late-2024 Spotify recommendations API shutdown, Cloudflare evasion via Playwright stealth and JSON-LD schema extraction, and dual-user OAuth token lifecycles for headless local execution. Minor implementation enhancements identified during review have been documented below and incorporated into the execution criteria.

---

## Review Checklist & Verification

### 1. Completeness & Grounding
- [x] **Compound Solutions Referenced:** Prior exploration (`docs/explorations/live-curator-engine-20261103.md`) and architectural decision record (`docs/decisions/001-engine-architecture-and-data-ingestion.md`) are explicitly referenced and tracked.
- [x] **Problem Statement:** Clear, specific, and motivated by practical automation of personal cultural curation.
- [x] **Measurable Success Criteria:** Clear definition of done covering 9 venues, dual Spotify profiles, 7 publications, 3-tier categorization, responsive HTML email digest, and local macOS cron execution.
- [x] **Modular Architecture:** Adheres strictly to single-responsibility modules (`dice_scraper.py`, `spotify_engine.py`, `review_parser.py`, `tier_classifier.py`, `digest_mailer.py`).

### 2. Deep Gap Analysis & Edge Cases

| Dimension | Risk / Edge Case | Plan Mitigation | Review Recommendation |
|-----------|------------------|-----------------|-----------------------|
| **DICE Scraping** | Venues with >10 events in a month require scrolling or "Load More" clicks | Plan includes scrolling | Explicitly implement a `scroll_and_load_all()` loop that terminates once event dates exceed the current month. |
| **Date Boundaries** | Scraper runs on the 1st of month; needs to only include events for that calendar month | Monthly date filtering | Add `Event.date` filtering utility comparing `event.date.year == current.year and event.date.month == current.month`. |
| **Act Normalization** | Complex co-bills like `"An Evening with Artist A"`, `"Artist A vs Artist B"`, `"Artist A feat. Artist B"` | `normalizer.py` splits `+`, `w/`, `feat.` | Include `"vs"`, `"presents"`, and strip `"An Evening with"` prefixes during normalization. |
| **Review Normalization** | Different scoring scales (5-star vs 10-point vs 100%) | Defined thresholds: $4\star+$ or $7.5+$ | Standardize in `Review` model with `is_recommended: bool` based on: $\text{score} \ge 4.0/5$ or $\text{score} \ge 7.5/10$. |
| **Email Previews** | Testing email formatting without spamming inbox | `--preview-html` flag in `main.py` | Save output directly to `output/preview.html` and auto-generate plain-text fallback. |

### 3. Multi-Order Thinking
- **1st Order:** Elliott & Chloe receive a beautifully curated, monthly gig guide tailored to their specific tastes and UK critical reviews on the 1st of every month.
- **2nd Order:** External dependencies (DICE markup, publication RSS feeds, Spotify tokens) are decoupled with caching and schema.org JSON-LD to prevent systemic drift.
- **3rd Order:** `venues.yaml` external configuration makes expanding beyond Dalston (e.g., Camden, Peckham, Soho) or adding independent promoters a zero-code change.
- **4th Order:** Transforms passive gig discovery into an automated cultural pipeline.

---

## Actionable Enhancements for Implementation

1. **Phase 1 (Models & Normalizer):**
   - Add unit test fixtures covering complex billing patterns: `"Pond + Special Guests"`, `"Black Country, New Road w/ Ethan P. Flynn"`, `"An Evening with Lankum"`.
2. **Phase 2 (Scraper):**
   - Implement date filtering logic directly in the scraper to exclude past gigs and gigs outside the target month.
3. **Phase 6 (Delivery):**
   - Implement local HTML preview generation so `python main.py --dry-run --preview-html` opens the exact email in the default browser.

---

## Verdict & Transition

**Verdict: APPROVED (Ready for Execution ✓)**

The implementation plan is sound, robust, and verified.
Update plan status to `Approved ✓` and proceed immediately to **/work**.
