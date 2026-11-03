"""Unit tests for configuration loading and validation."""

from src.core.config import load_config


def test_load_config_venues():
    config = load_config()
    assert len(config.venues) == 9

    venue_names = [v.name for v in config.venues]
    expected_venues = [
        "The Shacklewell Arms",
        "Oslo Hackney",
        "The Waiting Room",
        "MOTH Club",
        "The Victoria",
        "The George Tavern",
        "Hand of Glory",
        "EartH",
        "Next Door Records Two",
    ]
    for expected in expected_venues:
        assert expected in venue_names

    # Check DICE slugs
    for venue in config.venues:
        assert venue.dice_slug != ""
        assert venue.dice_url.startswith("https://dice.fm/venue/")


def test_load_settings():
    config = load_config()
    assert config.app.target_timezone == "Europe/London"
    assert config.reviews.min_aggregate_score_10 == 7.5
    assert config.reviews.min_stars_5 == 4.0
    assert len(config.classification.comedy_keywords) > 0
    assert "comedy" in config.classification.comedy_keywords
    assert "stand-up" in config.classification.comedy_keywords
