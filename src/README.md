# Live Curator Engine — Source Code (`src/`)

## Purpose
Core application modules for scraping, ingesting, classifying, and dispatching monthly live music and comedy digests across East London venues.

## Architecture & Components
- **`core/`**: Core configuration loader, pydantic domain models (`Event`, `Venue`, `Review`, `MonthlyDigest`), and act name normalizer / lineup splitting.
- **`ingestion/`**: Headless Playwright DICE scraper (`dice_scraper.py`), dual-user Spotify OAuth engine (`spotify_engine.py`), and UK music review aggregator (`review_parser.py`).
- **`processing/`**: 3-tier categorization engine (`tier_classifier.py`) matching events against direct library, discovery reviews, and comedy keywords.
- **`delivery/`**: Jinja2 HTML/text template engine (`template_engine.py`) and multi-channel email dispatcher (`digest_mailer.py`).
