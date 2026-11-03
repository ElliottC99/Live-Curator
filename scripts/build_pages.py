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
from src.core.config import load_config
from src.core.models import Event, MonthlyDigest, Venue
from src.delivery.template_engine import TemplateEngine
from src.processing.tier_classifier import TierClassifier
from src.ui.venue_manager import HTML_DASHBOARD

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BuildPages")


def load_events_from_history() -> list[Event]:
    """Load known upcoming events from historical cache."""
    db_path = PROJECT_ROOT / "data" / "cache" / "digest_history.sqlite"
    events = []
    if not db_path.exists():
        logger.warning(f"History DB not found at {db_path}")
        return events

    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""
            SELECT event_id, title, venue_name, venue_area, start_time, ticket_url, platform
            FROM seen_events
        """)
        for row in c.fetchall():
            try:
                dt = datetime.fromisoformat(row[4])
            except Exception:
                dt = datetime.now()

            # Clean venue area fallback
            area = row[3] or "East London"
            if area.lower() == "east london" and "wembley" in row[2].lower():
                area = "Wembley"

            events.append(
                Event(
                    id=row[0],
                    title=row[1],
                    venue_name=row[2],
                    venue_area=area,
                    start_time=dt,
                    date_str=dt.strftime("%a %d %b %Y, %H:%M"),
                    ticket_url=row[5] or "https://dice.fm",
                    platform=row[6] or "dice",
                )
            )
        conn.close()
        logger.info(f"Loaded {len(events)} events from historical database.")
    except Exception as e:
        logger.error(f"Error loading events from history: {e}")

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

    # 2. Build Event Digest
    events = load_events_from_history()
    classifier = TierClassifier()
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
