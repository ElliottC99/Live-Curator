"""Unit tests for the template engine and digest mailer."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from src.core.config import Config, DeliverySettings
from src.core.models import (
    Event,
    MatchRationale,
    MatchSource,
    MonthlyDigest,
    TierCategory,
)
from src.delivery.digest_mailer import DigestMailer
from src.delivery.template_engine import TemplateEngine


@pytest.fixture
def sample_digest():
    now = datetime(2026, 11, 1, 9, 0)
    event1 = Event(
        title="Fontaines D.C. + Support",
        venue_name="The Shacklewell Arms",
        venue_area="Dalston",
        start_time=now,
        date_str="Sun 01 Nov 2026, 19:30",
        performers=["Fontaines D.C."],
        ticket_url="https://dice.fm/event/fontaines-shacklewell",
        price_str="£18.50",
        tier=TierCategory.TIER_1_DIRECT,
        matches=[
            MatchRationale(
                tier=TierCategory.TIER_1_DIRECT,
                source=MatchSource.SPOTIFY_SAVED,
                matched_act="fontaines dc",
                user="Elliott",
                description="In Elliott's Liked Songs",
            )
        ],
    )
    event2 = Event(
        title="Fat Dog Album Launch",
        venue_name="MOTH Club",
        venue_area="Hackney Central",
        start_time=now,
        date_str="Tue 03 Nov 2026, 20:00",
        performers=["Fat Dog"],
        ticket_url="https://dice.fm/event/fatdog-moth",
        price_str="£15.00",
        tier=TierCategory.TIER_2_DISCOVERY,
        matches=[
            MatchRationale(
                tier=TierCategory.TIER_2_DISCOVERY,
                source=MatchSource.REVIEW_DORK,
                matched_act="fat dog",
                description="4★ review in Dork",
            )
        ],
    )
    event3 = Event(
        title="Dalston Comedy Club",
        venue_name="The Waiting Room",
        venue_area="Stoke Newington",
        start_time=now,
        date_str="Fri 06 Nov 2026, 20:30",
        performers=["Dalston Comedy Club"],
        ticket_url="https://dice.fm/event/dalston-comedy",
        price_str="Free",
        tier=TierCategory.TIER_3_COMEDY,
        matches=[
            MatchRationale(
                tier=TierCategory.TIER_3_COMEDY,
                source=MatchSource.COMEDY_KEYWORD,
                matched_act="Dalston Comedy Club",
                description="Comedy keyword: 'comedy'",
            )
        ],
    )

    return MonthlyDigest(
        month_name="November",
        year=2026,
        generated_at=now,
        tier_1_events=[event1],
        tier_2_events=[event2],
        tier_3_events=[event3],
        other_events=[],
        total_events_scraped=30,
    )


class TestTemplateEngine:
    """Test HTML and text template rendering."""

    def test_render_html_contains_critical_data(self, sample_digest):
        engine = TemplateEngine()
        html = engine.render_html(sample_digest)

        assert "November 2026" in html
        assert "LIVE CURATOR // LONDON" in html
        assert "Fontaines D.C." in html
        assert "The Shacklewell Arms" in html
        assert "In Elliott&#39;s Liked Songs" in html or "In Elliott's Liked Songs" in html
        assert "Fat Dog Album Launch" in html
        assert "Dalston Comedy Club" in html
        assert "https://dice.fm/event/fontaines-shacklewell" in html
        assert "£18.50" in html

        # Verify interactive single-page tab cycling controller
        assert "id=\"tab-nav\"" in html
        assert "switchTier('tier1')" in html
        assert "switchTier('tier2')" in html
        assert "switchTier('tier3')" in html
        assert "switchTier('all')" in html

    def test_render_text_contains_critical_data(self, sample_digest):
        engine = TemplateEngine()
        text = engine.render_text(sample_digest)

        assert "LIVE CURATOR // EAST LONDON" in text
        assert "November 2026" in text
        assert "Fontaines D.C." in text
        assert "Fat Dog" in text
        assert "Dalston Comedy Club" in text
        assert "https://dice.fm/event/fontaines-shacklewell" in text


class TestDigestMailer:
    """Test subject construction and dispatch mechanisms."""

    def test_build_subject_tier_1_highlight(self, sample_digest):
        config = Config(delivery=DeliverySettings(subject_prefix="[Live Curator]"))
        mailer = DigestMailer(config)
        subject = mailer.build_subject(sample_digest)

        assert subject == "[Live Curator] November 2026 — 1 Direct Matches"

    def test_build_subject_tier_2_highlight(self, sample_digest):
        sample_digest.tier_1_events = []
        config = Config(delivery=DeliverySettings(subject_prefix="[Live Curator]"))
        mailer = DigestMailer(config)
        subject = mailer.build_subject(sample_digest)

        assert subject == "[Live Curator] November 2026 — 1 Top Discovery Picks"

    def test_dry_run_dispatch(self, sample_digest):
        config = Config(
            digest_recipients=["test@example.com"],
            gmail_user="user@gmail.com",
            gmail_app_password="password",
        )
        mailer = DigestMailer(config)
        success = mailer.send_digest(sample_digest, dry_run=True)
        assert success is True

    @patch("smtplib.SMTP")
    def test_gmail_smtp_dispatch_success(self, mock_smtp_class, sample_digest):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        config = Config(
            gmail_user="elliott@gmail.com",
            gmail_app_password="test-app-password",
            digest_recipients=["elliott@gmail.com", "chloe@gmail.com"],
        )
        mailer = DigestMailer(config)
        success = mailer.send_digest(sample_digest, dry_run=False)

        assert success is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("elliott@gmail.com", "test-app-password")
        mock_server.sendmail.assert_called_once()
