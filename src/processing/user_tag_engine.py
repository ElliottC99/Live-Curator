"""Persistent SQLite storage for user-customized event tags (e.g., Club Nights vs Live Gigs)."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.core.models import Event

logger = logging.getLogger(__name__)

DEFAULT_TAGS_DB = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "user_event_tags.sqlite"


class UserTagEngine:
    """
    Manages persistent user overrides for event categorisation.
    Remembers whether a user designated an event as a Club Night, Live Gig, or Comedy.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_TAGS_DB
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_tags (
                    event_id TEXT PRIMARY KEY,
                    title TEXT,
                    category TEXT NOT NULL,
                    tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @staticmethod
    def get_canonical_id(event: Event) -> str:
        """Derive a deterministic ID for an event across runs."""
        if event.id:
            return event.id
        date_str = event.start_time.strftime("%Y-%m-%d")
        raw = f"{event.venue_name.lower().strip()}_{event.title.lower().strip()}_{date_str}"
        return f"ev_{abs(hash(raw))}"

    def get_tag(self, event_id: str) -> Optional[str]:
        """Fetch user tag for a specific event ID ('club_night', 'live_gig', 'comedy')."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT category FROM user_tags WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_tags(self) -> Dict[str, str]:
        """Fetch all user tags as a dictionary mapping event_id -> category."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT event_id, category FROM user_tags")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def set_tag(self, event_id: str, category: str, title: Optional[str] = None):
        """Set or update user tag for an event."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_tags (event_id, title, category, tagged_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    category = excluded.category,
                    title = COALESCE(excluded.title, user_tags.title),
                    tagged_at = excluded.tagged_at
                """,
                (event_id, title or "", category, datetime.now().isoformat()),
            )
            conn.commit()
        logger.info(f"Saved user tag: event_id={event_id} -> category={category}")

    def remove_tag(self, event_id: str):
        """Remove user tag override for an event."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM user_tags WHERE event_id = ?", (event_id,))
            conn.commit()
        logger.info(f"Removed user tag for event_id={event_id}")
