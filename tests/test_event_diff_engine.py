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


def test_diff_and_record_persists_price_and_sold_out(diff_engine):
    event = Event(
        id="dice-soldout",
        title="Popular Show",
        venue_name="MOTH Club",
        start_time=datetime(2026, 11, 20, 20, 0),
        date_str="Fri 20 Nov",
        ticket_url="https://dice.fm/event/soldout",
        platform="dice",
        price_str="£17.50",
        is_sold_out=True,
    )
    diff_engine.diff_and_record([event], digest_label="November 2026")

    # Verify directly in SQLite
    with diff_engine._get_connection() as conn:
        cursor = conn.execute("SELECT price_str, is_sold_out FROM seen_events WHERE event_id = ?", ("dice:dice-soldout",))
        row = cursor.fetchone()
        assert row is not None
        assert row["price_str"] == "£17.50"
        assert row["is_sold_out"] == 1


def test_idempotent_schema_migration_for_price_and_sold_out(tmp_path):
    import sqlite3
    db_file = tmp_path / "legacy.sqlite"
    # Create legacy schema without price_str and is_sold_out
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE seen_events (
            event_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            venue_name TEXT NOT NULL,
            venue_area TEXT NOT NULL,
            start_time TEXT,
            ticket_url TEXT NOT NULL,
            platform TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            first_digest_label TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    # Initializing EventDiffEngine should perform idempotent migration without crashing
    engine = EventDiffEngine(db_path=db_file)
    with engine._get_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(seen_events)")
        cols = {row["name"] for row in cursor.fetchall()}
        assert "price_str" in cols
        assert "is_sold_out" in cols
