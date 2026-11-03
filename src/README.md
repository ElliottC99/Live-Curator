# Live Curator Engine — Source Code (`src/`)

## Purpose
Core application modules for scraping, ingesting, classifying, and dispatching monthly live music and comedy digests across London venues.

## Key Components
- **`core/`**: Core configuration loader, pydantic domain models (`Event`, `Venue`, `Review`, `MonthlyDigest`), and act name normalizer / lineup splitting.
- **`ingestion/`**: Headless Playwright DICE scraper (`dice_scraper.py`), Songkick JSON-LD engine (`songkick_engine.py`), Ticketmaster Discovery API engine (`ticketmaster_engine.py`), dual-user Spotify OAuth engine (`spotify_engine.py`), and UK music review aggregator (`review_parser.py`).
- **`processing/`**: 3-tier categorization engine (`tier_classifier.py`), persistent SQLite announcement diffing (`event_diff_engine.py`), and interactive user tagging (`user_tag_engine.py`).
- **`delivery/`**: Jinja2 HTML/text template engine (`template_engine.py`) and multi-channel email dispatcher (`digest_mailer.py`).
- **`ui/`**: In-App Venue & Neighbourhood Manager web interface (`venue_manager.py`).

## Component Details
- `src/core/models.py`: Defines immutable domain models with versioning, ticket prices, and sold-out states.
- `src/processing/tier_classifier.py`: Evaluates events for Tier 1, Tier 2, Tier 3, Club Nights, and Unmatched tiers with word-boundary taste matching.
- `src/processing/event_diff_engine.py`: Manages SQLite state for historical seen events and announcement diffs.

## Changelog
### 2026-11-03
- Upgraded version to v0.0.2.
- Added ticket pricing and sold-out availability ingestion across Songkick, DICE, and Ticketmaster.
- Added musical taste and genre intelligence to Tier 4 (Club Nights & DJs).
