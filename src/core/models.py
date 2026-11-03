"""Domain entities for the Live Curator Engine."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Set
from pydantic import BaseModel, Field


class TierCategory(str, Enum):
    """Event classification tiers."""
    TIER_1_DIRECT = "Tier 1: Direct Matches"
    TIER_2_DISCOVERY = "Tier 2: Discovery Matches"
    TIER_3_COMEDY = "Tier 3: Comedy & Alternative"
    UNMATCHED = "Unmatched"


class MatchSource(str, Enum):
    """Source of taste or critical match."""
    SPOTIFY_SAVED = "spotify_saved"
    SPOTIFY_PLAYLIST = "spotify_playlist"
    SPOTIFY_TOP_ARTIST = "spotify_top_artist"
    SPOTIFY_DISCOVERY = "spotify_discovery"
    REVIEW_GUARDIAN = "review_guardian"
    REVIEW_ANYDECENTMUSIC = "review_anydecentmusic"
    REVIEW_NME = "review_nme"
    REVIEW_DIY = "review_diy"
    REVIEW_DORK = "review_dork"
    REVIEW_TLOBF = "review_tlobf"
    REVIEW_LOUD_AND_QUIET = "review_loud_and_quiet"
    COMEDY_KEYWORD = "comedy_keyword"


class MatchRationale(BaseModel):
    """Explanation of why an event qualified for a tier."""
    tier: TierCategory
    source: MatchSource
    matched_act: str
    user: Optional[str] = None  # "Elliott", "Chloe", "Both", or None for reviews/comedy
    description: str            # e.g., "In Chloe's Liked Songs", "4.5★ NME Review"


class Review(BaseModel):
    """Critical album/track review from a tracked publication."""
    artist_name: str
    normalized_artist: str
    publication: str
    score: Optional[float] = None
    max_score: Optional[float] = None
    stars: Optional[float] = None
    is_recommended: bool = False  # True if >= 4.0/5 or >= 7.5/10
    url: Optional[str] = None
    publication_date: Optional[str] = None
    album_title: Optional[str] = None


class Venue(BaseModel):
    """Configured target venue across DICE and Ticketmaster."""
    name: str
    dice_slug: Optional[str] = None
    platform: str = "dice"  # "dice", "ticketmaster", or "both"
    tm_venue_id: Optional[str] = None
    tm_keyword: Optional[str] = None
    area: str = "East London"
    address: Optional[str] = None
    genre_focus: List[str] = Field(default_factory=list)

    @property
    def dice_url(self) -> Optional[str]:
        return f"https://dice.fm/venue/{self.dice_slug}" if self.dice_slug else None


class Event(BaseModel):
    """Live event scraped from DICE or Ticketmaster."""
    id: Optional[str] = None
    title: str
    venue_name: str
    venue_area: str = "East London"
    start_time: datetime
    date_str: str
    performers: List[str] = Field(default_factory=list)
    normalized_performers: List[str] = Field(default_factory=list)
    ticket_url: str
    platform: str = "dice"  # "dice" or "ticketmaster"
    price_str: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    tier: TierCategory = TierCategory.UNMATCHED
    matches: List[MatchRationale] = Field(default_factory=list)

    @property
    def primary_act(self) -> str:
        return self.performers[0] if self.performers else self.title


class UserTasteProfile(BaseModel):
    """Taste profile for an individual user."""
    user_name: str
    saved_artists: Set[str] = Field(default_factory=set)
    playlist_artists: Set[str] = Field(default_factory=set)
    top_artists: Set[str] = Field(default_factory=set)
    discovery_artists: Set[str] = Field(default_factory=set)  # Discover Weekly / Release Radar

    @property
    def all_direct_artists(self) -> Set[str]:
        return self.saved_artists | self.playlist_artists | self.top_artists


class CombinedTasteProfile(BaseModel):
    """Aggregated profiles for Elliott and Chloe."""
    elliott: UserTasteProfile
    chloe: UserTasteProfile

    @property
    def combined_direct(self) -> Set[str]:
        return self.elliott.all_direct_artists | self.chloe.all_direct_artists

    @property
    def combined_discovery(self) -> Set[str]:
        return self.elliott.discovery_artists | self.chloe.discovery_artists


class MonthlyDigest(BaseModel):
    """Complete monthly event curation ready for delivery."""
    month_name: str
    year: int
    generated_at: datetime
    tier_1_events: List[Event] = Field(default_factory=list)
    tier_2_events: List[Event] = Field(default_factory=list)
    tier_3_events: List[Event] = Field(default_factory=list)
    other_events: List[Event] = Field(default_factory=list)
    total_events_scraped: int = 0
