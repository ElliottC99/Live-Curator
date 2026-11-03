#!/usr/bin/env python3
"""
Standalone test script to poll and inspect critical music reviews.
Usage:
    .venv/bin/python3 scripts/test_reviews.py
    .venv/bin/python3 scripts/test_reviews.py --refresh
    .venv/bin/python3 scripts/test_reviews.py --limit 15
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import load_config
from src.ingestion.review_parser import ReviewAggregator, ReviewDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ReviewsTest")


def main():
    parser = argparse.ArgumentParser(description="Test and inspect critical music reviews")
    parser.add_argument("--refresh", action="store_true", help="Fetch fresh reviews from publications")
    parser.add_argument("--limit", type=int, default=15, help="Number of reviews to display")
    args = parser.parse_args()

    config = load_config()
    db_path = PROJECT_ROOT / "data" / "cache" / "reviews.sqlite"

    aggregator = ReviewAggregator(
        db_path=db_path,
        guardian_api_key=config.guardian_api_key,
        min_aggregate_score=config.reviews.min_aggregate_score_10,
        min_stars=config.reviews.min_stars_5,
    )

    if args.refresh or not db_path.exists():
        logger.info("Polling British music publications (Guardian, ADM, DIY, Dork, TLOBF, NME, L&Q)...")
        reviews = aggregator.update_all_reviews()
        logger.info(f"Done! Ingested {len(reviews)} reviews.")

    recommended_artists = aggregator.get_recommended_artists()
    logger.info(f"Found {len(recommended_artists)} recommended artists in SQLite cache (score >= 4★ or >= 7.5/10).\n")

    print("=" * 75)
    print(f"SAMPLE HIGHLY-RATED ARTISTS & REVIEWS (Top {args.limit}):")
    print("=" * 75)

    count = 0
    for norm_artist in list(recommended_artists)[:args.limit]:
        revs = aggregator.db.get_reviews_for_artist(norm_artist)
        if revs:
            top_rev = revs[0]
            count += 1
            score_display = f"{top_rev.score}/{top_rev.max_score}" if top_rev.score else "Recommended"
            print(f"{count:02d}. {top_rev.artist_name} [{score_display}] - {top_rev.publication}")
            if top_rev.album_title:
                print(f"    Album: {top_rev.album_title}")
            if top_rev.url:
                print(f"    Link:  {top_rev.url}")
            print("-" * 75)


if __name__ == "__main__":
    main()
