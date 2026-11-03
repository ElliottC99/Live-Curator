"""Unit tests for the keyless Songkick Schema.org JSON-LD ingestion engine."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from src.core.models import Venue
from src.ingestion.songkick_engine import SongkickEngine


@pytest.fixture
def sample_venue():
    return Venue(
        name="Wembley Stadium",
        platform="songkick",
        songkick_url="https://www.songkick.com/venues/33134-wembley-stadium",
        area="Wembley",
        address="London HA9 0WS",
        genre_focus=["stadium", "rock", "pop"],
    )


@pytest.fixture
def sample_json_ld():
    return json.dumps([
        {
            "@context": "http://schema.org",
            "@type": "MusicEvent",
            "name": "Taylor Swift at Wembley Stadium (August 15, 2026)",
            "url": "https://www.songkick.com/concerts/41001-taylor-swift",
            "startDate": "2026-08-15T18:00:00+0100",
            "location": {
                "@type": "Place",
                "name": "Wembley Stadium",
                "address": "London",
            },
            "performer": [
                {"@type": "MusicGroup", "name": "Taylor Swift"},
                {"@type": "MusicGroup", "name": "Paramore"},
            ],
            "offers": [
                {
                    "@type": "Offer",
                    "url": "https://www.songkick.com/tickets/41001",
                    "price": "85.00",
                    "priceCurrency": "GBP",
                }
            ],
        },
        {
            "@context": "http://schema.org",
            "@type": "SportsEvent",
            "name": "FA Cup Final",
            "startDate": "2026-05-23T15:00:00+0100",
        },
        {
            "@context": "http://schema.org",
            "@type": "MusicEvent",
            "name": "Foo Fighters: Everything or Nothing at All Tour",
            "url": "https://www.songkick.com/concerts/41002-foo-fighters",
            "startDate": "2026-06-20T17:30:00Z",
            "performer": {"@type": "MusicGroup", "name": "Foo Fighters"},
        },
    ])


def test_parse_json_ld_filters_music_and_extracts_fields(sample_venue, sample_json_ld):
    engine = SongkickEngine()
    events = engine.parse_json_ld(sample_json_ld, sample_venue)

    # 3 items in JSON, but 1 is SportsEvent -> exactly 2 MusicEvents returned
    assert len(events) == 2

    e1 = events[0]
    assert e1.title == "Taylor Swift at Wembley Stadium (August 15, 2026)"
    assert e1.venue_name == "Wembley Stadium"
    assert e1.venue_area == "Wembley"
    assert "Taylor Swift" in e1.performers
    assert "Paramore" in e1.performers
    assert e1.start_time.year == 2026
    assert e1.start_time.month == 8
    assert e1.start_time.day == 15
    assert e1.ticket_url == "https://www.songkick.com/tickets/41001"
    assert e1.price_str == "£85.00"
    assert e1.platform == "songkick"

    e2 = events[1]
    assert "Foo Fighters" in e2.performers
    assert e2.start_time.year == 2026
    assert e2.start_time.month == 6
    assert e2.ticket_url == "https://www.songkick.com/concerts/41002-foo-fighters"


def test_parse_json_ld_graph_format(sample_venue):
    graph_data = json.dumps({
        "@context": "http://schema.org",
        "@graph": [
            {
                "@type": "MusicEvent",
                "name": "The Rolling Stones live in London",
                "startDate": "2026-07-10T19:00:00+01:00",
                "url": "https://www.songkick.com/concerts/stones",
                "performer": [{"name": "The Rolling Stones"}],
            }
        ]
    })
    engine = SongkickEngine()
    events = engine.parse_json_ld(graph_data, sample_venue)
    assert len(events) == 1
    assert events[0].title == "The Rolling Stones live in London"
    assert events[0].performers == ["The Rolling Stones"]


def test_parse_json_ld_malformed_ignored(sample_venue):
    engine = SongkickEngine()
    assert engine.parse_json_ld("not valid json", sample_venue) == []
    assert engine.parse_json_ld("{}", sample_venue) == []


def test_fetch_venue_events_extracts_from_html(sample_venue, sample_json_ld):
    engine = SongkickEngine()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = f"""
    <html>
      <head>
        <script type="application/ld+json">
          {sample_json_ld}
        </script>
      </head>
      <body>Concerts list</body>
    </html>
    """

    with patch.object(engine.session, "get", return_value=mock_resp):
        events = engine.fetch_venue_events(sample_venue)
        assert len(events) == 2
        assert events[0].title.startswith("Taylor Swift")


def test_fetch_all_venues_skips_venues_without_songkick_url():
    v1 = Venue(name="Venue A", platform="dice", dice_slug="venue-a")
    v2 = Venue(name="Venue B", platform="songkick", songkick_url="https://songkick.com/b")
    engine = SongkickEngine()

    with patch.object(engine, "fetch_venue_events", return_value=[]) as mock_fetch:
        engine.fetch_all_venues([v1, v2])
        # Only v2 should be queried
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0].name == "Venue B"
