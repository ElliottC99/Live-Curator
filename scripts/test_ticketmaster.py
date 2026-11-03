#!/usr/bin/env python3
"""
Standalone test script to inspect Ticketmaster stadium and arena live music ingestion.
Usage:
    .venv/bin/python3 scripts/test_ticketmaster.py
    .venv/bin/python3 scripts/test_ticketmaster.py --venue "Wembley Stadium"
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import load_config
from src.ingestion.ticketmaster_engine import TicketmasterEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TicketmasterTest")


def main():
    parser = argparse.ArgumentParser(description="Test Ticketmaster stadium event ingestion")
    parser.add_argument("--venue", type=str, default=None, help="Filter to a specific venue")
    parser.add_argument("--limit", type=int, default=10, help="Max events to display")
    args = parser.parse_args()

    config = load_config()
    tm_engine = TicketmasterEngine(config=config)

    if not tm_engine.is_configured:
        logger.warning(
            "TICKETMASTER_API_KEY is not set in .env. To enable real stadium ingestion, "
            "get a free developer key at https://developer.ticketmaster.com and add it to .env."
        )
        return

    tm_venues = [v for v in config.venues if v.platform in ["ticketmaster", "both"]]
    if args.venue:
        tm_venues = [v for v in tm_venues if args.venue.lower() in v.name.lower()]

    logger.info(f"Targeting {len(tm_venues)} stadiums and arenas on Ticketmaster...")
    events = tm_engine.fetch_all_venues(tm_venues)

    print("\n" + "=" * 70)
    print(f"EXTRACTED {len(events)} TICKETMASTER STADIUM / ARENA SHOWS:")
    print("=" * 70)
    for idx, e in enumerate(events[:args.limit], 1):
        price = f" [{e.price_str}]" if e.price_str else ""
        print(f"{idx:02d}. {e.title}{price}")
        print(f"    Venue: {e.venue_name} ({e.venue_area}) • {e.date_str}")
        print(f"    Acts:  {', '.join(e.performers)}")
        print(f"    Link:  {e.ticket_url}")
        print("-" * 70)


if __name__ == "__main__":
    main()
