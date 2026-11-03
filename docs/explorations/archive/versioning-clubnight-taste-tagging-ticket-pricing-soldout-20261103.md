---
title: "Exploration: Version Bumping, Club Night Taste Matching, & Ticket Price/Sold-Out Ingestion"
date: "2026-11-03"
exploration_type: "investigation"
component: "versioning-clubnights-and-ticketing"
status: "concluded"
time_box: "30m"
outcome: "proceed_to_plan"
last_referenced: "2026-11-03"
tags:
  - exploration
  - versioning
  - club-nights
  - genre-matching
  - ticket-prices
  - sold-out-status
summary: "Investigation into bumping version to v0.0.2, scanning Club Night titles and descriptions for user artists and preferred genres, and exhaustively persisting ticket prices and sold-out status across DICE, Songkick, and Ticketmaster."
---

# Exploration: Version Bumping, Club Night Taste Matching, & Ticket Price/Sold-Out Ingestion

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Core Questions:**
> 1. *Why has the displayed version remained at v0.0.1 instead of incrementing to v0.0.2?*  
> 2. *How can Club Night / DJ events scan titles and descriptions to flag artists or preferred genres that Elliott & Chloe like?*  
> 3. *Why are ticket prices and sold-out statuses missing from the web app, and how can they be captured and displayed across all ticketing platforms?*

---

## 1. Executive Summary

This exploration investigates three distinct user enhancements:
1. **Semantic Versioning Drift:** `src/__version__.py` and `src/core/models.py` still define `__version__ = "0.0.1"`. While `scripts/bump_version.py` exists, automated releases and static page generation never invoked version bumping during feature additions. The version should be bumped to `v0.0.2` (or `v0.1.0`) and wired into build generation.
2. **Club Night Taste Intelligence:** Currently, events in Tier 4 (*Club Nights & DJs*) are assigned generic heuristic labels (e.g. `Late Night Party (≥22:00)` or `Club / DJ Night`). However, London club nights frequently specify artist tributes and genre themes in their descriptions (e.g. *"Playing the best of Charli XCX, Arctic Monkeys, The Cure, Nu-Disco, and Post-Punk"*). By introducing a description scanner in `TierClassifier`, club nights that feature Elliott's or Chloe's favorite artists or preferred genres will be highlighted with dedicated badges (`🎧 Plays Elliott's Favorite: Arctic Monkeys` or `🎧 Genre: Post-Punk, Nu-Disco`).
3. **Ticket Pricing & Sold-Out Availability Disconnect:**
   - **Root Cause of Missing Prices:** In `scripts/build_pages.py` and SQLite `seen_events` table, `price_str` and `is_sold_out` columns were omitted from the SQLite schema and seed serialization query (`SELECT event_id, title, venue_name, venue_area, start_time, ticket_url, platform FROM seen_events`). Consequently, even when DICE or Songkick extracted prices during scraping, they were dropped during cache persistence.
   - **Sold-Out Availability:** Songkick exposes `offers[].availability` (`LimitedAvailability`, `SoldOut`, `InStock`) and `highPrice`/`lowPrice`. DICE exposes `price.amount` and status (`sold-out`, `waiting-list`). Ticketmaster exposes `priceRanges` and `dates.status.code`. By adding `price_str` and `is_sold_out` to SQLite, the seed files, and the HTML template, every event will display a real price and an unmistakable `🚫 SOLD OUT` or `⏳ WAITING LIST` badge.

---

## 2. Scope & Time-box

- **Time-box:** 30 minutes
- **Success Criteria:**
  1. Audit version specification across `src/__version__.py`, `src/core/models.py`, `templates/digest.html`, and `venues.html`.
  2. Design an efficient text-scanning algorithm for club night descriptions against both users' 1,200+ artists and configured genre keywords.
  3. Formulate the schema migration and extraction logic for ticket prices and sold-out flags across DICE, Songkick, and Ticketmaster.

---

## 3. Findings & Technical Analysis

### 3.1 Task 1: Version Bumping
- **Current State:**
  - `src/__version__.py`: `__version__ = "0.0.1"`
  - `src/core/models.py`: `version: str = "0.0.1"`
  - `templates/digest.html`: `LIVE CURATOR // LONDON • v{{ version or '0.0.1' }}`
  - `venues.html`: hardcoded `v0.0.1`
- **Solution:**
  - Bump `src/__version__.py` to `"0.0.2"`.
  - Update `src/core/models.py` default to `"0.0.2"`.
  - Ensure `scripts/build_pages.py` injects `__version__` into both `index.html` and `venues.html`.

### 3.2 Task 2: Club Night Taste & Genre Flagging
- **Current State:**
  Club nights matching late hours or DJ keywords get a static description: `"Late Night Party (≥22:00)"` or `"Club / DJ Night"`. Any user affinity is completely invisible.
- **Proposed Solution:**
  1. In `config/tastes.yaml`, add configured preferred genres for Elliott and Chloe (e.g. `indie rock`, `post-punk`, `nu-disco`, `electronic`, `techno`, `house`, `shoegaze`, `synthpop`, `new wave`, `hyperpop`).
  2. In `TierClassifier._check_club_night_taste_matches(event)`:
     - Combine `event.title` and `event.description` into a searchable text block.
     - Scan for occurrences of any artist in Elliott's or Chloe's direct library (using word-boundary regex for exact matching to prevent partial false positives on short names).
     - Scan for preferred genre keywords.
     - Attach rationales:
       - `MatchRationale(user="Elliott", description="🎧 Features Elliott's artist: {artist}")`
       - `MatchRationale(user="Chloe", description="🎧 Features Chloe's artist: {artist}")`
       - `MatchRationale(user="Mutual", description="🎧 Features your mutual artist: {artist}")`
       - `MatchRationale(user=None, description="🎧 Genre: {genre}")`
  3. In `templates/digest.html`:
     Render these badges with distinctive styling on the club night cards.

### 3.3 Task 3: Ticket Prices & Sold-Out Ingestion
- **Current Disconnect:**
  1. `data/cache/digest_history.sqlite` table `seen_events` lacks `price_str` and `is_sold_out` columns.
  2. `scripts/build_pages.py` loads from SQLite without querying `price_str` or `is_sold_out`.
  3. `data/seed_events.json` has `price_str: null` and `is_sold_out: false`.
- **Extraction Capabilities across Platforms:**
  - **DICE (`DiceScraper`):**
    - Price: `event_data.get("price", {}).get("amount")` (e.g. `1200` -> `£12.00`).
    - Sold-out: `event_data.get("status") in ["sold-out", "off-sale"]` or `event_data.get("waiting_list_enabled") == True`.
  - **Songkick (`SongkickEngine`):**
    - Price: In Schema.org JSON-LD `offers`:
      - Single offer: `offer.get("price")` and `priceCurrency`.
      - AggregateOffer: `lowPrice` and `highPrice` (e.g. `From £32.50` or `£32.50 – £41.33`).
    - Sold-out: `offer.get("availability")` containing `"SoldOut"` or `"LimitedAvailability"`, or title containing `"(Sold Out)"` or `"Sold Out"`.
  - **Ticketmaster (`TicketmasterEngine`):**
    - Price: `priceRanges` -> `min` and `max` (e.g. `£45 - £120`).
    - Sold-out: `dates.status.code in ["offsale", "cancelled", "soldout"]`.
- **UI Display in `templates/digest.html`:**
  - If `event.is_sold_out`:
    Render a bold red pill: `🚫 SOLD OUT` or `⏳ WAITING LIST`.
    Disable or alter the CTA button: `"Sold Out (Join Waiting List) →"`.
  - If `event.price_str`:
    Render a slate/emerald price pill: `£15.00` or `Free`.

---

## 4. Multi-Order Systematic Analysis

### Direct Effects (1st Order)
- Displayed app version increments to `v0.0.2` across web app header and venue control panel.
- Club night attendees immediately spot DJ nights playing their favorite artists (e.g. Charli XCX or Arctic Monkeys club nights) and genres.
- Users immediately see which concerts have ticket costs and whether high-demand shows (like Keo at Brixton) are sold out.

### Ripple Effects (2nd to 4th Order)
- **2nd Order:** Users avoid wasted clicks navigating to sold-out ticketing links.
- **3rd Order:** Club night engagement increases significantly because club listings are filtered by musical relevance rather than being a generic wall of nightlife.
- **4th Order:** The SQLite database schema becomes a durable, rich event repository retaining pricing trends and availability history over time.

---

## 5. Decision Gate & Next Steps

**Gate Decision:** **Proceed to `/plan`**

### Plan Execution Sequence:
1. Bump version to `v0.0.2` in `src/__version__.py`, `src/core/models.py`, and templates.
2. Extend `seen_events` SQLite schema and `data/seed_events.json` to store `price_str` and `is_sold_out`.
3. Enhance `SongkickEngine` and `DiceScraper` to extract `is_sold_out` and format `AggregateOffer` prices (`lowPrice` – `highPrice`).
4. Implement Club Night description scanning for user artists and preferred genres in `TierClassifier`.
5. Update `templates/digest.html` to render sold-out badges, price pills, and club night taste badges.
6. Rebuild static distribution, test, and deploy to GitHub Pages.
