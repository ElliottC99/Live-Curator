---
id: "ADR-001"
title: "Live Curator Engine Architecture and Ingestion Strategy"
date: "2026-11-03"
status: "accepted"
tags: ["architecture", "dice-scraping", "spotify-api", "playwright", "email-digest"]
last_referenced: "2026-11-03"
---

# ADR-001: Live Curator Engine Architecture and Ingestion Strategy

## Status

Accepted

## Context

The Live Curator Engine automates monthly event discovery across 9 Dalston and East London music venues ticketed through Dice.fm, cross-referencing listings against Elliott and Chloe's combined music tastes and music press reviews to dispatch a curated 3-tier HTML email digest.

Key technical constraints and discoveries:
1. **Dice.fm Cloudflare Turnstile/WAF:** Standard HTTP clients are blocked with 403 Forbidden.
2. **Spotify API Deprecation (Nov 27, 2024):** Spotify deprecated `GET /v1/recommendations` and `GET /v1/artists/{id}/related-artists` for third-party developer apps in Development Mode.
3. **Multi-User Taste Profiling:** The engine needs to capture two independent accounts (Elliott & Chloe) without requiring recurring interactive logins on headless cron runs.
4. **Resilient Data Ingestion:** 7 British music publications need reliable scraping/parsing with score normalization.

## Decision

1. **Scraping Framework:** Use Python `playwright` with `playwright-stealth` in headless Chromium. Extract structured schema.org JSON-LD data (`<script type="application/ld+json">`) from DICE venue pages rather than brittle CSS selectors.
2. **Spotify Recommendations Fallback:** Instead of the deprecated `/v1/recommendations` endpoint:
   - Ingest each user's personalized **"Discover Weekly"** and **"Release Radar"** algorithmic playlists via `/v1/me/playlists` and `/v1/playlists/{id}/tracks`.
   - Ingest **Saved Tracks** (`/v1/me/tracks`) and **Top Artists** (`/v1/me/top/artists`).
   - Use high-rated reviews ($\ge 4\star$ or $\ge 7.5$) as the primary discovery driver as specified in Tier 2.
3. **Dual-User Headless OAuth:** Use a one-time interactive script (`scripts/auth_spotify.py`) to generate two long-lived refresh tokens stored in `.env`. On monthly runs, the engine requests fresh access tokens programmatically with zero human intervention.
4. **Review Aggregation & Caching:** Build a unified `ReviewAggregator` targeting The Guardian (API/RSS), AnyDecentMusic? (HTML table), and RSS feeds for DIY, Dork, The Line of Best Fit, NME, and Loud & Quiet. Persist reviews into `cache/reviews.sqlite` to prevent re-scraping and deduplicate entries.
5. **3-Tier Matching Engine:** Normalize artist strings (lowercase, unidecode, strip parentheticals, strip leading articles) and split co-billed acts (`+`, `w/`, `feat.`). Match against Tier 1 (direct taste), Tier 2 (discovery & reviews), and Tier 3 (comedy keywords).
6. **Dispatch & Scheduling:** Support standard Gmail SMTP with Google App Password (via Python standard library `smtplib`) and optional SendGrid API. Support macOS `cron` and provide a native `launchd` plist for sleep-resilient scheduling.

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| Raw `requests` / `httpx` for Dice | Lightweight, fast | Blocked by Cloudflare WAF/Turnstile (403) | Does not bypass anti-bot challenges |
| Third-party scraping proxy service (Apify / ScraperAPI) | No local browser overhead | Recurring monthly subscription cost, external dependency | Unnecessary for 9 monthly venue requests run locally |
| Calling deprecated Spotify `/v1/recommendations` | Directly matches original wording | Fails with 403 Forbidden since Nov 2024 API shutdown | Broken at Spotify platform level |
| Single-user Spotify configuration | Simpler OAuth setup | Misses partner Chloe's taste profile completely | Violates core user objective |

## Consequences

**Positive:**
- 100% automated local execution without subscription costs.
- Headless, sleep-safe operation on macOS.
- Immune to frontend CSS class renaming due to JSON-LD extraction.
- Fully adheres to Spotify's current API capabilities.

**Negative:**
- Requires Playwright Chromium browser binaries (~150MB) locally installed.
- Initial one-time OAuth authorization requires running a local browser setup script.

## Related

- Exploration: `docs/explorations/live-curator-engine-20261103.md`
- Plan: `plans/live-curator-engine.md`
