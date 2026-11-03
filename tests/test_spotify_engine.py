"""Unit tests for the Spotify taste profiling engine using mock data."""

from unittest.mock import MagicMock, patch
import pytest

from src.ingestion.spotify_engine import SpotifyEngine


@pytest.fixture
def spotify_engine():
    return SpotifyEngine(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        redirect_uri="http://127.0.0.1:8888/callback",
    )


def test_is_configured(spotify_engine):
    assert spotify_engine.is_configured is True

    unconfigured = SpotifyEngine()
    assert unconfigured.is_configured is False


def test_refresh_access_token_success(spotify_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "mock_new_access_token_123"}

    with patch("requests.post", return_value=mock_response) as mock_post:
        token = spotify_engine.refresh_access_token("mock_refresh_token")
        assert token == "mock_new_access_token_123"
        mock_post.assert_called_once()


def test_refresh_access_token_failure(spotify_engine):
    with patch("requests.post", side_effect=Exception("Connection refused")):
        token = spotify_engine.refresh_access_token("bad_refresh_token")
        assert token is None


def test_fetch_saved_artists(spotify_engine):
    mock_sp = MagicMock()
    mock_sp.current_user_saved_tracks.return_value = {
        "items": [
            {
                "track": {
                    "artists": [
                        {"name": "Fontaines D.C."},
                        {"name": "The Smile"},
                    ]
                }
            },
            {
                "track": {
                    "artists": [
                        {"name": "Beyoncé"},
                    ]
                }
            },
        ]
    }

    artists = spotify_engine._fetch_saved_artists(mock_sp, limit_batches=1)
    # Normalized expectations
    assert "fontaines dc" in artists
    assert "smile" in artists
    assert "beyonce" in artists
    assert len(artists) == 3


def test_fetch_top_artists(spotify_engine):
    mock_sp = MagicMock()
    mock_sp.current_user_top_artists.return_value = {
        "items": [
            {"name": "Pond"},
            {"name": "Lankum"},
        ]
    }

    artists = spotify_engine._fetch_top_artists(mock_sp)
    assert "pond" in artists
    assert "lankum" in artists


def test_fetch_playlist_and_discovery_artists(spotify_engine):
    mock_sp = MagicMock()
    # 2 playlists: 1 normal, 1 Discover Weekly
    mock_sp.current_user_playlists.return_value = {
        "items": [
            {"id": "pl_1", "name": "East London Indie Vibes"},
            {"id": "pl_2", "name": "Discover Weekly"},
        ]
    }

    def mock_playlist_tracks(playlist_id, limit=100):
        if playlist_id == "pl_1":
            return {
                "items": [
                    {"track": {"artists": [{"name": "Dry Cleaning"}]}},
                ]
            }
        elif playlist_id == "pl_2":
            return {
                "items": [
                    {"track": {"artists": [{"name": "Warmduscher"}]}},
                    {"track": {"artists": [{"name": "Geese"}]}},
                ]
            }
        return {"items": []}

    mock_sp.playlist_tracks.side_effect = mock_playlist_tracks

    playlist_artists, discovery_artists = spotify_engine._fetch_playlist_and_discovery_artists(mock_sp)

    # Standard playlist
    assert "dry cleaning" in playlist_artists
    # Discovery playlist
    assert "warmduscher" in discovery_artists
    assert "geese" in discovery_artists
    assert "warmduscher" not in playlist_artists


def test_combined_taste_profile(spotify_engine):
    # Mock refresh_access_token and API calls
    with patch.object(spotify_engine, "refresh_access_token", return_value="mock_token"):
        with patch.object(spotify_engine, "create_client") as mock_client:
            sp = MagicMock()
            mock_client.return_value = sp

            # Return different items depending on user
            sp.current_user_saved_tracks.return_value = {
                "items": [{"track": {"artists": [{"name": "Pond"}]}}]
            }
            sp.current_user_top_artists.return_value = {
                "items": [{"name": "Lankum"}]
            }
            sp.current_user_playlists.return_value = {
                "items": [
                    {"id": "dw_1", "name": "Discover Weekly"}
                ]
            }
            sp.playlist_tracks.return_value = {
                "items": [{"track": {"artists": [{"name": "Goat Girl"}]}}]
            }

            combined = spotify_engine.get_combined_taste_profile(
                elliott_refresh_token="mock_tok_elliott",
                chloe_refresh_token="mock_tok_chloe",
            )

            assert "pond" in combined.combined_direct
            assert "lankum" in combined.combined_direct
            assert "goat girl" in combined.combined_discovery
