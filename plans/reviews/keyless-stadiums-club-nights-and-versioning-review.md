# Plan Review: Keyless Stadium Discovery, Club Night Categorization, GitHub Setup & Versioning

> Plan: [plans/keyless-stadiums-club-nights-and-versioning.md](../keyless-stadiums-club-nights-and-versioning.md)  
> Review Date: 2026-11-03  
> Reviewer: Antigravity Code Review Agent  
> Verdict: **Ready for Implementation (Approved ✓)**

---

## 1. Executive Summary
The implementation plan directly and thoroughly addresses all four requirements raised by the user:
1. **Keyless Stadium Discovery Engine:** Scrapes public Schema.org `MusicEvent` JSON-LD from Songkick venue pages (Wembley, Tottenham Hotspur Stadium, London Stadium, The O2 Arena, etc.), bypassing Ticketmaster Developer Portal 404s, login roadblocks, and API keys with 100% sports-free concert extraction.
2. **Club Nights as a 4th Category:** Separates late-night dance/electronic events (start time $\ge \text{22:00}$ or club keywords) into a dedicated `club_night_events` category and `[🎧 Club Nights & DJs]` tab pill, backed by a persistent SQLite memory (`data/cache/user_event_tags.sqlite`) so user tagging persists across runs.
3. **Dynamic Semantic Versioning (`v0.0.1`) & GitHub Setup:** Centralizes version in `src/__version__.py` ("0.0.1"), displays it in email digest, UI headers, and CLI banners, and provides `scripts/bump_version.py` and `scripts/setup_github.sh`.
4. **DICE Multi-Page Ingestion:** Implements automated Playwright scroll/pagination in `DiceScraper` to lift the 30-event Next.js SSR boundary for high-volume venues.

---

## 2. Quality & Completeness Checklist

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| **Requirements** | Keyless Stadium Ingestion | ✅ PASS | Songkick public Schema.org JSON-LD parser; zero API keys or accounts required |
| | Club Nights Separation & Memory | ✅ PASS | Dedicated category, start time $\ge \text{22:00}$ + keyword heuristic, SQLite tag persistence |
| | Semantic Versioning (`v0.0.1`) | ✅ PASS | `src/__version__.py` surfaced in all UI banners, CLI, and bump script |
| | GitHub Setup & Guidance | ✅ PASS | `scripts/setup_github.sh` automating remote addition and git push |
| | Multi-Page DICE Pagination | ✅ PASS | Playwright scroll loop to harvest all upcoming shows |
| **Research** | Codebase Patterns | ✅ PASS | Fits neatly into existing `BaseIngestionEngine`, `TierClassifier`, and `MonthlyDigest` models |
| | Best Practices | ✅ PASS | Adheres to ADR-001, ADR-002, and Schema.org `MusicEvent` specification |
| **Architecture** | Fallbacks & Robustness | ✅ PASS | Handles network blips gracefully in Songkick engine; falls back to SSR payload in DICE if Playwright is headless-only |
| | Data Integrity | ✅ PASS | SQLite tag table uses standard parameterized queries and unique event IDs |
| **Testing** | Automated Verification | ✅ PASS | Unit tests planned for Songkick engine, user tagging, and versioning (65+ total tests) |

---

## 3. Deep Analysis & Edge Case Mitigations

1. **Songkick Rate Limiting / Structure Changes:**
   - *Consideration:* Public scraping can encounter rate limits or missing JSON-LD scripts.
   - *Mitigation:* Cache responses via `requests_cache` or SQLite if needed, set realistic desktop User-Agent, and validate JSON-LD parse errors gracefully without failing the entire pipeline.
2. **Late-Night Live Gigs vs. Club Nights:**
   - *Consideration:* An occasional live band might headline late (e.g., 22:30 at Cafe OTO).
   - *Mitigation:* User tag SQLite engine allows the user to reclassify any event with one click, and that override takes precedence over automated heuristics on all future runs.
3. **Version Sync:**
   - *Consideration:* Version string getting out of sync between `pyproject.toml`, CLI, and HTML templates.
   - *Mitigation:* Single source of truth in `src/__version__.py`, read dynamically by `main.py`, `VenueManager`, and `digest.html`.
4. **GitHub Authentication for User:**
   - *Consideration:* Git push requires SSH keys or personal access token depending on the user's environment.
   - *Mitigation:* `scripts/setup_github.sh` checks `gh` CLI auth status or SSH configuration and provides explicit, copy-pasteable instructions.

---

## 4. Final Recommendation & Verdict

- **Verdict:** **Approved ✓**
- **Action:** Transition to `/work` and execute all five phases systematically.
