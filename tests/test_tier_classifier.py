"""Unit tests for the 3-Tier Categorization & Discovery Engine."""

from datetime import datetime, timedelta
import pytest

from src.core.models import (
    CombinedTasteProfile,
    Event,
    MatchSource,
    Review,
    TierCategory,
    UserTasteProfile,
)
from src.ingestion.review_parser import ReviewDatabase
from src.processing.tier_classifier import TierClassifier


@pytest.fixture
def sample_taste_profile():
    elliott = UserTasteProfile(
        user_name="Elliott",
        saved_artists={"fontaines dc", "idles", "the smile"},
        playlist_artists={"lcd soundsystem", "king krule"},
        top_artists={"radiohead", "bicep"},
        discovery_artists={"english teacher", "bar italia"},
    )
    chloe = UserTasteProfile(
        user_name="Chloe",
        saved_artists={"chappell roan", "charli xcx", "the smile"},
        playlist_artists={"boygenius", "caroline polachek"},
        top_artists={"clairo", "phoebe bridgers"},
        discovery_artists={"last dinner party", "geese"},
    )
    return CombinedTasteProfile(elliott=elliott, chloe=chloe)


@pytest.fixture
def sample_review_db(tmp_path):
    db_path = tmp_path / "test_classifier_reviews.sqlite"
    db = ReviewDatabase(db_path)
    reviews = [
        Review(
            artist_name="Fat Dog",
            normalized_artist="fat dog",
            publication="Dork",
            album_title="WOOF.",
            score=4.0,
            max_score=5.0,
            stars=4.0,
            is_recommended=True,
            url="https://readdork.com/fatdog",
        ),
        Review(
            artist_name="Protomartyr",
            normalized_artist="protomartyr",
            publication="DIY Magazine",
            album_title="Formal Growth",
            score=5.0,
            max_score=5.0,
            stars=5.0,
            is_recommended=True,
            url="https://diymag.com/protomartyr",
        ),
        Review(
            artist_name="Pond",
            normalized_artist="pond",
            publication="NME",
            score=3.0,
            max_score=5.0,
            stars=3.0,
            is_recommended=False,
        ),
    ]
    db.save_reviews(reviews)
    return db


def create_event(title: str, acts: list, days_ahead: int = 1, desc: str = "") -> Event:
    event_date = datetime(2026, 11, 1, 20, 0) + timedelta(days=days_ahead)
    return Event(
        title=title,
        venue_name="MOTH Club",
        venue_area="Hackney Central",
        start_time=event_date,
        date_str=event_date.strftime("%a %d %b %Y, %H:%M"),
        performers=acts,
        normalized_performers=[a.lower().replace(".", "").replace("'", "") for a in acts],
        ticket_url="https://dice.fm/event/test",
        price_str="£15.00",
        description=desc,
    )


class TestTierClassifier:
    """Test classification rules and digest compilation."""

    def test_tier_1_direct_match_elliott(self, sample_taste_profile):
        classifier = TierClassifier(taste_profile=sample_taste_profile)
        event = create_event("Fontaines D.C. + Support", ["Fontaines D.C."])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_1_DIRECT
        assert len(classified.matches) >= 1
        assert classified.matches[0].user == "Elliott"
        assert classified.matches[0].source == MatchSource.SPOTIFY_SAVED
        assert "Liked Songs" in classified.matches[0].description

    def test_tier_1_direct_match_chloe(self, sample_taste_profile):
        classifier = TierClassifier(taste_profile=sample_taste_profile)
        event = create_event("Caroline Polachek Live", ["Caroline Polachek"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_1_DIRECT
        assert classified.matches[0].user == "Chloe"
        assert classified.matches[0].source == MatchSource.SPOTIFY_PLAYLIST

    def test_tier_1_mutual_match(self, sample_taste_profile):
        classifier = TierClassifier(taste_profile=sample_taste_profile)
        event = create_event("The Smile in Concert", ["The Smile"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_1_DIRECT
        users = {m.user for m in classified.matches}
        assert "Elliott" in users
        assert "Chloe" in users

    def test_tier_1_multi_tag_with_reviews(self, sample_taste_profile, sample_review_db):
        from src.core.models import Review
        sample_review_db.save_reviews([
            Review(
                artist_name="The Smile",
                normalized_artist="the smile",
                publication="The Guardian",
                album_title="Wall of Eyes",
                stars=5.0,
                is_recommended=True,
            )
        ])
        classifier = TierClassifier(taste_profile=sample_taste_profile, review_db=sample_review_db)
        event = create_event("The Smile in Concert", ["The Smile"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_1_DIRECT
        descriptions = [m.description for m in classified.matches]
        assert any("Elliott" in d for d in descriptions)
        assert any("5★ review in The Guardian" in d for d in descriptions)

    def test_tier_2_discovery_spotify(self, sample_taste_profile):
        classifier = TierClassifier(taste_profile=sample_taste_profile)
        event = create_event("English Teacher + Guests", ["English Teacher"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_2_DISCOVERY
        assert classified.matches[0].user == "Elliott"
        assert classified.matches[0].source == MatchSource.SPOTIFY_DISCOVERY

    def test_tier_2_discovery_critical_reviews(self, sample_taste_profile, sample_review_db):
        classifier = TierClassifier(
            taste_profile=sample_taste_profile,
            review_db=sample_review_db,
        )
        event = create_event("Fat Dog Album Launch", ["Fat Dog"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_2_DISCOVERY
        assert classified.matches[0].source == MatchSource.REVIEW_DORK
        assert "4★ review in Dork" in classified.matches[0].description

    def test_tier_3_comedy_in_title(self, sample_taste_profile):
        classifier = TierClassifier(taste_profile=sample_taste_profile)
        event = create_event("Friday Night Stand-Up Showcase", ["Various Comedians"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_3_COMEDY
        assert classified.matches[0].source == MatchSource.COMEDY_KEYWORD

    def test_tier_3_comedy_in_description(self, sample_taste_profile):
        classifier = TierClassifier(taste_profile=sample_taste_profile)
        event = create_event("James Acaster: New Material", ["James Acaster"], desc="A work-in-progress comedy show.")
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.TIER_3_COMEDY
        assert classified.matches[0].source == MatchSource.COMEDY_KEYWORD

    def test_unmatched_event(self, sample_taste_profile, sample_review_db):
        classifier = TierClassifier(
            taste_profile=sample_taste_profile,
            review_db=sample_review_db,
        )
        event = create_event("Obscure Local Band", ["Obscure Local Band"])
        classified = classifier.classify_event(event)

        assert classified.tier == TierCategory.UNMATCHED
        assert len(classified.matches) == 0

    def test_build_digest_sorting_and_counts(self, sample_taste_profile, sample_review_db):
        classifier = TierClassifier(
            taste_profile=sample_taste_profile,
            review_db=sample_review_db,
        )

        events = [
            create_event("Obscure Act 2", ["Obscure Act 2"], days_ahead=10),
            create_event("Fontaines D.C.", ["Fontaines D.C."], days_ahead=5),
            create_event("Stand Up Night", ["Comedian A"], days_ahead=2),
            create_event("Fat Dog", ["Fat Dog"], days_ahead=3),
            create_event("The Smile", ["The Smile"], days_ahead=1),
        ]

        digest = classifier.build_digest(events, month_name="November", year=2026)

        assert digest.total_events_scraped == 5
        assert len(digest.tier_1_events) == 2  # The Smile (day 1), Fontaines D.C. (day 5)
        assert len(digest.tier_2_events) == 1  # Fat Dog (day 3)
        assert len(digest.tier_3_events) == 1  # Stand Up Night (day 2)
        assert len(digest.other_events) == 1   # Obscure Act 2 (day 10)

        # Check chronological ordering
        assert digest.tier_1_events[0].title == "The Smile"
        assert digest.tier_1_events[1].title == "Fontaines D.C."

    def test_club_night_heuristics_and_user_tags(self, tmp_path):
        from src.processing.user_tag_engine import UserTagEngine
        tag_db = tmp_path / "tags.sqlite"
        tag_engine = UserTagEngine(tag_db)

        classifier = TierClassifier(user_tag_engine=tag_engine)

        # 1. Late night event (starts at 23:00)
        dt_late = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
        late_event = Event(
            id="e_late",
            title="House Vibrations",
            venue_name="The Shacklewell Arms",
            start_time=dt_late,
            date_str="Tonight 23:00",
            ticket_url="https://dice.fm/e/late",
        )
        c1 = classifier.classify_event(late_event)
        assert c1.is_club_night is True
        assert c1.tier == TierCategory.CLUB_NIGHT

        # 2. Club keyword event at 20:00 (DJ Set)
        dt_early = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
        dj_event = Event(
            id="e_dj",
            title="Awesome DJ Set & Dance Party",
            venue_name="MOTH Club",
            start_time=dt_early,
            date_str="Tonight 20:00",
            ticket_url="https://dice.fm/e/dj",
        )
        c2 = classifier.classify_event(dj_event)
        assert c2.is_club_night is True
        assert c2.tier == TierCategory.CLUB_NIGHT

        # 3. User override: mark 23:00 event as live_gig
        tag_engine.set_tag("e_late_band", "live_gig")
        late_band = Event(
            id="e_late_band",
            title="Late Headline Band",
            venue_name="Cafe OTO",
            start_time=dt_late,
            date_str="Tonight 23:00",
            ticket_url="https://dice.fm/e/late-band",
        )
        # Re-initialize classifier so it picks up tags
        classifier_with_tags = TierClassifier(user_tag_engine=tag_engine)
        c3 = classifier_with_tags.classify_event(late_band)
        assert c3.is_club_night is False
        assert c3.tier != TierCategory.CLUB_NIGHT

