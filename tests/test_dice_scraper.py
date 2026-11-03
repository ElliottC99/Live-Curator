"""Unit tests for the DICE scraper parser and data conversion."""

from datetime import datetime
from src.core.models import Venue
from src.ingestion.dice_scraper import DiceScraper


def test_parse_event_from_dict_success():
    scraper = DiceScraper(headless=True)
    venue = Venue(
        name="The Shacklewell Arms",
        dice_slug="the-shacklewell-arms-z82z",
        area="Dalston",
    )

    raw_event = {
        "id": "event_12345",
        "name": "Pond + Warmduscher",
        "dates": {
            "event_start_date": "2026-11-15T20:00:00+00:00",
            "event_end_date": "2026-11-15T23:00:00+00:00",
            "timezone": "Europe/London",
        },
        "price": {
            "currency": "GBP",
            "amount": 1850,
        },
        "images": {
            "square": "https://example.com/pond.jpg"
        },
        "event_tag": "Live Music",
    }

    event = scraper._parse_event_from_dict(raw_event, venue)
    assert event is not None
    assert event.id == "event_12345"
    assert event.title == "Pond + Warmduscher"
    assert event.venue_name == "The Shacklewell Arms"
    assert event.venue_area == "Dalston"
    assert event.price_str == "£18.50"
    assert event.performers == ["Pond", "Warmduscher"]
    assert event.normalized_performers == ["pond", "warmduscher"]
    assert event.ticket_url == "https://dice.fm/event/event_12345"
    assert event.image_url == "https://example.com/pond.jpg"


def test_parse_free_event():
    scraper = DiceScraper(headless=True)
    venue = Venue(name="MOTH Club", dice_slug="moth-club-43ox")

    raw_event = {
        "id": "free_event",
        "name": "Open Mic Comedy",
        "dates": {
            "event_start_date": "2026-11-10T19:30:00+00:00",
        },
        "price": {
            "currency": "GBP",
            "amount": 0,
        },
    }

    event = scraper._parse_event_from_dict(raw_event, venue)
    assert event is not None
    assert event.price_str == "Free"


def test_parse_missing_dates():
    scraper = DiceScraper(headless=True)
    venue = Venue(name="EartH", dice_slug="earth-76a7")

    raw_event = {
        "id": "bad_event",
        "name": "Ghost Gig",
        "dates": {},
    }

    event = scraper._parse_event_from_dict(raw_event, venue)
    assert event is None
