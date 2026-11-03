"""Email dispatcher supporting Gmail SMTP (App Password) and SendGrid API."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
import requests

from src.core.config import Config
from src.core.models import MonthlyDigest
from src.delivery.template_engine import TemplateEngine

logger = logging.getLogger(__name__)


class DigestMailer:
    """Dispatches monthly live music digests via Gmail SMTP or SendGrid API."""

    def __init__(self, config: Config, template_engine: Optional[TemplateEngine] = None):
        self.config = config
        self.template_engine = template_engine or TemplateEngine()

    def build_subject(self, digest: MonthlyDigest) -> str:
        """Construct subject line for digest email."""
        prefix = self.config.delivery.subject_prefix.strip()
        t1_count = len(digest.tier_1_events)
        t2_count = len(digest.tier_2_events)

        if t1_count > 0:
            highlight = f"{t1_count} Direct Matches"
        elif t2_count > 0:
            highlight = f"{t2_count} Top Discovery Picks"
        else:
            highlight = f"{digest.total_events_scraped} Upcoming Shows"

        return f"{prefix} {digest.month_name} {digest.year} — {highlight}"

    def send_via_gmail_smtp(
        self,
        subject: str,
        html_body: str,
        text_body: str,
        recipients: List[str],
    ) -> bool:
        """Send email using standard Gmail SMTP with App Password."""
        if not self.config.gmail_user or not self.config.gmail_app_password:
            logger.error("Gmail SMTP credentials missing in configuration (GMAIL_USER, GMAIL_APP_PASSWORD).")
            return False

        sender = self.config.gmail_user
        sender_header = f"Live Curator <{sender}>"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_header
        msg["To"] = ", ".join(recipients)

        # Attach text part first, then HTML as alternative
        part1 = MIMEText(text_body, "plain", "utf-8")
        part2 = MIMEText(html_body, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        try:
            logger.info(
                f"Connecting to Gmail SMTP ({self.config.delivery.smtp_host}:{self.config.delivery.smtp_port})..."
            )
            with smtplib.SMTP(self.config.delivery.smtp_host, self.config.delivery.smtp_port, timeout=20) as server:
                if self.config.delivery.use_tls:
                    server.starttls()
                server.login(self.config.gmail_user, self.config.gmail_app_password)
                server.sendmail(sender, recipients, msg.as_string())
            logger.info(f"Digest successfully dispatched via Gmail SMTP to {recipients}")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch digest via Gmail SMTP: {e}")
            return False

    def send_via_sendgrid(
        self,
        subject: str,
        html_body: str,
        text_body: str,
        recipients: List[str],
    ) -> bool:
        """Send email using SendGrid v3 API."""
        if not self.config.sendgrid_api_key:
            logger.error("SendGrid API key missing in configuration.")
            return False

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {self.config.sendgrid_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "personalizations": [{"to": [{"email": r} for r in recipients]}],
            "from": {"email": self.config.sendgrid_from_email, "name": "Live Curator"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in [200, 202]:
                logger.info(f"Digest successfully dispatched via SendGrid to {recipients}")
                return True
            else:
                logger.error(f"SendGrid API failed with status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to dispatch digest via SendGrid API: {e}")
            return False

    def send_digest(
        self,
        digest: MonthlyDigest,
        recipients: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> bool:
        """
        Orchestrate rendering and dispatching the digest.
        If dry_run is True, logs details without sending network emails.
        """
        target_recipients = recipients or self.config.digest_recipients
        if not target_recipients:
            logger.warning("No digest recipients configured. Please set DIGEST_RECIPIENTS in .env.")
            target_recipients = [self.config.gmail_user] if self.config.gmail_user else []

        if not target_recipients and not dry_run:
            logger.error("Cannot dispatch digest: no recipients available.")
            return False

        subject = self.build_subject(digest)
        html_body, text_body = self.template_engine.render_all(digest)

        logger.info(f"Digest prepared: '{subject}' ({len(html_body)} bytes HTML, {len(text_body)} bytes text)")

        if dry_run:
            logger.info(f"[DRY RUN] Would send to: {target_recipients}")
            logger.info(f"[DRY RUN] Subject: {subject}")
            logger.info("[DRY RUN] Email dispatch simulated successfully.")
            return True

        # Dispatch via configured channel
        if self.config.has_gmail_smtp:
            return self.send_via_gmail_smtp(subject, html_body, text_body, target_recipients)
        elif self.config.has_sendgrid:
            return self.send_via_sendgrid(subject, html_body, text_body, target_recipients)
        else:
            logger.warning("No email delivery credentials found (Gmail SMTP or SendGrid). Simulating dry run.")
            return True
