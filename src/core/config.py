"""Configuration loader for the Live Curator Engine."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.core.models import Venue

# Load environment variables from .env if present
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AppSettings(BaseModel):
    name: str = "Live Curator Engine"
    target_timezone: str = "Europe/London"
    cache_dir: str = "data/cache"


class ScrapingSettings(BaseModel):
    headless: bool = True
    page_timeout_ms: int = 30000
    polite_delay_seconds_min: float = 2.0
    polite_delay_seconds_max: float = 4.0
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )


class ReviewSourceSettings(BaseModel):
    name: str
    type: str
    feed_url: Optional[str] = None
    url: Optional[str] = None
    enabled: bool = True


class ReviewsSettings(BaseModel):
    min_aggregate_score_10: float = 7.5
    min_stars_5: float = 4.0
    cache_retention_days: int = 90
    publications: List[ReviewSourceSettings] = Field(default_factory=list)


class ClassificationSettings(BaseModel):
    comedy_keywords: List[str] = Field(default_factory=list)


class DeliverySettings(BaseModel):
    subject_prefix: str = "[Live Curator East London]"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True


class Config(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    reviews: ReviewsSettings = Field(default_factory=ReviewsSettings)
    classification: ClassificationSettings = Field(default_factory=ClassificationSettings)
    delivery: DeliverySettings = Field(default_factory=DeliverySettings)
    venues: List[Venue] = Field(default_factory=list)

    # Environment-based secrets
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
    elliott_spotify_refresh_token: Optional[str] = None
    chloe_spotify_refresh_token: Optional[str] = None
    guardian_api_key: Optional[str] = None
    ticketmaster_api_key: Optional[str] = None
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None
    digest_recipients: List[str] = Field(default_factory=list)
    sendgrid_api_key: Optional[str] = None
    sendgrid_from_email: str = "digest@livecurator.local"

    @property
    def has_gmail_smtp(self) -> bool:
        return bool(self.gmail_user and self.gmail_app_password)

    @property
    def has_sendgrid(self) -> bool:
        return bool(self.sendgrid_api_key)


def load_config(
    venues_path: Optional[Path] = None,
    settings_path: Optional[Path] = None
) -> Config:
    """Load configuration from YAML files and environment variables."""
    venues_file = venues_path or (PROJECT_ROOT / "config" / "venues.yaml")
    settings_file = settings_path or (PROJECT_ROOT / "config" / "settings.yaml")

    settings_dict: Dict[str, Any] = {}
    if settings_file.exists():
        with open(settings_file, "r", encoding="utf-8") as f:
            settings_dict = yaml.safe_load(f) or {}

    venues_list: List[Venue] = []
    if venues_file.exists():
        with open(venues_file, "r", encoding="utf-8") as f:
            v_data = yaml.safe_load(f) or {}
            for item in v_data.get("venues", []):
                venues_list.append(Venue(**item))

    # Parse recipients from environment
    recipients_raw = os.getenv("DIGEST_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    return Config(
        app=AppSettings(**settings_dict.get("app", {})),
        scraping=ScrapingSettings(**settings_dict.get("scraping", {})),
        reviews=ReviewsSettings(**settings_dict.get("reviews", {})),
        classification=ClassificationSettings(**settings_dict.get("classification", {})),
        delivery=DeliverySettings(**settings_dict.get("delivery", {})),
        venues=venues_list,
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        elliott_spotify_refresh_token=os.getenv("ELLIOTT_SPOTIFY_REFRESH_TOKEN"),
        chloe_spotify_refresh_token=os.getenv("CHLOE_SPOTIFY_REFRESH_TOKEN"),
        guardian_api_key=os.getenv("GUARDIAN_API_KEY"),
        ticketmaster_api_key=os.getenv("TICKETMASTER_API_KEY"),
        gmail_user=os.getenv("GMAIL_USER"),
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD"),
        digest_recipients=recipients,
        sendgrid_api_key=os.getenv("SENDGRID_API_KEY"),
        sendgrid_from_email=os.getenv("SENDGRID_FROM_EMAIL", "digest@livecurator.local"),
    )
