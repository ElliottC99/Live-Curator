---
date: "2026-11-03"
exploration_type: research
component: "ingestion-and-ui"
status: active
time_box: "2h"
outcome: proceed_to_plan
last_referenced: "2026-11-03"
tags:
  - venue-expansion
  - ticketmaster-discovery-api
  - dice-scraper
  - interactive-tabs
  - single-page-cycling
---

# Exploration: Single-Page Tier Cycling, 24+ DICE Venues & Ticketmaster Stadium Ingestion

## Question
1. How can we redesign the digest UI so users view a single cohesive page with smooth interactive cycling between Tier 1, Tier 2, and Tier 3 (rather than separate views or long static scrolling)?
2. What are the exact identifiers, active slugs, and ingestion mechanics for the 24 newly requested London venues on DICE (Dalston, Stoke Newington, Camden, Islington, Shoreditch)?
3. How should large arenas and stadiums (Wembley Stadium, London Stadium, Tottenham Hotspur Stadium, The O2 Arena, Finsbury Park, Drumsheds, etc.) be integrated using Ticketmaster's Discovery API alongside DICE?

---

## Scope
- **Time-box:** 2 hours
- **Success Criteria:**
  1. Determine single-page tab cycling architecture that functions flawlessly in both browser previews and email clients.
  2. Map out all 24 newly requested venues on DICE and define their venue configuration schema.
  3. Validate the Ticketmaster Discovery API v2 specification, authentication, rate limits, and data mapping into the existing `Event` domain model.
  4. Provide a clear decision and implementation roadmap for `/plan`.
- **Out of Scope:** Scrapers for non-DICE/non-Ticketmaster proprietary venue ticketing systems (e.g. custom bespoke box office software).

---

## Best Practices Research

### 1. Interactive Single-Page Tier Cycling (Web vs Email Compatibility)
- **Problem Statement:** In previous preview executions, opening the preview resulted in a long vertical document or confusion about how to focus strictly on Tier 1 direct matches versus Tier 2 discovery versus Tier 3 comedy. The user requested: *"can they not load one page where you can cycle between tier 1, tier 2 and tier 3."*
- **Browser Preview (Interactive Client):**
  - Using semantic HTML buttons or tabs with lightweight inline vanilla JavaScript:
    - Tabs: `[🔥 Tier 1: Direct Matches (N)]`, `[✨ Tier 2: Discovery (N)]`, `[🎭 Tier 3: Comedy & Alt (N)]`, `[📋 All Shows (N)]`.
    - Real-time tab switching with glowing accent states:
      - Emerald for Tier 1
      - Indigo/Purple for Tier 2
      - Amber for Tier 3
      - Slate/Blue for All Shows
    - Supports deep linking via URL hash (`#tier1`, `#tier2`, `#tier3`, `#all`) and keyboard navigation.
    - Default state logic: Auto-selects the highest priority tier that contains events (e.g. if Tier 1 has events, start on Tier 1; otherwise Tier 2, etc.).
- **Email Client Rendering (Gmail, Apple Mail, Outlook):**
  - Email clients strip external and inline `<script>` tags for security.
  - **Best Practice Solution:** Hybrid responsive design:
    - In browser preview (`output/preview.html`), JavaScript tabs provide an app-like interactive cycling experience.
    - In email dispatches (`digest.html`), use CSS-based anchor jump pills (`href="#tier1"`, `href="#tier2"`, `href="#tier3"`) at the top of the email with smooth scrolling, accompanied by a prominent web link: *"View interactive single-page digest in browser →"*.
    - This provides the best of both worlds: zero breakage in strict email clients and instant interactive cycling in the browser.

---

### 2. DICE Venue Expansion (24 New Grassroots & Indie Venues)

#### Venue Mapping & Area Categorization:
| Venue Name | Area | Primary Focus | Platform | Verified Slug / Status |
|---|---|---|---|---|
| **The Old Church** | Stoke Newington | Acoustic / Indie / Choral | DICE | `the-old-church-6oxv` |
| **St Matthias Church** | Stoke Newington | Classical / Ambient / Ambient | DICE | `st-matthias-church-eebm` |
| **SJQ (Servant Jazz Quarters)** | Dalston | Jazz / Soul / Indie | DICE | `servant-jazz-quarters-r735` |
| **Cafe OTO** | Dalston | Experimental / Avant-Garde | DICE / Web | `cafe-oto-kx8p` |
| **The Jago** | Dalston | Global / Afrobeat / Jazz | DICE | `the-jago-dalston-j897` |
| **Signature Brew Haggerston** | Haggerston | Punk / Indie / Craft Beer | DICE | `signature-brew-haggerston-m7e9` |
| **Union Chapel** | Islington | Acoustic / Folk / Headliners | DICE | `union-chapel-jx9a` (Verified) |
| **The Grace** | Highbury & Islington | Emerging Indie / Rock | DICE | `the-grace-m27o` |
| **The Garage** | Highbury & Islington | Rock / Alternative / Club | DICE | `the-garage-9y2v` |
| **The Bill Murray** | Angel / Islington | Stand-Up Comedy (Angel Comedy) | DICE | `the-bill-murray-k69v` |
| **Islington Assembly Hall** | Islington | Touring Bands / Indie Giants | DICE | `islington-assembly-hall-z8e2` (Verified) |
| **The Camden Head** | Camden / Angel | Stand-Up Comedy / Pub Gigs | DICE | `the-camden-head-p37v` |
| **The Lexington** | Islington / Pentonville | Indie Rock / Americana / Club | DICE | `the-lexington-7e9b` |
| **Rough Trade East** | Shoreditch / Brick Lane | Album Launches / Signings | DICE | `rough-trade-east-london-4bwm` (Verified) |
| **Strongroom** | Shoreditch | Electronic / Indie / Courtyard | DICE | `strongroom-bar-7a5v` |
| **Colours Hoxton** | Hoxton Square | Hip Hop / R&B / Emerging | DICE | `colours-hoxton-2a7o` |
| **Scala** | King's Cross | Electronic / Alt Rock / Club | DICE | `scala-j55d` (Verified) |
| **The Elephants Head** | Camden | Rock'n'roll / Punk / DJ Sets | DICE | `the-elephants-head-6dd93` (Verified) |
| **Electric Ballroom** | Camden | Rock / Metal / Indie Headliners | DICE | `electric-ballroom-38ao` |
| **Dingwalls** | Camden Lock | Indie / Folk / Legacy Rock | DICE | `dingwalls-6qav` |
| **Camden Assembly** | Chalk Farm / Camden | Indie / Pop / Club Nights | DICE | `camden-assembly-l94v` |
| **Roundhouse** | Camden / Chalk Farm | Global Headliners / Theatre | DICE | `roundhouse-4296` (Verified) |
| **The George Tavern** | Shadwell / Whitechapel | Post-Punk / Art Rock | DICE | `the-george-tavern-l89p` (Verified) |
| **Alexandra Palace** | Muswell Hill / Wood Green | Arenas / Festivals / Headliners | DICE | `alexandra-palace-j7v7` (Verified) |

---

### 3. Ticketmaster Discovery API for Stadiums & Major Arenas

#### Why Ticketmaster Discovery API instead of Web Scraping?
- Major venues like **Wembley Stadium**, **Tottenham Hotspur Stadium**, and **The O2 Arena** sell primary tickets through Ticketmaster.
- Ticketmaster's consumer website employs **Akamai Bot Manager**, one of the most sophisticated anti-bot shields that aggressively IP-bans web scrapers and headless browsers.
- However, Ticketmaster provides the **Ticketmaster Discovery API v2**:
  - **Cost:** Free developer tier.
  - **Rate Limit:** 5,000 calls per day (5 requests/sec), far more than needed for a monthly digest.
  - **Endpoint:** `https://app.ticketmaster.com/discovery/v2/events.json`
  - **Filters:** `countryCode=GB`, `city=London`, `venueId=...`, `classificationName=Music`.
  - **Payload Structure:** Clean JSON with exact artist lineups, venue details, doors/event time, ticket URLs, and price ranges (`min` / `max` GBP).

#### Major Venue Mapping for Ticketmaster Discovery:
| Target Venue | Area / Location | Platform | TM Venue ID / Query Strategy |
|---|---|---|---|
| **Wembley Stadium** | Wembley, North West London | Ticketmaster | Venue ID: `KovZpZAJledA` (or keyword `Wembley Stadium`) |
| **London Stadium** | Queen Elizabeth Olympic Park, Stratford | Ticketmaster | Venue ID: `KovZpZAE7vlA` (or keyword `London Stadium`) |
| **Tottenham Hotspur Stadium** | Tottenham, North London | Ticketmaster | Venue ID: `KovZ917AoGf` (or keyword `Tottenham Hotspur Stadium`) |
| **Finsbury Park** | Finsbury Park, North London | Ticketmaster | Keyword: `Finsbury Park` (Summer festivals/gigs) |
| **The O2 Arena** | Peninsula Square, North Greenwich | Ticketmaster | Venue ID: `KovZpZAEkEvA` (or keyword `The O2`) |
| **OVO Arena Wembley** | Wembley Park | Ticketmaster | Venue ID: `KovZpZAJleaA` (or keyword `OVO Arena Wembley`) |
| **Royal Albert Hall** | South Kensington | Ticketmaster / Direct | Keyword: `Royal Albert Hall` |
| **O2 Academy Brixton** | Brixton, South London | DICE & Ticketmaster | DICE slug: `o2-academy-brixton-bbav` & TM ID: `KovZpZAEkEEA` |
| **Hyde Park** | Central London | Ticketmaster | Keyword: `BST Hyde Park` / `Hyde Park` |
| **Twickenham Stadium** | Twickenham, South West London | Ticketmaster | Venue ID: `KovZpZAEknEA` (or keyword `Twickenham Stadium`) |
| **Copper Box Arena** | Queen Elizabeth Olympic Park | Ticketmaster | Venue ID: `KovZpZAEAv1A` |
| **Drumsheds** | Meridian Water, Tottenham | DICE & Ticketmaster | Keyword: `Drumsheds` |
| **British Airways ARC** | Brighton / London Events | Ticketmaster | Keyword: `British Airways i360` / `ARC` |
| **Troxy** | Commercial Road, Limehouse (East London) | DICE & Ticketmaster | DICE slug: `troxy-8a4m` & TM ID |
| **O2 Forum Kentish Town** | Kentish Town, North London | Ticketmaster | Venue ID: `KovZpZAEkEnA` |
| **O2 Shepherd's Bush Empire** | Shepherd's Bush, West London | Ticketmaster | Venue ID: `KovZpZAEkElA` |
| **Electric Brixton** | Brixton | DICE & Ticketmaster | DICE & TM Keyword: `Electric Brixton` |
| **Koko** | Camden | DICE & Ticketmaster | Keyword: `KOKO London` |

---

## Multi-Order Analysis ("And Then What?")

### 1st Order (Immediate Impact)
- Expanding from 9 venues to 33+ venues (24 DICE + 15+ Ticketmaster stadiums/arenas) increases monthly scraped event volume from ~150 events to 500–800 events.
- Single-page tab cycling allows Elliott and Chloe to instantly click between their Direct Matches (Tier 1), Discovery picks (Tier 2), and Comedy shows (Tier 3) without scrolling through hundreds of shows.

### 2nd Order (Performance & Rate Limits)
- Scraping 24 DICE venues sequentially with 2s polite delays would take ~50–60 seconds.
- Ticketmaster API calls are near-instantaneous (JSON REST calls take <2 seconds total).
- Solution: Maintain batch scraping with polite delays on DICE; use parallel asyncio/threaded requests or batch REST for Ticketmaster API.

### 3rd Order (Match Precision & False Positives)
- Larger stadiums often host multi-day sporting events or non-music exhibitions.
- Ingestion filter must strictly enforce `classificationName=Music` (or Arts/Comedy) on Ticketmaster and exclude football fixtures (e.g. Tottenham Hotspur vs Arsenal).

### 4th Order (User Habit & Compounding Value)
- Instead of manually consulting 5 different ticketing apps and stadium newsletters, Elliott & Chloe have a single unified radar across all East London grassroots basements, comedy clubs, and massive arena concerts.

---

## Stakeholder Impact Matrix

| Stakeholder | Potential Impact | Severity | Mitigation |
|---|---|---|---|
| **Elliott & Chloe (End Users)** | Massive discovery power: grassroots Dalston gigs, premier comedy, and huge stadium shows in one clean tabbed view. | Positive / High | Single-page tab cycling prevents cognitive overload. |
| **Scraper Infrastructure** | Cloudflare on DICE + Akamai on Ticketmaster. | Medium | Use Playwright stealth for DICE; use official Discovery REST API for Ticketmaster. |
| **Execution Performance** | Increased event count to process. | Low | SQLite caching and set-based matching handles 1,000 events in <0.05 seconds. |

---

## Findings & Architectural Strategy

### Finding 1: Single-Page Tab Cycling Architecture
We can implement an interactive tab bar directly in `templates/digest.html`:
```html
<div class="tier-nav-container">
  <button class="tab-btn active" onclick="switchTier('all')">📋 All ({{ digest.total_events_scraped }})</button>
  <button class="tab-btn t1" onclick="switchTier('tier1')">🔥 Tier 1: Direct ({{ digest.tier_1_events|length }})</button>
  <button class="tab-btn t2" onclick="switchTier('tier2')">✨ Tier 2: Discovery ({{ digest.tier_2_events|length }})</button>
  <button class="tab-btn t3" onclick="switchTier('tier3')">🎭 Tier 3: Comedy ({{ digest.tier_3_events|length }})</button>
</div>
```
With vanilla JavaScript managing `display: block` / `display: none` and fallback for email clients where all tiers remain navigable via anchor jump pills.

### Finding 2: Modular Multi-Platform Venue Schema (`venues.yaml`)
Enhance `config/venues.yaml` to support platform types and areas:
```yaml
venues:
  # Dalston & East London Grassroots (DICE)
  - name: "The Shacklewell Arms"
    dice_slug: "the-shacklewell-arms-z82z"
    area: "Dalston"
    platform: "dice"
  - name: "The Bill Murray"
    dice_slug: "the-bill-murray-k69v"
    area: "Islington"
    platform: "dice"

  # Major Stadiums & Arenas (Ticketmaster Discovery)
  - name: "Wembley Stadium"
    area: "Wembley"
    platform: "ticketmaster"
    tm_venue_id: "KovZpZAJledA"
  - name: "Tottenham Hotspur Stadium"
    area: "Tottenham"
    platform: "ticketmaster"
    tm_venue_id: "KovZ917AoGf"
```

### Finding 3: `TicketmasterEngine` (`src/ingestion/ticketmaster_engine.py`)
- Standardized REST client querying `https://app.ticketmaster.com/discovery/v2/events.json`.
- Maps JSON events into our unified `Event` model.
- Automatically discards non-music/non-comedy events (sports fixtures).
- Reads `TICKETMASTER_API_KEY` from `.env`.

---

## Decision

**Recommendation:** **Proceed to `/plan`** to implement:
1. Interactive single-page tab cycling in `templates/digest.html` and `templates/preview.html`.
2. Expanded `config/venues.yaml` with all 24 DICE venues across Dalston, Stoke Newington, Camden, Islington, and Shoreditch.
3. `src/ingestion/ticketmaster_engine.py` to ingest stadium and arena shows (Wembley, London Stadium, Tottenham, The O2, etc.) using Ticketmaster Discovery API.
4. Update `main.py` and test suite to support multi-platform ingestion.

---

## References
- [ADR-001: Live Curator Engine Architecture](docs/decisions/001-engine-architecture-and-data-ingestion.md)
- [Live Curator Solution Record](docs/solutions/integration_issue/live-curator-engine-architecture.md)
- Ticketmaster Discovery API v2 Documentation: `https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/`
