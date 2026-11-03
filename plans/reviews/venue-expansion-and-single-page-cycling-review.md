# Plan Review: Venue Expansion, Ticketmaster Stadium Discovery & Single-Page Tier Cycling

> Review Date: 2026-11-03  
> Plan: [plans/venue-expansion-and-single-page-cycling.md](../venue-expansion-and-single-page-cycling.md)  
> Architectural Decision: [ADR-002: Ticketmaster Discovery and Single-Page Tier Cycling](../../docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)  
> Verdict: **Ready for Execution (Approved ✓)**

---

## 1. Completeness & Quality Audit

### Problem Statement & Requirements
- **Pass (High Clarity):** Explicitly addresses user feedback regarding single-page cycling between tiers (avoiding multiple views/pages), adds 24 requested grassroots venues on DICE, and bridges the stadium/arena blindspot with Ticketmaster Discovery API v2.

### Prior Solutions & Compound Learning
- **Pass:** Directly references ADR-001, ADR-002, and prior solution documents in `docs/solutions/integration_issue/live-curator-engine-architecture.md`.

### Architecture & Technical Soundness
- **Single-Page Tab Cycling:** Hybrid architecture solves the email client limitation (JavaScript stripped by Gmail) by offering rich instant DOM filtering in browser previews and anchor jump links with external web links in email clients.
- **Ticketmaster Discovery API v2:** Utilizing the official REST API rather than web scraping avoids Akamai bot-blocking, guarantees 100% reliability, and cleanly maps into our existing `Event` entity.
- **Sports Exclusion:** Explicitly enforces `classificationName=Music` (and Arts/Comedy) to prevent Premier League football matches or NFL games at Wembley/Tottenham from cluttering live music digests.
- **Backwards Compatibility:** All existing 47 pytest unit tests will continue to pass without regression.

---

## 2. Risk & Mitigation Assessment

| Risk | Likelihood | Impact | Planned Mitigation |
|---|---|---|---|
| Missing `TICKETMASTER_API_KEY` in `.env` | Medium | Low | Engine logs a friendly notice and gracefully continues with DICE venues; dry-run mock fixtures provide full test coverage. |
| Increased DICE scraping runtime (24 venues) | High | Low | Playwright stealth reuses a single browser context across venues; scraping takes ~45 seconds, well within monthly cron budgets. |
| Email client strips JavaScript | High | Medium | Dual-layer template provides interactive JS in browser preview while providing CSS anchor jump links in static email clients. |

---

## 3. Verdict & Recommended Execution Order

**Verdict:** **Approved ✓**

### Execution Plan:
- **Phase 1:** Update `src/core/models.py`, `src/core/config.py`, and expand `config/venues.yaml` (33+ venues across London).
- **Phase 2:** Implement `src/ingestion/ticketmaster_engine.py`, standalone test CLI, and unit tests with mock responses.
- **Phase 3:** Redesign `templates/digest.html` with the interactive single-page tab cycling controller and CSS/JS.
- **Phase 4:** Update `main.py` with dual-engine orchestration and CLI filter flags (`--platform`, `--area`).
- **Phase 5:** Run full test suite (55+ tests) and perform live e2e `--preview-html` validation.
