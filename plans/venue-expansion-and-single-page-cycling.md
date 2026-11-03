# Plan: Venue Expansion, Ticketmaster Stadium Discovery & Single-Page Tier Cycling

> Created: 2026-11-03  
> Status: Draft  
> Exploration Ref: [docs/explorations/venue-expansion-ticketmaster-tier-cycling-20261103.md](../docs/explorations/venue-expansion-ticketmaster-tier-cycling-20261103.md)  
> Architectural Decision: [docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md](../docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)

---

## Summary
Expand the **Live Curator Engine** to:
1. Provide an **interactive single-page UI** where users can cycle seamlessly between **Tier 1 (Direct Matches)**, **Tier 2 (Discovery Matches)**, **Tier 3 (Comedy & Alternative)**, and **All Upcoming Shows** without multiple pages or long static scrolling.
2. Expand DICE coverage to **24+ iconic London grassroots venues** across Dalston, Stoke Newington, Camden, Islington, and Shoreditch.
3. Integrate the official **Ticketmaster Discovery API v2** to ingest upcoming concerts and festival appearances at **massive London stadiums, arenas, and outdoor grounds** (Wembley Stadium, London Stadium, Tottenham Hotspur Stadium, The O2 Arena, Finsbury Park, Drumsheds, etc.) with automatic filtering against sports fixtures.

---

## Problem Statement
1. **Digest Usability:** When previewing or reading the monthly digest across dozens of venues, scrolling through hundreds of events makes it easy to miss high-priority direct matches (Tier 1) or comedy shows (Tier 3). Users need an interactive single-page view where they can cycle between tiers with one click.
2. **Grassroots Breadth:** Beyond Dalston, Elliott & Chloe regularly attend gigs in Camden, Islington, Stoke Newington, and Shoreditch (The Bill Murray for comedy, Rough Trade East for album launches, Union Chapel for acoustic sets, The Lexington, Scala, Roundhouse).
3. **Stadium & Arena Blindspot:** Massive headliner tours (Wembley Stadium, Tottenham Hotspur Stadium, The O2 Arena, London Stadium, Finsbury Park) are ticketed on Ticketmaster rather than DICE. Scraping Ticketmaster web pages fails due to Akamai bot detection, but Ticketmaster provides an official, free REST Discovery API.

---

## Prior Solutions

| Solution | Relevance | Action |
|----------|-----------|--------|
| [ADR-001: Live Curator Engine Architecture and Ingestion Strategy](docs/decisions/001-engine-architecture-and-data-ingestion.md) | ⭐️ Core Decision | Referencing |
| [Live Curator Engine: Architectural & Feasibility Exploration](docs/explorations/archive/live-curator-engine-20261103.md) | ⭐️ Core Exploration | Referencing |
| [Exploration: Single-Page Tier Cycling, 24+ DICE Venues & Ticketmaster Stadium Ingestion](docs/explorations/venue-expansion-ticketmaster-tier-cycling-20261103.md) | ⭐️ Feature Exploration | Referencing |
| [Live Curator Engine — Architecture, Ingestion & Categorization](docs/solutions/integration_issue/live-curator-engine-architecture.md) | ⭐️ Implementation Reference | Referencing |

---

## Research Findings

### 1. Single-Page Tab Cycling Architecture
- **In Browser (`output/preview.html`):** An interactive tab bar with semantic pill buttons (`[🔥 Tier 1 (N)] [✨ Tier 2 (N)] [🎭 Tier 3 (N)] [📋 All (N)]`) and vanilla JavaScript toggles section visibility instantaneously. Auto-selects the highest-priority tier with shows on initial page load and updates URL hash `#tier1`.
- **In Email Clients (Gmail / Apple Mail):** Uses inline CSS anchor links (`href="#tier1"`) with smooth scrolling and a prominent *"View interactive single-page digest in browser →"* button, ensuring 100% email client compatibility.

### 2. DICE Venue Expansion
- **Verified Slugs:**
  - *Union Chapel:* `union-chapel-jx9a`
  - *Islington Assembly Hall:* `islington-assembly-hall-z8e2`
  - *Scala:* `scala-j55d`
  - *Roundhouse:* `roundhouse-4296`
  - *Rough Trade East:* `rough-trade-east-london-4bwm`
  - *Alexandra Palace:* `alexandra-palace-j7v7`
  - *The Elephants Head:* `the-elephants-head-6dd93`
  - *O2 Academy Brixton:* `o2-academy-brixton-bbav`
  - Plus Dalston & North London clubs: The Bill Murray, Cafe OTO, SJQ, The Jago, Signature Brew Haggerston, The Old Church, St Matthias Church, The Garage, The Grace, The Lexington, Strongroom, Colours Hoxton, Electric Ballroom, Dingwalls, Camden Assembly.

### 3. Ticketmaster Discovery API v2
- **Endpoint:** `https://app.ticketmaster.com/discovery/v2/events.json`
- **Authentication:** `apikey={TICKETMASTER_API_KEY}` query parameter. Free developer tier (5,000 calls/day, 5 req/sec).
- **Filtering:** `countryCode=GB`, `city=London`, `classificationName=Music` (and Arts/Theatre/Comedy).
- **Sports Exclusion:** Filtering by `classificationName=Music` automatically excludes Tottenham Hotspur, Arsenal, and England football fixtures.

---

## Acceptance Criteria

### Single-Page Tier Cycling UI
- [ ] `templates/digest.html` includes an interactive tab controller at the top of the listings:
  - `[🔥 Tier 1: Direct Matches (N)]`
  - `[✨ Tier 2: Discovery Matches (N)]`
  - `[🎭 Tier 3: Comedy & Alternative (N)]`
  - `[📋 All Shows (N)]`
- [ ] Clicking any tab filters the visible events instantaneously without page reload in the browser preview.
- [ ] Active tab displays vibrant glowing styling matching tier aesthetics (Emerald, Indigo, Amber, Blue).
- [ ] Initial state automatically selects the highest priority tier that has events.
- [ ] Dual email-safe fallback preserves clean navigation for email clients that strip JavaScript.

### DICE Venue Expansion
- [ ] `config/venues.yaml` expanded to include all 24 requested DICE venues organized by area:
  - Dalston & Hackney, Stoke Newington, Islington & Angel, Shoreditch & Hoxton, Camden & King's Cross.
- [ ] All newly added venues load and parse without breaking the existing scraper.

### Ticketmaster Stadium & Arena Ingestion
- [ ] `Venue` model updated with `platform: str = "dice"`, `tm_venue_id: Optional[str] = None`, `tm_keyword: Optional[str] = None`.
- [ ] `src/ingestion/ticketmaster_engine.py` implemented:
  - Ingests events from Wembley Stadium, London Stadium, Tottenham Hotspur Stadium, The O2 Arena, Finsbury Park, Drumsheds, etc.
  - Maps Ticketmaster event payload into standard `Event` domain objects (lineup, start time, price range, venue, ticket URL).
  - Filters out sports fixtures (`classificationName=Music`).
  - Supports dry-run simulation when `TICKETMASTER_API_KEY` is not configured.
- [ ] Unit tests for `TicketmasterEngine` in `tests/test_ticketmaster_engine.py`.

### Pipeline Integration & Delivery
- [ ] `main.py` ingests from both `DiceScraper` and `TicketmasterEngine`.
- [ ] `TierClassifier` accurately categorizes Ticketmaster events into Tier 1, Tier 2, and Tier 3 alongside DICE events.
- [ ] All 47+ automated tests pass cleanly with pytest.
- [ ] Dry-run preview with `--preview-html` opens the new single-page tabbed interface in default browser.

---

## Implementation Phases

### Phase 1: Multi-Platform Venue Schema & Config Expansion
1. Update `src/core/models.py`:
   - Add `platform: str = "dice"` (or `"ticketmaster"`) to `Venue`.
   - Add `tm_venue_id: Optional[str] = None`, `tm_keyword: Optional[str] = None` to `Venue`.
2. Update `src/core/config.py`:
   - Add `ticketmaster_api_key: Optional[str] = None` to `Config`.
3. Update `config/venues.yaml`:
   - Add the 24 newly requested DICE venues with areas.
   - Add the Ticketmaster stadiums and arenas (Wembley, London Stadium, Tottenham, The O2, Finsbury Park, Drumsheds, etc.).
4. Update `tests/test_config.py`.

### Phase 2: Ticketmaster Discovery Engine
1. Implement `src/ingestion/ticketmaster_engine.py`:
   - REST client querying `https://app.ticketmaster.com/discovery/v2/events.json`.
   - Normalizes Ticketmaster event payloads into `Event` objects.
   - Filters out non-music/sports fixtures.
   - Graceful fallback for unconfigured API key.
2. Create `tests/test_ticketmaster_engine.py` with mock responses.
3. Create standalone verification tool `scripts/test_ticketmaster.py`.

### Phase 3: Interactive Single-Page Tier Cycling UI
1. Update `templates/digest.html`:
   - Implement sticky interactive tab navigation bar with counters.
   - Implement vanilla JavaScript tab controller (`switchTier(tierName)`).
   - Implement glowing CSS active states and transitions.
   - Maintain email-client anchor jump compatibility.
2. Update `templates/digest.txt`.
3. Update `src/delivery/template_engine.py` and `tests/test_delivery.py`.

### Phase 4: Master Orchestration & Filter Flags
1. Update `main.py`:
   - Ingest from both DICE and Ticketmaster engines.
   - Add CLI filter `--platform {all,dice,ticketmaster}`.
   - Add CLI filter `--area {dalston,camden,islington,stadiums,...}`.
2. Generate `output/preview.html` with full interactive single-page cycling.

### Phase 5: Verification & Quality Assurance
1. Run full test suite with `pytest`.
2. Run end-to-end dry-run validation with `--preview-html`.
3. Run compound validation (`./scripts/validate-compound.sh`) and housekeeping.

---

## References
- [ADR-002: Ticketmaster Discovery Ingestion and Single-Page Tier Cycling](docs/decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)
- [Exploration Document](docs/explorations/venue-expansion-ticketmaster-tier-cycling-20261103.md)
- Ticketmaster Discovery API: `https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/`
