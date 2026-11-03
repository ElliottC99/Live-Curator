"""Unit tests for EventDiffEngine."""

import tempfile
from datetime import datetime
from pathlib import Path
import pytest

from src.core.models import Event
from src.processing.event_diff_engine import EventDiffEngine


@pytest.fixture
def diff_engine():
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        temp_path = Path(f.name)
    engine = EventDiffEngine(db_path=temp_path)
    yield engine
    if temp_path.exists():
        temp_path.unlink()


def test_first_run_marks_new_events(diff_engine):
    event1 = Event(
        id="dice-1",
        title="Band A",
        venue_name="MOTH Club",
        start_time=datetime(2026, 11, 10, 19, 30),
        date_str="Tue 10 Nov",
        ticket_url="https://dice.fm/event/1",
        platform="dice",
    )
    event2 = Event(
        id="dice-2",
        title="Band B",
        venue_name="The Lexington",
        start_time=datetime(2026, 11, 12, 19, 30),
        date_str="Thu 12 Nov",
        ticket_url="https://dice.fm/event/2",
        platform="dice",
    )

    results = diff_engine.diff_and_record([event1, event2], digest_label="November 2026")
    assert all(e.is_new for e in results)
    assert len(diff_engine.get_known_event_ids()) == 2


def test_subsequent_run_identifies_deltas(diff_engine):
    event1 = Event(
        id="dice-1",
        title="Band A",
        venue_name="MOTH Club",
        start_time=datetime(2026, 11, 10, 19, 30),
        date_str="Tue 10 Nov",
        ticket_url="https://dice.fm/event/1",
        platform="dice",
    )
    # First run records event1
    diff_engine.diff_and_record([event1], digest_label="November 2026")

    # Second run has event1 again, plus newly added event3
    event1_repeat = Event(
        id="dice-1",
        title="Band A",
        venue_name="MOTH Club",
        start_time=datetime(2026, 11, 10, 19, 30),
        date_str="Tue 10 Nov",
        ticket_url="https://dice.fm/event/1",
        platform="dice",
    )
    event3_new = Event(
        id="dice-3",
        title="Band C Just Announced",
        venue_name="MOTH Club",
        start_time=datetime(2026, 12, 5, 20, 0),
        date_str="Sat 05 Dec",
        ticket_url="https://dice.fm/event/3",
        platform="dice",
    )

    results = diff_engine.diff_and_record([event1_repeat, event3_new], digest_label="December 2026")

    # event1 was already seen, so is_new must be False
    assert results[0].is_new is False
    # event3 is new, so is_new must be True
    assert results[1].is_new is True


def test_fingerprint_generation_without_id(diff_engine):
    event_no_id = Event(
        title="Secret Headliner",
        venue_name="Roundhouse",
        start_time=datetime(2027, 4, 15, 19, 0),
        date_str="Thu 15 Apr",
        ticket_url="https://dice.fm/event/secret",
        platform="dice",
    )
    fp = diff_engine.compute_fingerprint(event_no_id)
    assert isinstance(fp, str) and len(fp) > 10
