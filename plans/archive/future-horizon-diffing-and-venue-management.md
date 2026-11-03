# Plan: Rolling Future Horizon, Delta Announcement Highlighting & In-App Venue Manager

> Created: 2026-11-03  
> Status: Completed ✓  
> Exploration Ref: [docs/explorations/future-horizon-diffing-and-venue-management-20261103.md](../docs/explorations/future-horizon-diffing-and-venue-management-20261103.md)  
> Architectural Decisions: [docs/decisions/001-engine-architecture-and-data-ingestion.md](../docs/decisions/001-engine-architecture-and-data-ingestion.md), [docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md](../docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)

---

## Summary
Transform the **Live Curator Engine** from a month-bounded snapshot into a continuous live event intelligence system that:
1. Discovers and tracks **all upcoming announced events into the future** ($\text{date} \ge \text{today}$) across grassroots clubs, theatres, and major stadiums without cutting off at month-end.
2. Statefully tracks historical event discoveries in a persistent SQLite store (`data/cache/digest_history.sqlite`) and spotlights **newly announced gigs** (`[🔥 NEW ANNOUNCEMENT]` / `[🆕 JUST ADDED]`) since the previous digest run, with dedicated quick filters and subject line highlighting.
3. Provides an **in-app, user-friendly local web management UI** (`main.py --ui` or an in-preview management modal) allowing Elliott & Chloe to reassign venue neighbourhoods, add new venues, and toggle venues active/inactive with one click—persisting atomically to `config/venues.yaml` without writing code or editing YAML files.

---

## Problem Statement
1. **Missed Lead Time for Hot Tours:** Gigs in London are announced 3 to 12 months ahead. Limiting ingestion to a single calendar month (e.g. November) discards upcoming Spring/Summer stadium tours, festivals, and high-demand club gigs that sell out before that month arrives.
2. **Lack of Delta Highlighting:** Subscribers opening recurring digests need to know immediately: *"What has been added since the last digest?"* Without stateful diffing, readers cannot distinguish between long-standing listings and brand-new drops.
3. **High Friction Configuration:** Changing venue neighbourhoods (e.g. moving a venue between Dalston and Islington) currently requires editing YAML or code. A non-technical user needs a point-and-click UI to manage venues, neighbourhoods, and active toggles effortlessly.

---

## Prior Solutions

| Solution | Relevance | Action |
|----------|-----------|--------|
| [ADR-001: Live Curator Engine Architecture](docs/decisions/001-engine-architecture-and-data-ingestion.md) | ⭐️ Core Decision | Referencing |
| [ADR-002: Ticketmaster Ingestion and Single-Page Tier Cycling](docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md) | ⭐️ Core Decision | Referencing |
| [Exploration: Rolling Future Horizon & Venue Management](docs/explorations/future-horizon-diffing-and-venue-management-20261103.md) | ⭐️ Core Exploration | Implementing |
| [Pattern #09: Rigorous Planning (Multi-Order Thinking)](docs/solutions/patterns/individual/pattern-09-rigorous-planning-multi-order-thinking.md) | ⭐️ Best Practice | Following |
| [Pattern #24: Batch Resource Operations](docs/solutions/patterns/individual/pattern-24-batch-resource-operations.md) | ⭐️ Performance | Reusing |

---

## Research Findings

### Codebase Patterns
- `src/core/models.py`:
  - `Event` has `id: Optional[str]`, `title: str`, `venue_name: str`, `venue_area: str`, `start_time: datetime`, `ticket_url: str`.
  - Adding `is_new: bool = False` and `first_seen_at: Optional[datetime] = None` cleanly integrates delta tracking.
- `src/core/config.py` & `config/venues.yaml`:
  - Venues are loaded via `Venue(**item)`. We can use standard library atomic file writing (`tempfile` + `os.replace`) to preserve clean formatting when updating `config/venues.yaml`.
- `templates/digest.html`:
  - Contains responsive styling, sticky tab bar, and client-side filtering script (`applyFiltersAndSort()`). We can add a `[🆕 Just Announced (N)]` tab and a `🔥 NEW ANNOUNCEMENT` badge seamlessly.

### Best Practices (Industry Newsletters & Event Discovery)
- **Delta Highlighting:** Highlight fresh drops in subject lines (`[Live Curator London] 14 New Announcements Added`) and badge cards with contrasting vibrant pills.
- **Dedicated Delta Filter:** Users can filter specifically to newly discovered shows to reduce cognitive load.
- **Local Web Management UI:** Standard library Python `http.server` provides an instant local dashboard without adding heavy dependencies like Flask or FastAPI.

---

## Proposed Solution

### 1. Persistent Delta Tracking Engine (`src/processing/event_diff_engine.py`)
- SQLite database at `data/cache/digest_history.sqlite`.
- Schema:
  ```sql
  CREATE TABLE IF NOT EXISTS seen_events (
      event_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      venue_name TEXT NOT NULL,
      venue_area TEXT NOT NULL,
      start_time TEXT NOT NULL,
      ticket_url TEXT NOT NULL,
      platform TEXT NOT NULL,
      first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      first_digest_date TEXT NOT NULL
  );
  ```
- Generates canonical event fingerprint: `hash(event.ticket_url or (event.venue_name + event.title + event.date_str))`.
- When diffing:
  - If event ID is absent from `seen_events`, mark `event.is_new = True`.
  - Upsert all current events into `seen_events` with updated `last_seen_at`.

### 2. Open-Ended Horizon Pipeline (`main.py` & `src/processing/tier_classifier.py`)
- Do not reject events occurring outside the current month; retain all upcoming events ($\text{date} \ge \text{today}$).
- Pass `EventDiffEngine` into pipeline to annotate events with `is_new`.
- Digest metadata includes `new_announcements_count`.
- Update email subject line to highlight new announcements:
  - E.g.: `[Live Curator London] 14 New Shows Added — 2 Direct Matches (Colin Miller @ MOTH Club)`

### 3. Interactive UI & Email Enhancements (`templates/digest.html`)
- Display `🔥 JUST ANNOUNCED` badge on cards where `event.is_new` is true.
- Add `[🆕 New (N)]` button in tab bar (`switchTier('new')`).
- Add stats badge in header: `Total: N | 🆕 New This Month: M`.

### 4. In-App Venue & Neighbourhood Manager (`src/ui/venue_manager.py` & `main.py --ui`)
- Built using Python's standard `http.server` running on `http://127.0.0.1:8765`.
- Endpoints:
  - `GET /`: Clean, modern responsive dashboard listing all venues grouped by neighbourhood.
  - `POST /api/venues/update`: Updates venue's neighbourhood, name, or active status.
  - `POST /api/venues/add`: Adds a new venue with name, platform, slug/keyword, and neighbourhood.
  - `POST /api/run`: Triggers digest generation and opens the updated preview.
- Saves changes atomically to `config/venues.yaml` via YAML serializer with backup.

---

## Multi-Order Analysis (Think Hard)

### Direct Effects (1st Order)
- The digest captures all upcoming gigs regardless of month, eliminating the risk of missing advance ticket drops.
- Brand new announcements are prominently spotlighted.
- Elliott can reassign neighbourhoods in seconds through the web UI without editing code.

### Ripple Effects (2nd-4th Order)
- **2nd Order:** Scraper volume increases as multi-month listings are ingested. DICE already returns ~30 upcoming shows per venue (~1.2s per venue); Ticketmaster returns up to 50 events per stadium. The client-side filter and tier structure prevent user overwhelm.
- **3rd Order:** SQLite cache maintains persistent history across months. Re-running the tool on the same day won't re-flag previously seen shows as "new" unless a new run date is passed.
- **4th Order:** Live Curator functions as a continuous intelligence assistant, tracking touring cycles and ticket on-sale timing.

### Stakeholder Impact Matrix
| Stakeholder | Potential Impact | Severity |
|-------------|-----------------|----------|
| Elliott & Chloe | Spot hot tour announcements early; easily manage venues via browser | High Positive |
| Digest Deliverability | HTML size controlled via pagination/tier grouping; email-safe CSS maintained | Low / Managed |
| Development & Testing | Zero external dependencies added for UI (built with standard library `http.server`) | Positive |

---

## Acceptance Criteria

### Event Delta Diffing & Future Horizon
- [x] `Event` model updated with `is_new: bool = False` and `first_seen_at: Optional[datetime] = None`.
- [x] `EventDiffEngine` implemented in `src/processing/event_diff_engine.py`:
  - Persistent SQLite storage at `data/cache/digest_history.sqlite`.
  - Correctly detects previously seen vs. newly announced events.
  - Records discovery timestamps and digest dates.
- [x] Digest generation includes all future events ($\text{date} \ge \text{today}$) without single-month cutoff.
- [x] `templates/digest.html` displays:
  - Glowing `🔥 JUST ANNOUNCED` badge on newly discovered cards.
  - `[🆕 Just Announced (N)]` quick tab pill in top navigation.
  - New-announcement counter in digest summary banner.
- [x] Email subject line highlights new announcement count when present.

### In-App Venue & Neighbourhood Manager
- [x] `src/ui/venue_manager.py` implemented:
  - Self-contained local web server (built using Python standard library `http.server`).
  - Web UI at `http://127.0.0.1:8765` featuring:
    - Interactive table of all configured venues.
    - Dropdown to reassign any venue's neighbourhood (*Dalston*, *Islington & Angel*, *Camden*, *Stoke Newington*, *Shoreditch*, *Stadiums*, or new custom area).
    - Form to add new venues with automatic slug/keyword validation.
    - One-click "Save Changes & Generate Digest" button.
  - Atomic persistence to `config/venues.yaml` ensuring zero formatting corruption.
- [x] CLI command `python main.py --ui` launches the manager and automatically opens the browser.
- [x] `templates/digest.html` includes a direct button: `⚙️ Manage Venues & Neighbourhoods` linking to the local manager.

### Quality & Verification
- [x] Comprehensive unit tests for `EventDiffEngine` in `tests/test_event_diff_engine.py`.
- [x] Unit tests for `VenueManager` API and YAML updating in `tests/test_venue_manager.py`.
- [x] All existing and new automated tests pass (59+ tests).
- [x] Verified end-to-end dry-run with browser preview.

---

## Implementation Phases

### Phase 1: Event Model & Diffing Engine
1. Update `src/core/models.py` with `is_new: bool = False`, `first_seen_at: Optional[datetime] = None`.
2. Implement `src/processing/event_diff_engine.py` with SQLite backing.
3. Create unit tests in `tests/test_event_diff_engine.py`.

### Phase 2: Pipeline Integration & Rolling Horizon
1. Update `src/processing/tier_classifier.py` and `main.py` to remove month truncation and retain all future events.
2. Ingest `EventDiffEngine` into `run_pipeline()`.
3. Update `MonthlyDigest` model with `new_announcements_count`.
4. Update `DigestMailer` subject line builder to highlight new drops.

### Phase 3: Single-Page UI Updates (Badges & New-Drop Tab)
1. Update `templates/digest.html`:
   - Add `🔥 JUST ANNOUNCED` badge markup.
   - Add `[🆕 New (N)]` tab to interactive pill bar.
   - Update JavaScript controller to filter by `is_new`.
   - Add `⚙️ Manage Venues` header button.

### Phase 4: In-App Venue & Neighbourhood Manager UI
1. Implement `src/ui/venue_manager.py`:
   - Standard library `http.server` handler.
   - Embedded HTML/CSS/JS dashboard for venue and neighbourhood management.
   - REST endpoints `/api/venues/save` and `/api/venues/add`.
   - Safe atomic writer for `config/venues.yaml`.
2. Add `--ui` flag to `main.py` to start the server and open browser.
3. Create unit tests in `tests/test_venue_manager.py`.

### Phase 5: Verification & Quality Assurance
1. Run full test suite with pytest.
2. Test `--ui` and verify venue neighbourhood changes persist to `config/venues.yaml`.
3. Run end-to-end preview check.
4. Run compound validation and housekeeping.

---

## References
- [Exploration Document](docs/explorations/future-horizon-diffing-and-venue-management-20261103.md)
- [ADR-001: Architecture Decision](docs/decisions/001-engine-architecture-and-data-ingestion.md)
- [ADR-002: Ticketmaster Ingestion and Single-Page Tier Cycling](docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)
