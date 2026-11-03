"""Persistent event diffing engine.

Tracks historically seen events in SQLite to identify newly announced shows
in comparison to previous digest runs.
"""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from src.core.models import Event


class EventDiffEngine:
    """Manages historical event persistence and delta identification."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.db_path = project_root / "data" / "cache" / "digest_history.sqlite"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_events (
                    event_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    venue_name TEXT NOT NULL,
                    venue_area TEXT NOT NULL,
                    start_time TEXT,
                    ticket_url TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    first_digest_label TEXT NOT NULL,
                    price_str TEXT,
                    is_sold_out INTEGER DEFAULT 0
                )
                """
            )
            # Idempotent migration for existing databases
            cursor = conn.execute("PRAGMA table_info(seen_events)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            if "price_str" not in existing_cols:
                conn.execute("ALTER TABLE seen_events ADD COLUMN price_str TEXT")
            if "is_sold_out" not in existing_cols:
                conn.execute("ALTER TABLE seen_events ADD COLUMN is_sold_out INTEGER DEFAULT 0")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_seen_events_platform ON seen_events(platform)"
            )
            conn.commit()

    @staticmethod
    def compute_fingerprint(event: Event) -> str:
        """Generate a canonical unique identifier for an event."""
        if event.id:
            return f"{event.platform}:{event.id.strip()}"

        # Canonical hash based on platform, venue, title, and date
        norm_key = f"{event.platform}|{event.venue_name.lower().strip()}|{event.title.lower().strip()}|{event.date_str.lower().strip()}"
        return hashlib.sha256(norm_key.encode("utf-8")).hexdigest()[:24]

    def get_known_event_ids(self) -> Set[str]:
        """Fetch all previously recorded event fingerprints."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT event_id FROM seen_events")
            return {row["event_id"] for row in cursor.fetchall()}

    def diff_and_record(
        self,
        events: List[Event],
        digest_label: str = "",
        mark_initial_as_new: bool = True,
    ) -> List[Event]:
        """
        Compare current events against previously recorded events.
        Sets event.is_new = True for newly announced events and persists them.
        """
        now_iso = datetime.now().isoformat()
        label = digest_label or datetime.now().strftime("%B %Y")

        known_ids = self.get_known_event_ids()
        is_first_run_ever = (len(known_ids) == 0)

        with self._get_connection() as conn:
            for event in events:
                fingerprint = self.compute_fingerprint(event)
                start_iso = event.start_time.isoformat() if event.start_time else ""

                if fingerprint in known_ids:
                    # Already seen in previous runs
                    event.is_new = False
                    conn.execute(
                        """
                        UPDATE seen_events
                        SET last_seen_at = ?,
                            price_str = COALESCE(?, price_str),
                            is_sold_out = ?
                        WHERE event_id = ?
                        """,
                        (now_iso, event.price_str, 1 if event.is_sold_out else 0, fingerprint),
                    )
                else:
                    # Brand new announcement!
                    if is_first_run_ever and not mark_initial_as_new:
                        event.is_new = False
                    else:
                        event.is_new = True

                    event.first_seen_at = datetime.now()
                    conn.execute(
                        """
                        INSERT INTO seen_events (
                            event_id, title, venue_name, venue_area, start_time,
                            ticket_url, platform, first_seen_at, last_seen_at, first_digest_label,
                            price_str, is_sold_out
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fingerprint,
                            event.title,
                            event.venue_name,
                            event.venue_area,
                            start_iso,
                            event.ticket_url,
                            event.platform,
                            now_iso,
                            now_iso,
                            label,
                            event.price_str,
                            1 if event.is_sold_out else 0,
                        ),
                    )
                    known_ids.add(fingerprint)

            conn.commit()

        return events
