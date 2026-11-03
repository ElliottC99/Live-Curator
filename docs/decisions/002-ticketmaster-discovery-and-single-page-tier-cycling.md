---
id: "ADR-002"
title: "Ticketmaster Discovery Ingestion and Single-Page Tier Cycling"
date: "2026-11-03"
status: "accepted"
deprecated_date: ""
superseded_by: ""
tags:
  - ticketmaster-api
  - stadium-ingestion
  - single-page-ui
  - tier-cycling
  - interactive-tabs
last_referenced: "2026-11-03"
---

# ADR-002: Ticketmaster Discovery Ingestion and Single-Page Tier Cycling

## Status
Accepted

## Context
1. **User Experience:** The monthly digest output needs to be digestible without scrolling through hundreds of events across dozens of venues. The user explicitly requested a single-page view where they can cycle between Tier 1 (Direct Matches), Tier 2 (Discovery Matches), and Tier 3 (Comedy & Alternative).
2. **Venue Expansion:** Elliott & Chloe's live music discovery scope is expanding from 9 Dalston seed venues to 24+ iconic London grassroots music and comedy venues across Dalston, Stoke Newington, Islington, Camden, and Shoreditch on DICE.
3. **Major Stadiums & Arenas:** Massive London venues (Wembley Stadium, London Stadium, Tottenham Hotspur Stadium, The O2 Arena, OVO Arena Wembley, Finsbury Park, Drumsheds, etc.) ticket primarily through Ticketmaster rather than DICE. Ticketmaster's website employs Akamai Bot Manager which bans web scrapers, but Ticketmaster provides an official, free REST Discovery API v2 with 5,000 requests/day.

## Decision
1. **Interactive Single-Page Tier Cycling:**
   - In browser preview (`output/preview.html`), implement an interactive tab controller (`[🔥 Tier 1] [✨ Tier 2] [🎭 Tier 3] [📋 All Shows]`) using semantic markup and vanilla JavaScript.
   - Support URL hash routing (`#tier1`, `#tier2`, `#tier3`, `#all`) and keyboard cycling.
   - For email client dispatch (`templates/digest.html`), implement anchor jump pills at the top that smoothly scroll to sections in email clients, plus a prominent web link to view the full interactive single-page digest.
2. **Multi-Platform Venue Schema:**
   - Update `Venue` model and `config/venues.yaml` with fields: `platform: "dice" | "ticketmaster"`, `tm_venue_id: Optional[str]`, `tm_keyword: Optional[str]`, and `area: str`.
3. **Ticketmaster Discovery Engine (`src/ingestion/ticketmaster_engine.py`):**
   - Query `https://app.ticketmaster.com/discovery/v2/events.json` using `TICKETMASTER_API_KEY` (with graceful dry-run simulation when the key is not yet set).
   - Strictly filter with `classificationName=Music` (and Arts/Comedy) to exclude non-music sporting fixtures (e.g. Premier League football matches at Tottenham Hotspur or Wembley).
   - Normalize lineups and prices into unified `Event` models.

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| Web scrape Ticketmaster HTML via Playwright | No API key needed | Akamai Bot Manager IP-bans headless browsers; brittle DOM changes | Highly fragile, high risk of execution failure |
| Static vertical email without cycling | Simple markup | Long wall of text when 33+ venues are scraped | Fails user requirement to cycle between tiers on one page |
| Dedicated React/Vue Single-Page App | Rich client-side state | Heavy tooling, build step, separate server required | Overkill for a local monthly digest engine; vanilla JS/HTML delivers 100% of capabilities in zero extra dependencies |

## Consequences

**Positive:**
- Seamless cycling between tiers on one page.
- Direct coverage of massive stadium and arena tours alongside intimate basement gigs.
- Zero bot-blocking for stadium shows via official Ticketmaster REST API.
- Fully backwards compatible with existing 9 venues and test suite.

**Negative:**
- Users who want stadium shows must obtain a free Ticketmaster developer key (or rely on mock/cached stadium listings in dry-run).

## Related
- ADR: [ADR-001: Live Curator Engine Architecture](001-engine-architecture-and-data-ingestion.md)
- Exploration: [docs/explorations/venue-expansion-ticketmaster-tier-cycling-20261103.md](../explorations/venue-expansion-ticketmaster-tier-cycling-20261103.md)
