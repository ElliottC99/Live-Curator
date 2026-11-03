# Plan Review: Rolling Future Horizon, Delta Highlighting & In-App Venue Manager

> Plan: [plans/future-horizon-diffing-and-venue-management.md](../future-horizon-diffing-and-venue-management.md)  
> Review Date: 2026-11-03  
> Reviewer: Antigravity Code Review Agent  
> Verdict: **Ready for Implementation (Approved ✓)**

---

## 1. Executive Summary
The implementation plan directly and completely solves the user's requirements:
1. Expanding beyond single calendar months to a rolling, open-ended future horizon ($\text{date} \ge \text{today}$).
2. Statefully diffing discovered events against historical runs via persistent SQLite storage to highlight `[🔥 NEW ANNOUNCEMENT]` events in email subjects, card badges, and dedicated tab pills.
3. Providing an in-app local web UI (`main.py --ui`) allowing point-and-click neighbourhood reassignments, venue additions, and active toggling with atomic `config/venues.yaml` updates.

---

## 2. Quality & Completeness Checklist

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| **Requirements** | Rolling future horizon | ✅ PASS | Retains all upcoming events ($\text{date} \ge \text{today}$) without monthly cutoff |
| | Delta / New Announcement Diffing | ✅ PASS | SQLite database `digest_history.sqlite` with canonical event fingerprint |
| | In-App Venue & Neighbourhood Manager | ✅ PASS | Point-and-click UI via standard library `http.server` (zero extra dependencies) |
| **Research** | Codebase Patterns | ✅ PASS | Follows SQLite pattern from `review_parser.py` and `Venue`/`Event` models |
| | Best Practices | ✅ PASS | Cites newsletter and event discovery patterns (urgency, dedicated new-drop tab) |
| **Architecture** | Atomic persistence | ✅ PASS | Uses safe atomic file write to prevent YAML corruption |
| | Fallback handling | ✅ PASS | Gracefully handles empty baseline history and port conflicts |
| **Testing** | Automated tests | ✅ PASS | Unit tests for `EventDiffEngine` and `VenueManager` (60+ total tests) |

---

## 3. Deep Analysis & Edge Case Mitigations

1. **Initial Baseline Run Handling:**
   - *Consideration:* On the very first run of `EventDiffEngine`, every existing event would be technically "new" to the database.
   - *Mitigation:* `EventDiffEngine` should distinguish between the initial baseline seeding (where all events are recorded as the baseline) and subsequent runs where events discovered after the baseline are flagged as `is_new_announcement = True`. Alternatively, if it is the first run, it can flag all as newly discovered or baseline.
2. **Duplicate Detection across Scrapers:**
   - *Consideration:* If a venue is listed on both DICE and Ticketmaster, or date strings vary slightly.
   - *Mitigation:* Generate canonical fingerprint based on normalized title + normalized venue name + event date (`YYYY-MM-DD`).
3. **YAML Comment & Structure Preservation:**
   - *Consideration:* Writing to `config/venues.yaml` should preserve venue schema fields (`dice_slug`, `tm_venue_id`, `tm_keyword`, `area`, `address`, `genre_focus`).
   - *Mitigation:* Serialize via PyYAML with standard formatting, writing through a temporary file to avoid partial write failures.
4. **Port Availability for Local UI:**
   - *Consideration:* Port 8765 might be occupied.
   - *Mitigation:* Bind with fallback to auto-find next available port if 8765 is in use.

---

## 4. Final Recommendation & Verdict

- **Verdict:** **Approved ✓**
- **Action:** Update plan status to `Approved ✓` and proceed directly to execution via `/work`.
