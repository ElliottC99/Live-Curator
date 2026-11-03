#!/usr/bin/env python3
"""Build static distribution for GitHub Pages.

Generates:
- public/index.html: Interactive Live Curator Digest web app with client-side tier cycling & filters
- public/venues.html: In-App Venue & Neighbourhood Manager with preloaded venues and localStorage memory
- docs/index.html & docs/venues.html: For direct 'main /docs' GitHub Pages branch deployment
"""

import json
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from src.__version__ import __version__
from src.core.models import Event, MonthlyDigest, Venue
from src.core.normalizer import normalize_artist_name, split_lineup
from src.delivery.template_engine import TemplateEngine
from src.ingestion.review_parser import ReviewDatabase
from src.ingestion.spotify_engine import load_seed_taste_profile
from src.processing.tier_classifier import TierClassifier
from src.ui.venue_manager import HTML_DASHBOARD

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BuildPages")


def load_events_from_history() -> list[Event]:
    """Load known upcoming events from JSON seed file or historical SQLite cache."""
    seed_json_path = PROJECT_ROOT / "data" / "seed_events.json"
    db_path = PROJECT_ROOT / "data" / "cache" / "digest_history.sqlite"
    events = []

    # If SQLite exists locally, sync latest into seed_events.json
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()
            c.execute("""
                SELECT event_id, title, venue_name, venue_area, start_time, ticket_url, platform
                FROM seen_events
            """)
            raw_list = []
            for row in c.fetchall():
                raw_list.append({
                    "id": row[0],
                    "title": row[1],
                    "venue_name": row[2],
                    "venue_area": row[3] or "East London",
                    "start_time": row[4],
                    "ticket_url": row[5] or "https://dice.fm",
                    "platform": row[6] or "dice",
                })
            conn.close()
            seed_json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(seed_json_path, "w", encoding="utf-8") as f:
                json.dump(raw_list, f, indent=2)
            logger.info(f"Synchronized {len(raw_list)} events to data/seed_events.json")
        except Exception as e:
            logger.warning(f"Failed to sync SQLite to seed_events.json: {e}")

    # Load from seed_events.json (tracked in Git, always present on GitHub Actions)
    if seed_json_path.exists():
        try:
            with open(seed_json_path, "r", encoding="utf-8") as f:
                raw_events = json.load(f)
            for item in raw_events:
                try:
                    dt = datetime.fromisoformat(item["start_time"])
                except Exception:
                    dt = datetime.now()
                area = item.get("venue_area") or "East London"
                if area.lower() == "east london" and "wembley" in item.get("venue_name", "").lower():
                    area = "Wembley"
                title = item.get("title", "")
                performers = item.get("performers") or split_lineup(title)
                norm_performers = [normalize_artist_name(p) for p in performers if p]
                events.append(
                    Event(
                        id=item.get("id"),
                        title=title,
                        venue_name=item.get("venue_name", ""),
                        venue_area=area,
                        start_time=dt,
                        date_str=dt.strftime("%a %d %b %Y, %H:%M"),
                        performers=performers,
                        normalized_performers=norm_performers,
                        ticket_url=item.get("ticket_url") or "https://dice.fm",
                        platform=item.get("platform") or "dice",
                    )
                )

            # Deduplicate cross-platform duplicate listings
            deduped_events = []
            seen_signatures = set()
            for ev in events:
                primary = ev.normalized_performers[0] if ev.normalized_performers else normalize_artist_name(ev.title)
                d_str = ev.start_time.strftime("%Y-%m-%d") if ev.start_time else ""
                v_name = ev.venue_name.lower().strip()
                sig = (primary, d_str, v_name)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    deduped_events.append(ev)

            logger.info(f"Loaded {len(deduped_events)} events from data/seed_events.json (deduplicated from {len(events)}).")
            return deduped_events
        except Exception as ex:
            logger.error(f"Error loading seed_events.json: {ex}")

    return events


def build_pages():
    logger.info("Building static GitHub Pages application...")
    public_dir = PROJECT_ROOT / "public"
    docs_dir = PROJECT_ROOT / "docs"
    public_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load venues from config
    venues_yaml_path = PROJECT_ROOT / "config" / "venues.yaml"
    venues_list = []
    if venues_yaml_path.exists():
        with open(venues_yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            venues_list = data.get("venues", [])

    # 2. Build Event Digest with Taste Profiles and Review Insights
    events = load_events_from_history()
    taste_profile = load_seed_taste_profile()
    review_db = ReviewDatabase()
    rec_artists = review_db.get_recommended_artists()

    classifier = TierClassifier(
        taste_profile=taste_profile,
        review_db=review_db,
        recommended_review_artists=rec_artists,
    )
    now = datetime.now()
    month_name = now.strftime("%B")
    year = now.year

    digest = classifier.build_digest(events, month_name=month_name, year=year)

    # Render index.html
    template_engine = TemplateEngine()
    html_content = template_engine.render_html(digest)
    (public_dir / "index.html").write_text(html_content, encoding="utf-8")
    (docs_dir / "index.html").write_text(html_content, encoding="utf-8")
    logger.info(f"Generated index.html with {digest.total_events_scraped} events.")

    # 3. Build venues.html with embedded initial venues data
    venues_json = json.dumps(venues_list)
    embedded_script = f"<script>window.INITIAL_VENUES = {venues_json};</script>\n</head>"
    venues_html = HTML_DASHBOARD.replace("{{VERSION}}", __version__)
    venues_html = venues_html.replace("</head>", embedded_script)

    (public_dir / "venues.html").write_text(venues_html, encoding="utf-8")
    (docs_dir / "venues.html").write_text(venues_html, encoding="utf-8")
    logger.info(f"Generated venues.html with {len(venues_list)} venues.")

    # Create .nojekyll in both to avoid Jekyll ignoring underscores
    (public_dir / ".nojekyll").touch()
    (docs_dir / ".nojekyll").touch()

    logger.info("✓ GitHub Pages build completed successfully.")


if __name__ == "__main__":
    build_pages()
