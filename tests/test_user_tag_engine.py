"""Unit tests for the UserTagEngine SQLite persistence."""

from datetime import datetime
import pytest

from src.core.models import Event
from src.processing.user_tag_engine import UserTagEngine


@pytest.fixture
def tag_engine(tmp_path):
    db_file = tmp_path / "test_user_tags.sqlite"
    return UserTagEngine(db_file)


def test_set_and_get_user_tag(tag_engine):
    tag_engine.set_tag("event_123", "club_night", "Friday Night Rave")
    assert tag_engine.get_tag("event_123") == "club_night"

    # Update tag to live_gig
    tag_engine.set_tag("event_123", "live_gig")
    assert tag_engine.get_tag("event_123") == "live_gig"


def test_get_all_tags(tag_engine):
    tag_engine.set_tag("e1", "club_night")
    tag_engine.set_tag("e2", "live_gig")
    tags = tag_engine.get_all_tags()
    assert tags == {"e1": "club_night", "e2": "live_gig"}


def test_remove_tag(tag_engine):
    tag_engine.set_tag("e3", "club_night")
    assert tag_engine.get_tag("e3") == "club_night"
    tag_engine.remove_tag("e3")
    assert tag_engine.get_tag("e3") is None


def test_canonical_id_generation():
    dt = datetime(2026, 11, 20, 23, 0)
    e = Event(
        title="Late Disco",
        venue_name="MOTH Club",
        start_time=dt,
        date_str="Fri 20 Nov 2026, 23:00",
        ticket_url="https://dice.fm/e/late-disco",
    )
    cid = UserTagEngine.get_canonical_id(e)
    assert cid.startswith("ev_")
