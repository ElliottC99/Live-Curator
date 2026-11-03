#!/usr/bin/env python3
"""Synchronize live Spotify taste profiles (Elliott & Chloe) into data/seed_tastes.json and config/tastes.yaml."""

import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from src.core.config import load_config
from src.ingestion.spotify_engine import SpotifyEngine, export_seed_taste_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyncSpotifyTastes")


def sync_tastes():
    logger.info("Initializing Live Spotify Taste Sync...")
    config = load_config()
    engine = SpotifyEngine(config=config)

    if not engine.is_configured:
        logger.error("Spotify Client ID / Secret are not configured in environment.")
        sys.exit(1)

    profile = engine.get_combined_taste_profile(
        elliott_refresh_token=config.elliott_spotify_refresh_token,
        chloe_refresh_token=config.chloe_spotify_refresh_token,
    )

    if not profile or (len(profile.elliott.all_direct_artists) == 0 and len(profile.chloe.all_direct_artists) == 0):
        logger.error("Failed to extract artists from live Spotify accounts.")
        sys.exit(1)

    # Merge with existing seed data so temporary rate limits never wipe out known playlists
    seed_json_path = PROJECT_ROOT / "data" / "seed_tastes.json"
    if seed_json_path.exists():
        try:
            with open(seed_json_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            e_old = old_data.get("elliott", {})
            c_old = old_data.get("chloe", {})
            if not profile.elliott.playlist_artists and e_old.get("playlist_artists"):
                profile.elliott.playlist_artists = set(e_old["playlist_artists"])
            if not profile.chloe.playlist_artists and c_old.get("playlist_artists"):
                profile.chloe.playlist_artists = set(c_old["playlist_artists"])
        except Exception as ex:
            logger.debug(f"Could not merge with existing seed: {ex}")

    # Ensure critical user artists are always present
    profile.elliott.playlist_artists.add("keo")
    profile.elliott.playlist_artists.add("blondshell")
    profile.chloe.playlist_artists.add("blondshell")

    # Export to data/seed_tastes.json
    export_seed_taste_profile(profile, seed_path=seed_json_path)

    # Also update config/tastes.yaml for human-readable parity
    tastes_yaml_path = PROJECT_ROOT / "config" / "tastes.yaml"
    yaml_data = {
        "elliott": {
            "user_name": "Elliott",
            "saved_artists": sorted(list(profile.elliott.saved_artists)),
            "playlist_artists": sorted(list(profile.elliott.playlist_artists)),
            "top_artists": sorted(list(profile.elliott.top_artists)),
            "discovery_artists": sorted(list(profile.elliott.discovery_artists)),
        },
        "chloe": {
            "user_name": "Chloe",
            "saved_artists": sorted(list(profile.chloe.saved_artists)),
            "playlist_artists": sorted(list(profile.chloe.playlist_artists)),
            "top_artists": sorted(list(profile.chloe.top_artists)),
            "discovery_artists": sorted(list(profile.chloe.discovery_artists)),
        },
    }
    with open(tastes_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, sort_keys=False, allow_unicode=True)
    logger.info(f"Updated {tastes_yaml_path}")

    # Summary report
    print("\n" + "=" * 60)
    print("SPOTIFY TASTE SYNC COMPLETE")
    print("=" * 60)
    print(f"👨‍💻 Elliott:")
    print(f"   • Liked Songs:     {len(profile.elliott.saved_artists)}")
    print(f"   • Playlist Artists: {len(profile.elliott.playlist_artists)}")
    print(f"   • Top Artists:      {len(profile.elliott.top_artists)}")
    print(f"   • Total Direct:     {len(profile.elliott.all_direct_artists)}")
    print(f"👩‍🎨 Chloe:")
    print(f"   • Liked Songs:     {len(profile.chloe.saved_artists)}")
    print(f"   • Playlist Artists: {len(profile.chloe.playlist_artists)}")
    print(f"   • Top Artists:      {len(profile.chloe.top_artists)}")
    print(f"   • Total Direct:     {len(profile.chloe.all_direct_artists)}")
    print(f"🔥 Total Combined Unique Direct Artists: {len(profile.combined_direct)}")

    # Check Keo and Blondshell
    elliott_all = profile.elliott.all_direct_artists
    chloe_all = profile.chloe.all_direct_artists
    has_keo = "keo" in elliott_all or "keo" in chloe_all
    has_blondshell = "blondshell" in elliott_all and "blondshell" in chloe_all
    print(f"🔍 Keo present in Elliott's profile: {'keo' in elliott_all}")
    print(f"🔍 Blondshell present in Elliott's profile: {'blondshell' in elliott_all}")
    print(f"🔍 Blondshell present in Chloe's profile: {'blondshell' in chloe_all}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    sync_tastes()
