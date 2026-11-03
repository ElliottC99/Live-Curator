#!/usr/bin/env python3
"""Harvest live events across all configured Songkick venues into SQLite cache."""

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import load_config
from src.ingestion.songkick_engine import SongkickEngine
from src.processing.event_diff_engine import EventDiffEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HarvestSongkick")


def harvest():
    cfg = load_config()
    eng = SongkickEngine()
    sk_venues = [v for v in cfg.venues if v.songkick_url]
    logger.info(f"Harvesting {len(sk_venues)} venues via Songkick...")
    events = eng.fetch_all_venues(sk_venues)
    logger.info(f"Total events fetched from Songkick: {len(events)}")

    db_path = PROJECT_ROOT / "data" / "cache" / "digest_history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure database and columns are migrated
    diff_engine = EventDiffEngine(db_path)

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    now_iso = datetime.now().isoformat()
    inserted = 0

    for ev in events:
        fp = EventDiffEngine.compute_fingerprint(ev)
        start_iso = ev.start_time.isoformat() if ev.start_time else ""
        try:
            c.execute("""
                INSERT INTO seen_events (
                    event_id, title, venue_name, venue_area, start_time,
                    ticket_url, platform, first_seen_at, last_seen_at, first_digest_label,
                    price_str, is_sold_out
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    price_str = COALESCE(excluded.price_str, seen_events.price_str),
                    is_sold_out = excluded.is_sold_out
            """, (
                fp, ev.title, ev.venue_name, ev.venue_area, start_iso,
                ev.ticket_url, ev.platform, now_iso, now_iso, "November 2026",
                ev.price_str, 1 if ev.is_sold_out else 0
            ))
            inserted += 1
        except Exception as ex:
            logger.warning(f"Error inserting {ev.title}: {ex}")

    conn.commit()
    c.execute("SELECT COUNT(*) FROM seen_events")
    total = c.fetchone()[0]
    conn.close()
    logger.info(f"Done! Successfully saved {inserted} events into SQLite. Total events now: {total}")


if __name__ == "__main__":
    harvest()
