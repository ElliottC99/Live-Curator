"""Unit tests for the master pipeline orchestrator (main.py)."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from src.core.config import Config
from src.core.models import CombinedTasteProfile, UserTasteProfile, Event, Venue
from main import run_pipeline


@pytest.fixture
def mock_config():
    venues = [
        Venue(name="MOTH Club", dice_slug="moth-club-43ox", area="hackney", platform="dice"),
        Venue(name="Wembley Stadium", area="stadiums", platform="ticketmaster", tm_keyword="Wembley Stadium"),
        Venue(name="The Lexington", dice_slug="the-lexington-7gqy", area="islington", platform="dice"),
    ]
    return Config(
        venues=venues,
    )


@patch("main.SpotifyEngine")
@patch("main.ReviewAggregator")
@patch("main.DiceScraper")
@patch("main.TicketmasterEngine")
@patch("main.DigestMailer")
def test_run_pipeline_platform_filter_dice(
    mock_mailer_cls,
    mock_tm_cls,
    mock_dice_cls,
    mock_reviews_cls,
    mock_spotify_cls,
    mock_config,
):
    mock_spotify = MagicMock()
    mock_spotify.get_combined_taste_profile.return_value = CombinedTasteProfile(
        elliott=UserTasteProfile(user_name="Elliott"),
        chloe=UserTasteProfile(user_name="Chloe"),
    )
    mock_spotify_cls.return_value = mock_spotify

    mock_reviews = MagicMock()
    mock_reviews.get_recommended_artists.return_value = {}
    mock_reviews_cls.return_value = mock_reviews

    mock_dice = MagicMock()
    mock_dice.scrape_all_venues.return_value = [
        Event(
            title="Band A",
            performers=["Band A"],
            venue_name="MOTH Club",
            date_str="Fri 20 Nov",
            start_time=datetime.now(),
            price_str="£15.00",
            ticket_url="https://dice.fm/event/123",
            platform="dice",
        )
    ]
    mock_dice_cls.return_value = mock_dice

    mock_tm = MagicMock()
    mock_tm.fetch_all_venues.return_value = []
    mock_tm_cls.return_value = mock_tm

    digest = run_pipeline(
        config=mock_config,
        platform_filter="dice",
        dry_run=True,
        preview_html=False,
    )

    # Dice scraper should have been called with only dice venues (MOTH Club, The Lexington)
    assert mock_dice.scrape_all_venues.called
    called_venues = mock_dice.scrape_all_venues.call_args[0][0]
    assert len(called_venues) == 2
    assert all(v.platform == "dice" for v in called_venues)

    # Ticketmaster scraper should NOT have been called
    assert not mock_tm.fetch_all_venues.called
    assert digest.total_events_scraped == 1


@patch("main.SpotifyEngine")
@patch("main.ReviewAggregator")
@patch("main.DiceScraper")
@patch("main.TicketmasterEngine")
@patch("main.DigestMailer")
def test_run_pipeline_platform_filter_ticketmaster(
    mock_mailer_cls,
    mock_tm_cls,
    mock_dice_cls,
    mock_reviews_cls,
    mock_spotify_cls,
    mock_config,
):
    mock_spotify = MagicMock()
    mock_spotify.get_combined_taste_profile.return_value = CombinedTasteProfile(
        elliott=UserTasteProfile(user_name="Elliott"),
        chloe=UserTasteProfile(user_name="Chloe"),
    )
    mock_spotify_cls.return_value = mock_spotify

    mock_reviews = MagicMock()
    mock_reviews.get_recommended_artists.return_value = {}
    mock_reviews_cls.return_value = mock_reviews

    mock_tm = MagicMock()
    mock_tm.fetch_all_venues.return_value = [
        Event(
            title="Oasis Live",
            performers=["Oasis"],
            venue_name="Wembley Stadium",
            date_str="Sat 25 Jul",
            start_time=datetime.now(),
            price_str="£80.00",
            ticket_url="https://ticketmaster.co.uk/event/999",
            platform="ticketmaster",
        )
    ]
    mock_tm_cls.return_value = mock_tm

    mock_dice = MagicMock()
    mock_dice_cls.return_value = mock_dice

    digest = run_pipeline(
        config=mock_config,
        platform_filter="ticketmaster",
        dry_run=True,
        preview_html=False,
    )

    # TM engine should have been called with Wembley Stadium
    assert mock_tm.fetch_all_venues.called
    called_venues = mock_tm.fetch_all_venues.call_args[0][0]
    assert len(called_venues) == 1
    assert called_venues[0].name == "Wembley Stadium"

    # Dice scraper should not have been called
    assert not mock_dice.scrape_all_venues.called
    assert digest.total_events_scraped == 1


@patch("main.SpotifyEngine")
@patch("main.ReviewAggregator")
@patch("main.DiceScraper")
@patch("main.TicketmasterEngine")
@patch("main.DigestMailer")
def test_run_pipeline_area_filter(
    mock_mailer_cls,
    mock_tm_cls,
    mock_dice_cls,
    mock_reviews_cls,
    mock_spotify_cls,
    mock_config,
):
    mock_spotify = MagicMock()
    mock_spotify.get_combined_taste_profile.return_value = CombinedTasteProfile(
        elliott=UserTasteProfile(user_name="Elliott"),
        chloe=UserTasteProfile(user_name="Chloe"),
    )
    mock_spotify_cls.return_value = mock_spotify

    mock_reviews = MagicMock()
    mock_reviews.get_recommended_artists.return_value = {}
    mock_reviews_cls.return_value = mock_reviews

    mock_dice = MagicMock()
    mock_dice.scrape_all_venues.return_value = []
    mock_dice_cls.return_value = mock_dice

    digest = run_pipeline(
        config=mock_config,
        area_filter="islington",
        dry_run=True,
        preview_html=False,
    )

    assert mock_dice.scrape_all_venues.called
    called_venues = mock_dice.scrape_all_venues.call_args[0][0]
    assert len(called_venues) == 1
    assert called_venues[0].name == "The Lexington"


@patch("main.SpotifyEngine")
@patch("main.ReviewAggregator")
@patch("main.DiceScraper")
@patch("main.TicketmasterEngine")
@patch("main.SongkickEngine")
@patch("main.DigestMailer")
def test_run_pipeline_fallback_to_seed_events(
    mock_mailer_cls,
    mock_sk_cls,
    mock_tm_cls,
    mock_dice_cls,
    mock_reviews_cls,
    mock_spotify_cls,
    mock_config,
):
    mock_spotify = MagicMock()
    mock_spotify.get_combined_taste_profile.return_value = CombinedTasteProfile(
        elliott=UserTasteProfile(user_name="Elliott"),
        chloe=UserTasteProfile(user_name="Chloe"),
    )
    mock_spotify_cls.return_value = mock_spotify

    mock_reviews = MagicMock()
    mock_reviews.get_recommended_artists.return_value = {}
    mock_reviews_cls.return_value = mock_reviews

    mock_dice = MagicMock()
    mock_dice.scrape_all_venues.return_value = []
    mock_dice_cls.return_value = mock_dice

    mock_tm = MagicMock()
    mock_tm.fetch_all_venues.return_value = []
    mock_tm_cls.return_value = mock_tm

    mock_sk = MagicMock()
    mock_sk.fetch_all_venues.return_value = []
    mock_sk_cls.return_value = mock_sk

    digest = run_pipeline(
        config=mock_config,
        dry_run=True,
        preview_html=False,
    )

    # When all scrapers return empty and no filters were applied, fallback loads data/seed_events.json
    assert digest.total_events_scraped > 0

