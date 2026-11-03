"""Ticketmaster Discovery API v2 client for stadium and arena live music events."""

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests

from src.core.models import Event, Venue
from src.core.normalizer import extract_normalized_acts, normalize_artist_name, split_lineup

logger = logging.getLogger(__name__)

TM_DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"


class TicketmasterEngine:
    """
    Ingests live music and comedy events from major stadiums, arenas, and outdoor grounds
    via the Ticketmaster Discovery API v2.
    """

    def __init__(
        self,
        api_key: Optional[Any] = None,
        config: Optional[Any] = None,
    ):
        # Support passing Config object as the first positional argument
        if api_key is not None and not isinstance(api_key, str):
            config = api_key
            api_key = None

        if config is not None:
            self.api_key = api_key or getattr(config, "ticketmaster_api_key", None)
        else:
            self.api_key = api_key or os.getenv("TICKETMASTER_API_KEY")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LiveCurator/1.0 (+https://github.com/LiveCurator)",
            "Accept": "application/json",
        })

    @property
    def is_configured(self) -> bool:
        return bool(isinstance(self.api_key, str) and self.api_key.strip())

    def _format_price_range(self, price_ranges: List[Dict[str, Any]]) -> Optional[str]:
        """Format Ticketmaster price ranges into readable string."""
        if not price_ranges:
            return None

        pr = price_ranges[0]
        currency = "£" if pr.get("currency") in ["GBP", None] else f"{pr.get('currency')} "
        min_p = pr.get("min")
        max_p = pr.get("max")

        if min_p is not None and max_p is not None and min_p != max_p:
            return f"{currency}{min_p:g} - {currency}{max_p:g}"
        elif min_p is not None:
            return f"From {currency}{min_p:g}"
        elif max_p is not None:
            return f"Up to {currency}{max_p:g}"
        return None

    def parse_event(self, item: Dict[str, Any], venue: Venue) -> Optional[Event]:
        """Convert a Ticketmaster API event item into an Event domain object."""
        try:
            event_id = item.get("id")
            title = item.get("name", "").strip()
            ticket_url = item.get("url", "")
            if not title or not ticket_url:
                return None

            # Dates and Times
            dates_info = item.get("dates", {})
            start_info = dates_info.get("start", {})
            date_time_str = start_info.get("dateTime")
            local_date = start_info.get("localDate")
            local_time = start_info.get("localTime", "19:00:00")

            if date_time_str:
                clean_iso = date_time_str.replace("Z", "+00:00")
                try:
                    start_dt = datetime.fromisoformat(clean_iso)
                except ValueError:
                    start_dt = datetime.strptime(f"{local_date} {local_time[:5]}", "%Y-%m-%d %H:%M")
            elif local_date:
                start_dt = datetime.strptime(f"{local_date} {local_time[:5]}", "%Y-%m-%d %H:%M")
            else:
                start_dt = datetime.now()

            # Formatted date string
            date_str = start_dt.strftime("%a %d %b %Y, %H:%M")

            # Extract Performers / Attractions
            performers: List[str] = []
            attractions = item.get("_embedded", {}).get("attractions", [])
            for att in attractions:
                att_name = att.get("name", "").strip()
                if att_name and att_name not in performers:
                    performers.append(att_name)

            if not performers:
                performers = split_lineup(title)

            normalized_acts = [normalize_artist_name(p) for p in performers if normalize_artist_name(p)]

            # Price
            price_str = self._format_price_range(item.get("priceRanges", []))

            # Status & Sold out check
            status_code = str(item.get("dates", {}).get("status", {}).get("code", "")).lower()
            is_sold_out = (status_code in ["soldout", "offsale"] or bool(re.search(r"\b(sold\s*out)\b", title, re.IGNORECASE)))

            # Description
            description = item.get("info") or item.get("pleaseNote") or ""

            return Event(
                id=event_id,
                title=title,
                venue_name=venue.name,
                venue_area=venue.area,
                start_time=start_dt,
                date_str=date_str,
                performers=performers,
                normalized_performers=normalized_acts,
                ticket_url=ticket_url,
                platform="ticketmaster",
                price_str=price_str,
                is_sold_out=is_sold_out,
                description=description[:300] if description else None,
            )
        except Exception as e:
            logger.debug(f"Error parsing Ticketmaster event: {e}")
            return None

    def fetch_venue_events(
        self,
        venue: Venue,
        target_month: Optional[int] = None,
        target_year: Optional[int] = None,
    ) -> List[Event]:
        """Fetch upcoming live music concerts for a specific venue from Ticketmaster."""
        if not self.is_configured:
            logger.debug(f"Ticketmaster API key not configured. Skipping {venue.name}.")
            return []

        events: List[Event] = []
        now = datetime.now()
        month = target_month or now.month
        year = target_year or now.year

        # Define month search bounds in ISO 8601
        start_date = f"{year:04d}-{month:02d}-01T00:00:00Z"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01T00:00:00Z"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01T00:00:00Z"

        params: Dict[str, Any] = {
            "apikey": self.api_key,
            "countryCode": "GB",
            "classificationName": "Music",  # Exclude football and sporting fixtures
            "startDateTime": start_date,
            "endDateTime": end_date,
            "size": 50,
            "sort": "date,asc",
        }

        if venue.tm_venue_id:
            params["venueId"] = venue.tm_venue_id
        elif venue.tm_keyword:
            params["keyword"] = venue.tm_keyword
            params["city"] = "London"
        else:
            params["keyword"] = venue.name
            params["city"] = "London"

        try:
            resp = self.session.get(TM_DISCOVERY_URL, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                raw_events = data.get("_embedded", {}).get("events", [])
                for it in raw_events:
                    parsed = self.parse_event(it, venue)
                    if parsed:
                        events.append(parsed)
                logger.info(f"Ticketmaster Discovery: Extracted {len(events)} events for {venue.name}")
            elif resp.status_code == 401:
                logger.warning("Ticketmaster API key is invalid or unauthorized (HTTP 401).")
            else:
                logger.warning(f"Ticketmaster API error for {venue.name}: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to fetch Ticketmaster events for {venue.name}: {e}")

        return events

    def fetch_all_venues(
        self,
        venues: List[Venue],
        target_month: Optional[int] = None,
        target_year: Optional[int] = None,
    ) -> List[Event]:
        """Fetch events across all configured Ticketmaster stadiums and arenas."""
        target_venues = [v for v in venues if v.platform in ["ticketmaster", "both"]]
        if not target_venues:
            return []

        if not self.is_configured:
            logger.info("Ticketmaster API key not configured in .env (TICKETMASTER_API_KEY). Stadium events skipped.")
            return []

        logger.info(f"Querying Ticketmaster Discovery API for {len(target_venues)} stadiums & arenas...")
        all_events: List[Event] = []

        for idx, venue in enumerate(target_venues):
            venue_events = self.fetch_venue_events(venue, target_month=target_month, target_year=target_year)
            all_events.extend(venue_events)

            # Polite pacing between requests (stays well under 5 req/sec limit)
            if idx < len(target_venues) - 1:
                time.sleep(0.25)

        logger.info(f"Total Ticketmaster events extracted: {len(all_events)}")
        return all_events
