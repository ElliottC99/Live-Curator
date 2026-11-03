"""Unit tests for the Ticketmaster Discovery API engine."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from src.core.models import Venue
from src.ingestion.ticketmaster_engine import TicketmasterEngine


@pytest.fixture
def sample_tm_venue():
    return Venue(
        name="Wembley Stadium",
        platform="ticketmaster",
        tm_venue_id="KovZpZAJledA",
        tm_keyword="Wembley Stadium",
        area="Wembley",
    )


@pytest.fixture
def sample_tm_api_event():
    return {
        "id": "tm123456",
        "name": "Oasis '25 Live",
        "url": "https://www.ticketmaster.co.uk/event/tm123456",
        "dates": {
            "start": {
                "localDate": "2026-11-20",
                "localTime": "18:00:00",
                "dateTime": "2026-11-20T18:00:00Z",
            }
        },
        "priceRanges": [
            {
                "currency": "GBP",
                "min": 75.0,
                "max": 150.0,
            }
        ],
        "_embedded": {
            "attractions": [
                {"name": "Oasis"},
                {"name": "Cast"},
            ]
        },
        "pleaseNote": "Strict age restrictions apply.",
    }


class TestTicketmasterEngine:
    """Test Ticketmaster Discovery API client and event parsing."""

    def test_is_configured(self):
        engine_no_key = TicketmasterEngine(api_key="")
        assert engine_no_key.is_configured is False

        engine_with_key = TicketmasterEngine(api_key="valid-test-key")
        assert engine_with_key.is_configured is True

    def test_init_with_config_object(self):
        from src.core.config import Config
        cfg_without_key = Config(ticketmaster_api_key=None)
        engine1 = TicketmasterEngine(cfg_without_key)
        assert engine1.is_configured is False
        assert engine1.fetch_all_venues([Venue(name="Wembley Stadium", platform="ticketmaster")]) == []

        cfg_with_key = Config(ticketmaster_api_key="test-key-123")
        engine2 = TicketmasterEngine(cfg_with_key)
        assert engine2.is_configured is True
        assert engine2.api_key == "test-key-123"

    def test_format_price_range(self):
        engine = TicketmasterEngine(api_key="test")
        pr_range = [{"currency": "GBP", "min": 45.0, "max": 95.0}]
        assert engine._format_price_range(pr_range) == "£45 - £95"

        pr_min_only = [{"currency": "GBP", "min": 50.0}]
        assert engine._format_price_range(pr_min_only) == "From £50"

        pr_empty = []
        assert engine._format_price_range(pr_empty) is None

    def test_parse_event_with_attractions(self, sample_tm_venue, sample_tm_api_event):
        engine = TicketmasterEngine(api_key="test")
        event = engine.parse_event(sample_tm_api_event, sample_tm_venue)

        assert event is not None
        assert event.id == "tm123456"
        assert event.title == "Oasis '25 Live"
        assert event.venue_name == "Wembley Stadium"
        assert event.venue_area == "Wembley"
        assert event.platform == "ticketmaster"
        assert event.ticket_url == "https://www.ticketmaster.co.uk/event/tm123456"
        assert event.price_str == "£75 - £150"
        assert "Oasis" in event.performers
        assert "Cast" in event.performers
        assert "oasis" in event.normalized_performers

    def test_parse_event_without_attractions_splits_title(self, sample_tm_venue):
        engine = TicketmasterEngine(api_key="test")
        raw_event = {
            "id": "tm789",
            "name": "Fontaines D.C. + Wunderhorse",
            "url": "https://www.ticketmaster.co.uk/event/tm789",
            "dates": {
                "start": {
                    "localDate": "2026-11-15",
                    "localTime": "19:30:00",
                }
            },
        }
        event = engine.parse_event(raw_event, sample_tm_venue)

        assert event is not None
        assert "Fontaines D.C." in event.performers
        assert "Wunderhorse" in event.performers

    @patch("requests.Session.get")
    def test_fetch_venue_events_success(self, mock_get, sample_tm_venue, sample_tm_api_event):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {"events": [sample_tm_api_event]}
        }
        mock_get.return_value = mock_response

        engine = TicketmasterEngine(api_key="test-api-key")
        events = engine.fetch_venue_events(sample_tm_venue, target_month=11, target_year=2026)

        assert len(events) == 1
        assert events[0].title == "Oasis '25 Live"
        mock_get.assert_called_once()
        call_params = mock_get.call_args[1]["params"]
        assert call_params["classificationName"] == "Music"
        assert call_params["venueId"] == "KovZpZAJledA"
        assert call_params["apikey"] == "test-api-key"
