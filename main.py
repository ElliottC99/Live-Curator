#!/usr/bin/env python3
"""
Live Curator Engine — Master Orchestrator CLI.
Discovers local live music and comedy events in East London, matches them against
Elliott & Chloe's Spotify tastes and UK music reviews, and generates an email digest.
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import Config, load_config
from src.core.models import CombinedTasteProfile, MonthlyDigest, UserTasteProfile
from src.delivery.digest_mailer import DigestMailer
from src.delivery.template_engine import TemplateEngine
from src.ingestion.dice_scraper import DiceScraper
from src.ingestion.review_parser import ReviewAggregator
from src.ingestion.spotify_engine import SpotifyEngine
from src.ingestion.ticketmaster_engine import TicketmasterEngine
from src.processing.tier_classifier import TierClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("LiveCurator")


def print_banner(month: str, year: int):
    print("=" * 72)
    print(f"  LIVE CURATOR ENGINE // LONDON — {month.upper()} {year}")
    print("=" * 72)


def print_digest_summary(digest: MonthlyDigest):
    print("\n" + "=" * 72)
    print(f"DIGEST SUMMARY — {digest.month_name} {digest.year}")
    print("=" * 72)
    print(f"Total Events Scraped:      {digest.total_events_scraped}")
    print(f"🔥 Tier 1 (Direct Matches): {len(digest.tier_1_events)}")
    print(f"✨ Tier 2 (Discovery):      {len(digest.tier_2_events)}")
    print(f"🎭 Tier 3 (Comedy & Alt):   {len(digest.tier_3_events)}")
    print(f"   Other Unmatched Shows:  {len(digest.other_events)}")
    print("=" * 72)

    if digest.tier_1_events:
        print("\n🔥 TIER 1 HIGHLIGHTS:")
        for e in digest.tier_1_events[:5]:
            matches_str = " | ".join(m.description for m in e.matches)
            print(f"  • {e.title} @ {e.venue_name} ({e.date_str})")
            print(f"    Match: {matches_str}")
            print(f"    Link:  {e.ticket_url}")

    if digest.tier_2_events:
        print("\n✨ TIER 2 HIGHLIGHTS:")
        for e in digest.tier_2_events[:5]:
            matches_str = " | ".join(m.description for m in e.matches)
            print(f"  • {e.title} @ {e.venue_name} ({e.date_str})")
            print(f"    Match: {matches_str}")
            print(f"    Link:  {e.ticket_url}")

    if digest.tier_3_events:
        print("\n🎭 TIER 3 COMEDY HIGHLIGHTS:")
        for e in digest.tier_3_events[:5]:
            print(f"  • {e.title} @ {e.venue_name} ({e.date_str})")
            print(f"    Link:  {e.ticket_url}")
    print("=" * 72 + "\n")


def run_pipeline(
    config: Config,
    venue_filter: Optional[str] = None,
    platform_filter: str = "all",
    area_filter: Optional[str] = None,
    refresh_reviews: bool = False,
    dry_run: bool = True,
    preview_html: bool = False,
    target_month: Optional[str] = None,
    target_year: Optional[int] = None,
) -> MonthlyDigest:
    """Run the complete end-to-end Live Curator pipeline."""
    now = datetime.now()
    month_name = target_month or now.strftime("%B")
    year = target_year or now.year

    print_banner(month_name, year)

    # 1. Ingest Spotify Taste Profiles
    logger.info("Step 1/5: Loading Spotify taste profiles (Elliott & Chloe)...")
    spotify_engine = SpotifyEngine(config)
    taste_profile = spotify_engine.get_combined_taste_profile()
    logger.info(
        f"Spotify profiles loaded: Elliott={len(taste_profile.elliott.all_direct_artists)} direct, "
        f"Chloe={len(taste_profile.chloe.all_direct_artists)} direct artists."
    )

    # 2. Ingest Critical Music Reviews
    logger.info("Step 2/5: Checking critical music reviews (Guardian, ADM, DIY, Dork, NME, L&Q)...")
    db_path = PROJECT_ROOT / "data" / "cache" / "reviews.sqlite"
    review_aggregator = ReviewAggregator(
        db_path=db_path,
        guardian_api_key=config.guardian_api_key,
        min_aggregate_score=config.reviews.min_aggregate_score_10,
        min_stars=config.reviews.min_stars_5,
    )

    if refresh_reviews or not db_path.exists():
        logger.info("Polling publications for fresh critical reviews...")
        review_aggregator.update_all_reviews()

    recommended_artists = review_aggregator.get_recommended_artists()
    logger.info(f"Loaded {len(recommended_artists)} recommended artists from review cache.")

    # 3. Filter venues & Ingest Multi-Platform Listings
    logger.info("Step 3/5: Ingesting event listings (DICE and Ticketmaster)...")
    target_venues = list(config.venues)

    # Apply platform filter
    if platform_filter and platform_filter.lower() != "all":
        target_venues = [v for v in target_venues if v.platform.lower() == platform_filter.lower()]
        logger.info(f"Filtered by platform '{platform_filter}': {len(target_venues)} venues")

    # Apply area filter
    if area_filter:
        target_venues = [
            v for v in target_venues
            if v.area and area_filter.lower() in v.area.lower()
        ]
        logger.info(f"Filtered by area '{area_filter}': {len(target_venues)} venues")

    # Apply venue name filter
    if venue_filter:
        target_venues = [
            v for v in target_venues
            if venue_filter.lower() in v.name.lower()
        ]
        logger.info(f"Filtered by venue name '{venue_filter}': {[v.name for v in target_venues]}")

    all_events = []

    # Ingest DICE venues
    dice_venues = [v for v in target_venues if v.platform == "dice"]
    if dice_venues:
        logger.info(f"Scraping DICE listings ({len(dice_venues)} venues)...")
        dice_scraper = DiceScraper(config)
        dice_events = dice_scraper.scrape_all_venues(dice_venues)
        logger.info(f"Extracted {len(dice_events)} events from DICE.")
        all_events.extend(dice_events)

    # Ingest Ticketmaster venues
    tm_venues = [v for v in target_venues if v.platform == "ticketmaster"]
    if tm_venues:
        logger.info(f"Querying Ticketmaster Discovery API ({len(tm_venues)} stadiums/arenas)...")
        tm_engine = TicketmasterEngine(config)
        tm_events = tm_engine.fetch_all_venues(tm_venues)
        logger.info(f"Extracted {len(tm_events)} events from Ticketmaster.")
        all_events.extend(tm_events)

    logger.info(f"Total live events harvested across all platforms: {len(all_events)}")

    # 4. 3-Tier Categorization
    logger.info("Step 4/5: Categorizing events into 3 Tiers...")
    classifier = TierClassifier(
        taste_profile=taste_profile,
        review_db=review_aggregator.db,
        recommended_review_artists=recommended_artists,
        comedy_keywords=config.classification.comedy_keywords,
    )
    digest = classifier.build_digest(all_events, month_name=month_name, year=year)

    print_digest_summary(digest)

    # 5. Rendering & Delivery
    logger.info("Step 5/5: Rendering digest templates and handling delivery...")
    template_engine = TemplateEngine()
    mailer = DigestMailer(config, template_engine=template_engine)

    if preview_html:
        output_dir = PROJECT_ROOT / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        preview_file = output_dir / "preview.html"
        html_content = template_engine.render_html(digest)
        preview_file.write_text(html_content, encoding="utf-8")
        logger.info(f"Rendered HTML preview saved to: {preview_file.resolve()}")

        # Attempt to open in default browser on macOS
        if sys.platform == "darwin":
            try:
                subprocess.run(["open", str(preview_file)], check=False)
                logger.info("Opened preview in browser.")
            except Exception:
                pass

    mailer.send_digest(digest, dry_run=dry_run)
    return digest


def main():
    parser = argparse.ArgumentParser(
        description="Live Curator Engine — Monthly London Gig & Comedy Digest"
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Actually send the email digest (default is dry-run mode)",
    )
    parser.add_argument(
        "--preview-html",
        action="store_true",
        help="Save HTML preview to output/preview.html and open in browser",
    )
    parser.add_argument(
        "--refresh-reviews",
        action="store_true",
        help="Force re-scraping fresh reviews from all publications",
    )
    parser.add_argument(
        "--platform",
        type=str,
        choices=["all", "dice", "ticketmaster"],
        default="all",
        help="Filter by ticketing platform (default: all)",
    )
    parser.add_argument(
        "--area",
        type=str,
        default=None,
        help="Filter venues by area (e.g. dalston, hackney, camden, islington, stadiums)",
    )
    parser.add_argument(
        "--venue",
        type=str,
        default=None,
        help="Filter to a single venue (e.g. --venue 'MOTH Club')",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Override digest month name (e.g. November)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Override digest year (e.g. 2026)",
    )

    args = parser.parse_args()
    config = load_config()

    is_dry_run = not args.send_email
    run_pipeline(
        config=config,
        venue_filter=args.venue,
        platform_filter=args.platform,
        area_filter=args.area,
        refresh_reviews=args.refresh_reviews,
        dry_run=is_dry_run,
        preview_html=args.preview_html,
        target_month=args.month,
        target_year=args.year,
    )


if __name__ == "__main__":
    main()
