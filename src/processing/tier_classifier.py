"""3-Tier Categorization & Discovery Engine for live events."""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from src.core.models import (
    CombinedTasteProfile,
    Event,
    MatchRationale,
    MatchSource,
    MonthlyDigest,
    Review,
    TierCategory,
    UserTasteProfile,
)
from src.core.normalizer import matches_artist_set, normalize_artist_name
from src.ingestion.review_parser import ReviewDatabase
from src.processing.event_diff_engine import EventDiffEngine

logger = logging.getLogger(__name__)

PUBLICATION_SOURCE_MAP: Dict[str, MatchSource] = {
    "The Guardian": MatchSource.REVIEW_GUARDIAN,
    "AnyDecentMusic?": MatchSource.REVIEW_ANYDECENTMUSIC,
    "NME": MatchSource.REVIEW_NME,
    "DIY Magazine": MatchSource.REVIEW_DIY,
    "Dork": MatchSource.REVIEW_DORK,
    "The Line of Best Fit": MatchSource.REVIEW_TLOBF,
    "Loud & Quiet": MatchSource.REVIEW_LOUD_AND_QUIET,
}

DEFAULT_COMEDY_KEYWORDS = [
    "comedy",
    "stand-up",
    "stand up",
    "comedian",
    "improv",
    "cabaret",
    "sketch",
    "fringe",
    "work-in-progress",
    "wip",
    "open mic comedy",
]


class TierClassifier:
    """
    Categorizes events into:
    - Tier 1: Direct Matches (in Elliott or Chloe's saved tracks, playlists, or top artists)
    - Tier 2: Discovery Matches (in Discover Weekly / Release Radar, or high-rated UK reviews)
    - Tier 3: Comedy & Alternative (matched against comedy/stand-up keywords)
    - Unmatched: Remaining events
    """

    def __init__(
        self,
        taste_profile: Optional[CombinedTasteProfile] = None,
        review_db: Optional[ReviewDatabase] = None,
        recommended_review_artists: Optional[Set[str]] = None,
        comedy_keywords: Optional[List[str]] = None,
    ):
        self.taste_profile = taste_profile
        self.review_db = review_db
        self.comedy_keywords = comedy_keywords or DEFAULT_COMEDY_KEYWORDS

        # Precompile comedy keyword regex with word boundaries
        escaped_patterns = [r"\b" + re.escape(kw.strip()) + r"\b" for kw in self.comedy_keywords if kw.strip()]
        self.comedy_regex = re.compile("|".join(escaped_patterns), re.IGNORECASE) if escaped_patterns else None

        # Load recommended review artists
        if recommended_review_artists is not None:
            self.recommended_review_artists = recommended_review_artists
        elif self.review_db is not None:
            self.recommended_review_artists = self.review_db.get_recommended_artists()
        else:
            self.recommended_review_artists = set()

    def _check_user_direct_match(
        self,
        user_profile: UserTasteProfile,
        normalized_acts: List[str],
        user_label: str,
    ) -> List[MatchRationale]:
        """Check if any act matches a user's direct Spotify library."""
        rationales: List[MatchRationale] = []

        for act in normalized_acts:
            if act in user_profile.saved_artists:
                rationales.append(
                    MatchRationale(
                        tier=TierCategory.TIER_1_DIRECT,
                        source=MatchSource.SPOTIFY_SAVED,
                        matched_act=act,
                        user=user_label,
                        description=f"In {user_label}'s Liked Songs",
                    )
                )
            elif act in user_profile.playlist_artists:
                rationales.append(
                    MatchRationale(
                        tier=TierCategory.TIER_1_DIRECT,
                        source=MatchSource.SPOTIFY_PLAYLIST,
                        matched_act=act,
                        user=user_label,
                        description=f"In {user_label}'s Playlists",
                    )
                )
            elif act in user_profile.top_artists:
                rationales.append(
                    MatchRationale(
                        tier=TierCategory.TIER_1_DIRECT,
                        source=MatchSource.SPOTIFY_TOP_ARTIST,
                        matched_act=act,
                        user=user_label,
                        description=f"In {user_label}'s Top Artists",
                    )
                )

        return rationales

    def _check_user_discovery_match(
        self,
        user_profile: UserTasteProfile,
        normalized_acts: List[str],
        user_label: str,
    ) -> List[MatchRationale]:
        """Check if any act matches a user's Spotify algorithmic discovery."""
        rationales: List[MatchRationale] = []

        for act in normalized_acts:
            if act in user_profile.discovery_artists:
                rationales.append(
                    MatchRationale(
                        tier=TierCategory.TIER_2_DISCOVERY,
                        source=MatchSource.SPOTIFY_DISCOVERY,
                        matched_act=act,
                        user=user_label,
                        description=f"In {user_label}'s Discover Weekly / Release Radar",
                    )
                )

        return rationales

    def _check_review_matches(self, normalized_acts: List[str]) -> List[MatchRationale]:
        """Check if any act has high-rated reviews in tracked publications."""
        rationales: List[MatchRationale] = []

        for act in normalized_acts:
            if act in self.recommended_review_artists:
                # Query database for exact details if available
                reviews: List[Review] = []
                if self.review_db:
                    reviews = self.review_db.get_reviews_for_artist(act)

                if reviews:
                    for rev in reviews[:2]:  # Include up to top 2 publications
                        src = PUBLICATION_SOURCE_MAP.get(rev.publication, MatchSource.REVIEW_NME)
                        if rev.stars:
                            score_text = f"{rev.stars:g}★"
                        elif rev.score and rev.max_score:
                            score_text = f"{rev.score:g}/{rev.max_score:g}"
                        else:
                            score_text = "Recommended"

                        rationales.append(
                            MatchRationale(
                                tier=TierCategory.TIER_2_DISCOVERY,
                                source=src,
                                matched_act=act,
                                user=None,
                                description=f"{score_text} review in {rev.publication}",
                            )
                        )
                else:
                    rationales.append(
                        MatchRationale(
                            tier=TierCategory.TIER_2_DISCOVERY,
                            source=MatchSource.REVIEW_NME,
                            matched_act=act,
                            user=None,
                            description=f"High-rated review in UK music press",
                        )
                    )

        return rationales

    def _check_comedy_match(self, event: Event) -> Optional[MatchRationale]:
        """Check if an event title or description matches comedy keywords."""
        if not self.comedy_regex:
            return None

        text_to_search = f"{event.title} {event.description or ''}"
        match = self.comedy_regex.search(text_to_search)
        if match:
            matched_kw = match.group(0)
            return MatchRationale(
                tier=TierCategory.TIER_3_COMEDY,
                source=MatchSource.COMEDY_KEYWORD,
                matched_act=event.primary_act,
                user=None,
                description=f"Comedy keyword: '{matched_kw}'",
            )
        return None

    def classify_event(self, event: Event) -> Event:
        """
        Classify a single event into Tier 1, Tier 2, Tier 3, or Unmatched,
        attaching match rationales.
        """
        # Ensure we have normalized performers to inspect
        norm_acts = list(event.normalized_performers)
        title_norm = normalize_artist_name(event.title)
        if title_norm and title_norm not in norm_acts:
            norm_acts.append(title_norm)

        event.matches = []

        # 1. Tier 1: Direct Spotify Matches (Elliott & Chloe)
        if self.taste_profile:
            elliott_matches = self._check_user_direct_match(
                self.taste_profile.elliott, norm_acts, "Elliott"
            )
            chloe_matches = self._check_user_direct_match(
                self.taste_profile.chloe, norm_acts, "Chloe"
            )

            tier_1_matches = elliott_matches + chloe_matches
            if tier_1_matches:
                event.tier = TierCategory.TIER_1_DIRECT
                event.matches = tier_1_matches
                return event

        # 2. Tier 2: Discovery Matches (Spotify Discovery OR High-Rated Reviews)
        tier_2_matches: List[MatchRationale] = []
        if self.taste_profile:
            tier_2_matches.extend(
                self._check_user_discovery_match(self.taste_profile.elliott, norm_acts, "Elliott")
            )
            tier_2_matches.extend(
                self._check_user_discovery_match(self.taste_profile.chloe, norm_acts, "Chloe")
            )

        review_matches = self._check_review_matches(norm_acts)
        tier_2_matches.extend(review_matches)

        if tier_2_matches:
            event.tier = TierCategory.TIER_2_DISCOVERY
            event.matches = tier_2_matches
            return event

        # 3. Tier 3: Comedy & Alternative
        comedy_match = self._check_comedy_match(event)
        if comedy_match:
            event.tier = TierCategory.TIER_3_COMEDY
            event.matches = [comedy_match]
            return event

        # 4. Unmatched
        event.tier = TierCategory.UNMATCHED
        return event

    def build_digest(
        self,
        events: List[Event],
        month_name: Optional[str] = None,
        year: Optional[int] = None,
        diff_engine: Optional[EventDiffEngine] = None,
    ) -> MonthlyDigest:
        """
        Classify all events, track deltas against previous digests, and construct a sorted MonthlyDigest.
        """
        now = datetime.now()
        target_month = month_name or now.strftime("%B")
        target_year = year or now.year

        # 1. Statefully diff against previous runs if diff engine provided
        new_announcements: List[Event] = []
        if diff_engine is not None:
            events = diff_engine.diff_and_record(
                events, digest_label=f"{target_month} {target_year}"
            )

        tier_1: List[Event] = []
        tier_2: List[Event] = []
        tier_3: List[Event] = []
        other: List[Event] = []

        for raw_event in events:
            classified = self.classify_event(raw_event)
            if classified.is_new:
                new_announcements.append(classified)

            if classified.tier == TierCategory.TIER_1_DIRECT:
                tier_1.append(classified)
            elif classified.tier == TierCategory.TIER_2_DISCOVERY:
                tier_2.append(classified)
            elif classified.tier == TierCategory.TIER_3_COMEDY:
                tier_3.append(classified)
            else:
                other.append(classified)

        # Sort chronologically by start_time
        tier_1.sort(key=lambda e: e.start_time)
        tier_2.sort(key=lambda e: e.start_time)
        tier_3.sort(key=lambda e: e.start_time)
        other.sort(key=lambda e: e.start_time)
        new_announcements.sort(key=lambda e: e.start_time)

        logger.info(
            f"Digest classification complete: {len(tier_1)} Tier 1, "
            f"{len(tier_2)} Tier 2, {len(tier_3)} Tier 3, {len(other)} Unmatched. "
            f"🆕 New Announcements since last run: {len(new_announcements)} "
            f"(Total: {len(events)})"
        )

        return MonthlyDigest(
            month_name=target_month,
            year=target_year,
            generated_at=now,
            tier_1_events=tier_1,
            tier_2_events=tier_2,
            tier_3_events=tier_3,
            other_events=other,
            new_announcements=new_announcements,
            total_events_scraped=len(events),
        )
