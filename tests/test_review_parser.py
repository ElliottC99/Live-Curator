"""Unit tests for the critical review parser and SQLite cache."""

from pathlib import Path
import pytest
from src.core.models import Review
from src.ingestion.review_parser import (
    ReviewDatabase,
    ReviewAggregator,
    parse_rating_from_text,
    split_artist_album,
)


class TestRatingParsing:
    """Test extracting scores and recommendation status from review text."""

    def test_unicode_stars(self):
        score, scale, is_rec = parse_rating_from_text("Fontaines D.C.: Romance review – ★★★★☆")
        assert score == 4.0
        assert scale == 5.0
        assert is_rec is True

        score2, scale2, is_rec2 = parse_rating_from_text("Average record – ★★★☆☆")
        assert score2 == 3.0
        assert is_rec2 is False

    def test_numeric_5_point_scale(self):
        score, scale, is_rec = parse_rating_from_text("Rating: 4.5/5")
        assert score == 4.5
        assert scale == 5.0
        assert is_rec is True

        score2, scale2, is_rec2 = parse_rating_from_text("3/5 stars")
        assert score2 == 3.0
        assert is_rec2 is False

    def test_numeric_10_point_scale(self):
        score, scale, is_rec = parse_rating_from_text("Overall Score: 8.4/10")
        assert score == 8.4
        assert scale == 10.0
        assert is_rec is True

        score2, scale2, is_rec2 = parse_rating_from_text("Score: 7.1 out of 10")
        assert score2 == 7.1
        assert scale2 == 10.0
        assert is_rec2 is False  # below 7.5


class TestArtistAlbumSplitting:
    """Test splitting headline strings into artist and album components."""

    def test_hyphen_split(self):
        artist, album = split_artist_album("Fontaines D.C. - Romance")
        assert artist == "Fontaines D.C."
        assert album == "Romance"

    def test_colon_split(self):
        artist, album = split_artist_album("English Teacher: This Could Be Texas review")
        assert artist == "English Teacher"
        assert album == "This Could Be Texas"

    def test_prefix_removal(self):
        artist, album = split_artist_album("Album Review: The Smile - Wall of Eyes")
        assert artist == "The Smile"
        assert album == "Wall of Eyes"


class TestReviewDatabase:
    """Test SQLite review caching and fast indexing."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_file = tmp_path / "test_reviews.sqlite"
        return ReviewDatabase(db_file)

    def test_save_and_retrieve_reviews(self, temp_db):
        reviews = [
            Review(
                artist_name="Fontaines D.C.",
                normalized_artist="fontaines dc",
                publication="The Guardian",
                album_title="Romance",
                score=4.0,
                max_score=5.0,
                stars=4.0,
                is_recommended=True,
                url="https://example.com/fontaines",
            ),
            Review(
                artist_name="Pond",
                normalized_artist="pond",
                publication="NME",
                album_title="Stung!",
                score=3.0,
                max_score=5.0,
                stars=3.0,
                is_recommended=False,
                url="https://example.com/pond",
            ),
            Review(
                artist_name="Geese",
                normalized_artist="geese",
                publication="AnyDecentMusic?",
                album_title="3D Country",
                score=8.1,
                max_score=10.0,
                is_recommended=True,
                url="https://example.com/geese",
            ),
        ]

        temp_db.save_reviews(reviews)

        # Check recommended artists query
        recommended = temp_db.get_recommended_artists()
        assert "fontaines dc" in recommended
        assert "geese" in recommended
        assert "pond" not in recommended

        # Check query for specific artist
        fontaines_revs = temp_db.get_reviews_for_artist("fontaines dc")
        assert len(fontaines_revs) == 1
        assert fontaines_revs[0].publication == "The Guardian"
        assert fontaines_revs[0].score == 4.0
