#!/usr/bin/env python3
"""Batch harvester for all 51 venues configured in config/venues.yaml.

Harvests concerts and club nights from:
1. Songkick (Schema.org JSON-LD for keyless arenas, stadiums, and iconic venues)
2. DICE.fm (Playwright headless scraper with stealth evasions)

Saves all events to:
- data/cache/digest_history.sqlite (seen_events)
- data/seed_events.json (Git-tracked static seed for GitHub Pages CI)
"""

import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from src.core.config import Config, load_config
from src.core.models import Event, Venue
from src.ingestion.dice_scraper import DiceScraper
from src.ingestion.songkick_engine import SongkickEngine
from src.processing.event_diff_engine import EventDiffEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Harvester")


def harvest_all():
    logger.info("Starting London Live Music & Comedy Multi-Venue Harvester...")
    config = load_config()
    venues = list(config.venues)
    logger.info(f"Loaded {len(venues)} venues from config/venues.yaml.")

    all_harvested_events: list[Event] = []

    # 1. Harvest Songkick Venues (Fast, Schema.org JSON-LD via HTTP)
    songkick_venues = [
        v for v in venues
        if v.platform == "songkick" or (v.songkick_url and v.platform not in ["dice", "ticketmaster"])
    ]
    logger.info(f"--- Harvesting {len(songkick_venues)} Songkick Venues ---")
    sk_engine = SongkickEngine()
    for v in songkick_venues:
        try:
            logger.info(f"Fetching Songkick: {v.name} ({v.area})...")
            events = sk_engine.fetch_venue_events(v)
            logger.info(f"  ✓ {v.name}: {len(events)} events found")
            all_harvested_events.extend(events)
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"  ✗ Failed Songkick fetch for {v.name}: {e}")

    # 2. Harvest DICE Venues (Playwright Headless)
    dice_venues = [v for v in venues if v.platform == "dice"]
    logger.info(f"--- Harvesting {len(dice_venues)} DICE.fm Venues ---")
    if dice_venues:
        scraper = DiceScraper(headless=True, config=config)
        # Use single browser context for efficiency
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser, context = scraper._create_browser_and_context(p)
            page = context.new_page()
            scraper.stealth.apply_stealth_sync(page)

            for v in dice_venues:
                try:
                    logger.info(f"Scraping DICE: {v.name} ({v.area})...")
                    events = scraper.scrape_venue(page, v)
                    logger.info(f"  ✓ {v.name}: {len(events)} events found")
                    all_harvested_events.extend(events)
                    time.sleep(1.0)
                except Exception as e:
                    logger.warning(f"  ✗ Failed DICE scrape for {v.name}: {e}")

            browser.close()

    logger.info(f"=== Total Events Harvested: {len(all_harvested_events)} ===")

    # 3. Deduplicate events by canonical fingerprint
    unique_events: dict[str, Event] = {}
    for ev in all_harvested_events:
        fp = EventDiffEngine.compute_fingerprint(ev)
        if fp not in unique_events:
            unique_events[fp] = ev

    deduped_events = list(unique_events.values())
    logger.info(f"Unique Events after deduplication: {len(deduped_events)}")

    # 4. Save to SQLite cache (digest_history.sqlite)
    db_path = PROJECT_ROOT / "data" / "cache" / "digest_history.sqlite"
    diff_engine = EventDiffEngine(db_path)
    now_iso = datetime.now().isoformat()
    label = datetime.now().strftime("%B %Y")

    with diff_engine._get_connection() as conn:
        for ev in deduped_events:
            fp = EventDiffEngine.compute_fingerprint(ev)
            start_iso = ev.start_time.isoformat() if ev.start_time else ""
            conn.execute(
                """
                INSERT INTO seen_events (
                    event_id, title, venue_name, venue_area, start_time,
                    ticket_url, platform, first_seen_at, last_seen_at, first_digest_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    ticket_url = excluded.ticket_url,
                    venue_area = excluded.venue_area
                """,
                (
                    fp,
                    ev.title,
                    ev.venue_name,
                    ev.venue_area,
                    start_iso,
                    ev.ticket_url,
                    ev.platform,
                    now_iso,
                    now_iso,
                    label,
                ),
            )
        conn.commit()

    logger.info(f"Persisted {len(deduped_events)} events into {db_path}")

    # 5. Export directly to data/seed_events.json
    seed_json_path = PROJECT_ROOT / "data" / "seed_events.json"
    seed_data = []
    for ev in deduped_events:
        seed_data.append({
            "id": ev.id or EventDiffEngine.compute_fingerprint(ev),
            "title": ev.title,
            "venue_name": ev.venue_name,
            "venue_area": ev.venue_area or "London",
            "start_time": ev.start_time.isoformat() if ev.start_time else datetime.now().isoformat(),
            "ticket_url": ev.ticket_url or "https://dice.fm",
            "platform": ev.platform or "dice",
        })

    with open(seed_json_path, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, indent=2)

    logger.info(f"Exported {len(seed_data)} events to {seed_json_path}")
    print(f"\n✓ HARVEST COMPLETE: {len(seed_data)} events across London ready for deployment.")


if __name__ == "__main__":
    harvest_all()
