"""Headless Playwright scraper for DICE.fm venue listings with anti-bot bypass."""

import json
import logging
import random
import re
import time
from datetime import datetime
from typing import Any, List, Optional
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from playwright_stealth import Stealth

from src.core.models import Event, Venue
from src.core.normalizer import split_lineup, extract_normalized_acts

logger = logging.getLogger(__name__)


class DiceScraper:
    """
    Stealth web scraper for extracting monthly event listings from DICE.fm venue pages.
    Bypasses Cloudflare Turnstile/WAF using Playwright Chromium with stealth evasions.
    """

    def __init__(
        self,
        headless: bool = True,
        user_agent: Optional[str] = None,
        page_timeout_ms: int = 25000,
        delay_min: float = 1.5,
        delay_max: float = 3.5,
        config: Optional[Any] = None,
    ):
        # Support passing Config object as the first positional argument
        if not isinstance(headless, bool):
            config = headless
            headless = getattr(getattr(config, "scraping", None), "headless", True)

        default_ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )

        if config is not None and hasattr(config, "scraping"):
            self.headless = getattr(config.scraping, "headless", headless)
            self.user_agent = getattr(config.scraping, "user_agent", None) or default_ua
            self.page_timeout_ms = getattr(config.scraping, "page_timeout_ms", page_timeout_ms)
            self.delay_min = getattr(config.scraping, "polite_delay_seconds_min", delay_min)
            self.delay_max = getattr(config.scraping, "polite_delay_seconds_max", delay_max)
        else:
            self.headless = headless
            self.user_agent = user_agent or default_ua
            self.page_timeout_ms = page_timeout_ms
            self.delay_min = delay_min
            self.delay_max = delay_max
        self.stealth = Stealth()

    def _create_browser_and_context(self, p) -> tuple[Browser, BrowserContext]:
        """Launch an evasion-hardened Chromium instance."""
        browser = p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1280, "height": 800},
            locale="en-GB",
            timezone_id="Europe/London",
        )
        return browser, context

    def _parse_event_from_dict(self, event_data: dict, venue: Venue) -> Optional[Event]:
        """Convert a raw DICE Next.js event object into a domain Event entity."""
        try:
            event_id = event_data.get("id")
            name = event_data.get("name", "").strip()
            if not name:
                return None

            # Dates parsing
            dates_info = event_data.get("dates", {})
            start_iso = dates_info.get("event_start_date")
            if not start_iso:
                return None

            # Parse ISO 8601 timestamp
            try:
                start_dt = datetime.fromisoformat(start_iso)
            except Exception:
                return None

            date_str = start_dt.strftime("%a %d %b %Y, %H:%M")

            # Ticket URL
            ticket_url = f"https://dice.fm/event/{event_id}" if event_id else venue.dice_url

            # Price parsing
            price_info = event_data.get("price") or {}
            amount = price_info.get("amount")
            currency = price_info.get("currency", "GBP")
            if amount is not None and amount > 0:
                symbol = "£" if currency == "GBP" else "$" if currency == "USD" else "€"
                price_str = f"{symbol}{amount / 100:.2f}"
            elif amount == 0:
                price_str = "Free"
            else:
                price_str = None

            # Status & Sold out check
            status = str(event_data.get("status") or "").lower()
            waiting_list = bool(event_data.get("waiting_list_enabled", False))
            is_sold_out = (status in ["sold-out", "off-sale"] or waiting_list or bool(re.search(r"\b(sold\s*out)\b", name, re.IGNORECASE)))

            # Images
            images = event_data.get("images") or {}
            image_url = images.get("square") or images.get("landscape")

            # Performers extraction and normalization
            performers = split_lineup(name)
            normalized = extract_normalized_acts(name)

            return Event(
                id=event_id,
                title=name,
                venue_name=venue.name,
                venue_area=venue.area,
                start_time=start_dt,
                date_str=date_str,
                performers=performers,
                normalized_performers=normalized,
                ticket_url=ticket_url,
                price_str=price_str,
                is_sold_out=is_sold_out,
                description=event_data.get("event_tag") or None,
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"Error parsing event item for {venue.name}: {e}")
            return None

    def scrape_venue(
        self,
        page: Page,
        venue: Venue,
        target_month: Optional[int] = None,
        target_year: Optional[int] = None,
    ) -> List[Event]:
        """
        Scrape a single venue page on DICE.fm.
        Returns a list of upcoming Event objects.
        """
        logger.info(f"Navigating to {venue.name} ({venue.dice_url})...")
        events: List[Event] = []

        try:
            response = page.goto(venue.dice_url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
            page.wait_for_timeout(2000)

            # Check if page returned 404
            status = response.status if response else 0
            title = page.title()

            if status == 404 or "404" in title:
                logger.warning(f"Venue {venue.name} returned 404 at {venue.dice_url}. Skipping.")
                return []

            # Check for Cloudflare Turnstile challenge page
            if "Just a moment" in title:
                logger.info(f"Cloudflare challenge detected for {venue.name}. Waiting for resolution...")
                for _ in range(6):
                    page.wait_for_timeout(1000)
                    if "Just a moment" not in page.title():
                        break

            # Method 1: Extract structured Next.js state (#__NEXT_DATA__)
            next_data_el = page.query_selector("#__NEXT_DATA__")
            if next_data_el:
                try:
                    payload = json.loads(next_data_el.inner_text())
                    profile = payload.get("props", {}).get("pageProps", {}).get("profile", {})
                    sections = profile.get("sections", [])

                    for section in sections:
                        items = section.get("items", [])
                        for item in items:
                            event_data = item.get("event")
                            if event_data and isinstance(event_data, dict):
                                parsed_event = self._parse_event_from_dict(event_data, venue)
                                if parsed_event:
                                    # Month & year filtering if specified
                                    if target_month and target_year:
                                        if (
                                            parsed_event.start_time.month != target_month
                                            or parsed_event.start_time.year != target_year
                                        ):
                                            continue
                                    events.append(parsed_event)

                    # Multi-page pagination: if 30 items found, trigger scroll loop
                    if len(events) >= 30:
                        logger.info(f"Venue {venue.name} reached 30-event SSR ceiling. Attempting scroll pagination...")
                        for scroll_step in range(3):
                            try:
                                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                                page.wait_for_timeout(1000)
                                load_more = page.query_selector("button:has-text('Load more'), button:has-text('See more')")
                                if load_more and load_more.is_visible():
                                    load_more.click()
                                    page.wait_for_timeout(1200)
                            except Exception as scroll_err:
                                logger.debug(f"Scroll pagination step {scroll_step + 1} error: {scroll_err}")
                                break
                except Exception as ex:
                    logger.warning(f"Failed to parse __NEXT_DATA__ for {venue.name}: {ex}")

            logger.info(f"Extracted {len(events)} events for {venue.name}")

        except Exception as e:
            logger.error(f"Error scraping venue {venue.name}: {e}")

        return events

    def scrape_all_venues(
        self,
        venues: List[Venue],
        target_month: Optional[int] = None,
        target_year: Optional[int] = None,
    ) -> List[Event]:
        """
        Scrape events across all configured venues with polite request throttling.
        """
        all_events: List[Event] = []

        with sync_playwright() as p:
            browser, context = self._create_browser_and_context(p)
            page = context.new_page()
            self.stealth.apply_stealth_sync(page)

            for idx, venue in enumerate(venues):
                try:
                    venue_events = self.scrape_venue(
                        page=page,
                        venue=venue,
                        target_month=target_month,
                        target_year=target_year,
                    )
                    all_events.extend(venue_events)

                    # Polite jittered delay between venue requests
                    if idx < len(venues) - 1:
                        sleep_time = random.uniform(self.delay_min, self.delay_max)
                        logger.debug(f"Polite delay: sleeping {sleep_time:.2f}s...")
                        time.sleep(sleep_time)

                except Exception as e:
                    logger.error(f"Unexpected error scraping {venue.name}: {e}")

            browser.close()

        # Deduplicate events by ID or title+date
        unique_events: dict[str, Event] = {}
        for ev in all_events:
            key = ev.id if ev.id else f"{ev.title}_{ev.start_time.isoformat()}"
            if key not in unique_events:
                unique_events[key] = ev

        logger.info(f"Total unique events extracted across {len(venues)} venues: {len(unique_events)}")
        return list(unique_events.values())

    scrape_venues = scrape_all_venues
