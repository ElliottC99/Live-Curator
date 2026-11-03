"""Unit tests for VenueManager and atomic YAML persistence."""

import json
import tempfile
from pathlib import Path
import pytest
import yaml

from src.ui.venue_manager import VenueManagerHandler


def test_atomic_save_venues_and_backup():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_yaml = Path(temp_dir) / "venues.yaml"
        initial_data = {
            "venues": [
                {
                    "name": "MOTH Club",
                    "platform": "dice",
                    "area": "Hackney Central",
                    "dice_slug": "moth-club-43ox",
                }
            ]
        }
        with open(temp_yaml, "w", encoding="utf-8") as f:
            yaml.dump(initial_data, f)

        handler = VenueManagerHandler
        handler.venues_yaml_path = temp_yaml

        # Reassign neighbourhood to Dalston
        updated_venues = [
            {
                "name": "MOTH Club",
                "platform": "dice",
                "area": "Dalston",
                "dice_slug": "moth-club-43ox",
            },
            {
                "name": "The Lexington",
                "platform": "dice",
                "area": "Islington & Angel",
                "dice_slug": "the-lexington-7e9b",
            },
        ]

        # Call atomic save
        instance = object.__new__(handler)
        instance.venues_yaml_path = temp_yaml
        instance._atomic_save_venues(updated_venues)

        # Verify backup was created
        backup_file = temp_yaml.with_suffix(".yaml.bak")
        assert backup_file.exists()

        # Verify main YAML file updated correctly
        with open(temp_yaml, "r", encoding="utf-8") as f:
            reloaded = yaml.safe_load(f)

        assert len(reloaded["venues"]) == 2
        assert reloaded["venues"][0]["name"] == "MOTH Club"
        assert reloaded["venues"][0]["area"] == "Dalston"
        assert reloaded["venues"][1]["name"] == "The Lexington"
        assert reloaded["venues"][1]["area"] == "Islington & Angel"
