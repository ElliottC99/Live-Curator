"""Unit tests for the artist normalizer and lineup splitter."""

import pytest
from src.core.normalizer import (
    normalize_artist_name,
    split_lineup,
    extract_normalized_acts,
    matches_artist_set,
)


class TestArtistNormalization:
    """Test normalization of artist names and titles."""

    def test_basic_lowercase_and_strip(self):
        assert normalize_artist_name("Fontaines D.C.") == "fontaines dc"
        assert normalize_artist_name("  The Smile  ") == "smile"

    def test_strip_leading_articles(self):
        assert normalize_artist_name("The Beatles") == "beatles"
        assert normalize_artist_name("A Certain Ratio") == "certain ratio"
        assert normalize_artist_name("An Horse") == "horse"

    def test_accent_and_diacritic_removal(self):
        assert normalize_artist_name("Beyoncé") == "beyonce"
        assert normalize_artist_name("Björk") == "bjork"
        assert normalize_artist_name("Sigur Rós") == "sigur ros"
        assert normalize_artist_name("MØ") == "mo"

    def test_parenthetical_event_tags_removal(self):
        assert normalize_artist_name("Pond (Live)") == "pond"
        assert normalize_artist_name("Overmono (DJ Set)") == "overmono"
        assert normalize_artist_name("Dry Cleaning (Single Launch)") == "dry cleaning"
        assert normalize_artist_name("IDLES [Sold Out]") == "idles"

    def test_prefix_removal(self):
        assert normalize_artist_name("An Evening with Lankum") == "lankum"
        assert normalize_artist_name("Live: Squid") == "squid"
        assert normalize_artist_name("In Conversation with Jarvis Cocker") == "jarvis cocker"


class TestLineupSplitting:
    """Test splitting multi-act bills into distinct performers."""

    def test_plus_delimiter(self):
        acts = split_lineup("Pond + Warmduscher")
        assert acts == ["Pond", "Warmduscher"]

    def test_plus_with_generic_guests(self):
        acts = split_lineup("Pond + Special Guests")
        assert acts == ["Pond"]

    def test_with_delimiters(self):
        acts = split_lineup("Dry Cleaning w/ Ethan P. Flynn")
        assert acts == ["Dry Cleaning", "Ethan P. Flynn"]

        acts2 = split_lineup("Squid with PVA")
        assert acts2 == ["Squid", "PVA"]

    def test_featuring_delimiters(self):
        acts = split_lineup("Fred again.. feat. Romy")
        assert acts == ["Fred again..", "Romy"]

        acts2 = split_lineup("Four Tet ft. Skrillex")
        assert acts2 == ["Four Tet", "Skrillex"]

    def test_comma_delimited_lineup(self):
        acts = split_lineup("Goat Girl, Sorry, English Teacher")
        assert acts == ["Goat Girl", "Sorry", "English Teacher"]

    def test_protected_band_names(self):
        acts = split_lineup("Florence and the Machine")
        assert acts == ["Florence and the Machine"]

        acts2 = split_lineup("Belle and Sebastian")
        assert acts2 == ["Belle and Sebastian"]


class TestMatchingLogic:
    """Test matching extracted acts against reference taste sets."""

    def test_matches_artist_set(self):
        event_acts = extract_normalized_acts("Pond + Warmduscher + Special Guests")
        # event_acts -> ["pond", "warmduscher"]

        reference_library = {"pond", "dry cleaning", "fontaines dc"}
        matched = matches_artist_set(event_acts, reference_library)

        assert matched == ["pond"]

    def test_matches_accented_artist(self):
        event_acts = extract_normalized_acts("Björk (Live)")
        reference_library = {"bjork"}
        matched = matches_artist_set(event_acts, reference_library)

        assert matched == ["bjork"]
