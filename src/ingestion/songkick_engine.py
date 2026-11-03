"""Keyless Songkick Schema.org JSON-LD scraper for London stadiums and arenas."""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import requests

from src.core.models import Event, Venue
from src.core.normalizer import extract_normalized_acts, normalize_artist_name

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class SongkickEngine:
    """
    Ingests concert and live music events from major stadiums, arenas, and venues
    via public Schema.org MusicEvent JSON-LD structured data.
    Requires ZERO API keys, accounts, or developer tokens.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })

    def _parse_iso_date(self, date_str: str) -> Optional[datetime]:
        """Parse ISO 8601 date string from Schema.org startDate."""
        if not date_str:
            return None
        cleaned = date_str.strip()
        # Handle trailing Z
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        # Handle +0100 -> +01:00 for older python fromisoformat
        if re.search(r"[+-]\d{4}$", cleaned):
            cleaned = cleaned[:-2] + ":" + cleaned[-2:]

        try:
            return datetime.fromisoformat(cleaned)
        except Exception:
            # Fallback to dateutil or basic YYYY-MM-DD
            try:
                date_part = cleaned.split("T")[0]
                return datetime.strptime(date_part, "%Y-%m-%d")
            except Exception:
                return None

    def _extract_performers(self, item: Dict[str, Any], title: str) -> List[str]:
        """Extract performers from Schema.org item or fall back to title parsing."""
        performers: List[str] = []
        raw_perf = item.get("performer")

        if isinstance(raw_perf, dict):
            name = raw_perf.get("name")
            if name:
                performers.append(str(name).strip())
        elif isinstance(raw_perf, list):
            for p in raw_perf:
                if isinstance(p, dict):
                    name = p.get("name")
                    if name:
                        performers.append(str(name).strip())
                elif isinstance(p, str) and p.strip():
                    performers.append(p.strip())

        if not performers:
            # Parse artist from "Artist Name at Venue Name"
            extracted = extract_normalized_acts(title)
            if extracted:
                performers = extracted
            else:
                clean_title = re.sub(r"\s+at\s+.*$", "", title, flags=re.IGNORECASE).strip()
                if clean_title:
                    performers = [clean_title]

        return performers

    def _extract_price(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract readable price from Schema.org offers."""
        offers = item.get("offers")
        if not offers:
            return None
        if isinstance(offers, dict):
            offers = [offers]

        if isinstance(offers, list) and offers:
            off = offers[0]
            if isinstance(off, dict):
                price = off.get("price")
                curr = off.get("priceCurrency", "GBP")
                symbol = "£" if curr in ["GBP", None] else f"{curr} "
                if price is not None:
                    return f"{symbol}{price}"
        return None

    def parse_json_ld(self, json_ld_text: str, venue: Venue) -> List[Event]:
        """Parse raw JSON-LD text into Event domain entities."""
        events: List[Event] = []
        try:
            data = json.loads(json_ld_text)
        except Exception as e:
            logger.debug(f"Failed to parse JSON-LD for {venue.name}: {e}")
            return events

        # Handle list, single object, or @graph
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = data["@graph"]
            else:
                items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            item_type = item.get("@type", "")
            # Schema.org MusicEvent or Event
            is_event = False
            if isinstance(item_type, str):
                is_event = item_type in ["MusicEvent", "Event", "Festival"]
            elif isinstance(item_type, list):
                is_event = any(t in ["MusicEvent", "Event", "Festival"] for t in item_type)

            if not is_event:
                continue

            title = item.get("name", "").strip()
            if not title:
                continue

            start_date_raw = item.get("startDate", "")
            dt = self._parse_iso_date(start_date_raw)
            if not dt:
                continue

            # Target URL: prefer direct ticket offer link, fallback to concert page URL
            ticket_url = None
            offers = item.get("offers")
            if isinstance(offers, list) and offers and isinstance(offers[0], dict):
                ticket_url = offers[0].get("url")
            elif isinstance(offers, dict):
                ticket_url = offers.get("url")

            if not ticket_url:
                ticket_url = item.get("url")

            if not ticket_url:
                ticket_url = venue.songkick_url or "https://www.songkick.com"

            performers = self._extract_performers(item, title)
            norm_performers = [normalize_artist_name(p) for p in performers if p]
            price_str = self._extract_price(item)
            image_url = item.get("image")
            if isinstance(image_url, list) and image_url:
                image_url = str(image_url[0])
            elif not isinstance(image_url, str):
                image_url = None

            event_id = f"songkick_{abs(hash(ticket_url or title))}"

            event = Event(
                id=event_id,
                title=title,
                venue_name=venue.name,
                venue_area=venue.area,
                start_time=dt,
                date_str=dt.strftime("%a %d %b %Y, %H:%M"),
                performers=performers,
                normalized_performers=norm_performers,
                ticket_url=ticket_url,
                platform="songkick",
                price_str=price_str,
                description=item.get("description"),
                image_url=image_url,
            )
            events.append(event)

        return events

    def fetch_venue_events(self, venue: Venue, max_pages: int = 20) -> List[Event]:
        """
        Fetch and extract events for a specific venue from Songkick.
        Exhaustively paginates through /calendar until <a rel="next"> is None or max_pages is reached.
        """
        raw_url = (venue.songkick_url or "").rstrip("/")
        if not raw_url:
            logger.debug(f"Venue {venue.name} has no songkick_url configured.")
            return []

        # Target full /calendar view
        calendar_url = raw_url if raw_url.endswith("/calendar") else f"{raw_url}/calendar"

        events: List[Event] = []
        seen_signatures: set = set()
        seen_page_signatures: set = set()
        current_page = 1
        current_url = calendar_url

        try:
            while current_page <= max_pages:
                resp = self.session.get(current_url, timeout=12)
                if resp.status_code != 200:
                    # If /calendar gave 404 on page 1, fallback to raw overview page
                    if current_page == 1 and resp.status_code == 404:
                        logger.debug(f"Venue calendar 404 for {venue.name}, falling back to overview: {raw_url}")
                        resp = self.session.get(raw_url, timeout=12)
                        if resp.status_code != 200:
                            break
                    else:
                        break

                soup = BeautifulSoup(resp.text, "html.parser")
                page_events: List[Event] = []
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    if script.string:
                        parsed_events = self.parse_json_ld(script.string, venue)
                        page_events.extend(parsed_events)

                if not page_events:
                    break

                # Loop detection: check if first few events match a previous page
                page_sig = tuple((e.title, e.start_time) for e in page_events[:3])
                if page_sig in seen_page_signatures:
                    break
                seen_page_signatures.add(page_sig)

                # Add new unique events
                for ev in page_events:
                    ev_sig = (normalize_artist_name(ev.title), ev.start_time)
                    if ev_sig not in seen_signatures:
                        seen_signatures.add(ev_sig)
                        events.append(ev)

                # Find next page link (rel="next" or class containing "next")
                next_link = soup.find("a", rel="next") or soup.find("a", class_=lambda c: c and "next" in c.lower())
                if not next_link or not next_link.get("href"):
                    break

                next_href = str(next_link["href"])
                if next_href.startswith("http"):
                    current_url = next_href
                else:
                    current_url = f"https://www.songkick.com{next_href}"

                current_page += 1
                time.sleep(1.2)  # Polite throttle between pages

            logger.info(f"Songkick: Exhaustively harvested {len(events)} events across {current_page} page(s) for {venue.name}")

        except Exception as e:
            logger.warning(f"Failed to fetch Songkick events for {venue.name}: {e}")

        return events

    def fetch_all_venues(self, venues: List[Venue]) -> List[Event]:
        """Fetch events across all configured Songkick venues."""
        target_venues = [
            v for v in venues
            if (v.platform in ["songkick", "both"] or v.songkick_url is not None)
            and v.songkick_url
        ]

        if not target_venues:
            logger.info("No venues configured with Songkick URLs.")
            return []

        logger.info(f"Ingesting keyless concert calendars for {len(target_venues)} stadiums & arenas via Songkick...")
        all_events: List[Event] = []

        for idx, venue in enumerate(target_venues):
            venue_events = self.fetch_venue_events(venue)
            all_events.extend(venue_events)

            if idx < len(target_venues) - 1:
                time.sleep(0.3)

        logger.info(f"Total Songkick stadium/arena events extracted: {len(all_events)}")
        return all_events
