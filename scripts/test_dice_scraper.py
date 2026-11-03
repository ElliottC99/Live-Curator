#!/usr/bin/env python3
"""
Standalone test script for the DICE.fm Stealth Scraper.
Usage:
    .venv/bin/python3 scripts/test_dice_scraper.py
    .venv/bin/python3 scripts/test_dice_scraper.py --venue "MOTH Club"
    .venv/bin/python3 scripts/test_dice_scraper.py --month 11 --year 2026
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import load_config
from src.ingestion.dice_scraper import DiceScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DiceScraperTest")


def main():
    parser = argparse.ArgumentParser(description="Test DICE.fm Stealth Scraper")
    parser.add_argument("--venue", help="Filter by venue name (case-insensitive substring)")
    parser.add_argument("--month", type=int, help="Filter by event start month (1-12)")
    parser.add_argument("--year", type=int, help="Filter by event start year (e.g., 2026)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--limit", type=int, default=15, help="Number of sample events to print")
    args = parser.parse_args()

    config = load_config()
    venues = config.venues

    if args.venue:
        venues = [v for v in venues if args.venue.lower() in v.name.lower()]
        if not venues:
            logger.error(f"No venue matching '{args.venue}' found in config/venues.yaml")
            sys.exit(1)

    logger.info(f"Targeting {len(venues)} venues:")
    for v in venues:
        logger.info(f"  - {v.name} -> {v.dice_url}")

    scraper = DiceScraper(
        headless=args.headless,
        page_timeout_ms=config.scraping.page_timeout_ms,
        delay_min=config.scraping.polite_delay_seconds_min,
        delay_max=config.scraping.polite_delay_seconds_max,
    )

    logger.info("Starting scraper run...")
    start_time = datetime.now()

    events = scraper.scrape_all_venues(
        venues=venues,
        target_month=args.month,
        target_year=args.year,
    )

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\nScraping complete in {elapsed:.1f}s! Extracted {len(events)} events.")

    if events:
        print("\n" + "=" * 70)
        print(f"SAMPLE EXTRACTED EVENTS (showing up to {args.limit} of {len(events)}):")
        print("=" * 70)
        for idx, ev in enumerate(events[:args.limit], 1):
            price_tag = f"[{ev.price_str}]" if ev.price_str else "[Price N/A]"
            print(f"{idx:02d}. {ev.title} {price_tag}")
            print(f"    Venue:  {ev.venue_name} ({ev.venue_area})")
            print(f"    Date:   {ev.date_str}")
            print(f"    Acts:   {', '.join(ev.performers)}")
            print(f"    Link:   {ev.ticket_url}")
            print("-" * 70)


if __name__ == "__main__":
    main()
