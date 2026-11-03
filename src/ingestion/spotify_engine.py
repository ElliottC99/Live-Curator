"""Dual-user Spotify taste profiling engine using OAuth refresh tokens."""

import logging
from typing import Any, Dict, List, Optional, Set
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from src.core.models import CombinedTasteProfile, UserTasteProfile
from src.core.normalizer import normalize_artist_name

logger = logging.getLogger(__name__)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SCOPES = [
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-top-read",
]


class SpotifyEngine:
    """
    Manages OAuth token lifecycle and taste profile extraction for Elliott & Chloe.
    Headless: Uses long-lived refresh tokens stored in .env to acquire fresh access tokens.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: str = "http://127.0.0.1:8888/callback",
        config: Optional[Any] = None,
    ):
        # Support passing Config object as the first positional argument
        if client_id is not None and not isinstance(client_id, str):
            config = client_id
            client_id = None

        self.config = config
        if config is not None:
            self.client_id = client_id or getattr(config, "spotify_client_id", None)
            self.client_secret = client_secret or getattr(config, "spotify_client_secret", None)
            self.redirect_uri = getattr(config, "spotify_redirect_uri", redirect_uri)
        else:
            self.client_id = client_id
            self.client_secret = client_secret
            self.redirect_uri = redirect_uri

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Headless exchange of a long-lived refresh token for a fresh short-lived access token.
        """
        if not self.is_configured:
            logger.error("Spotify Client ID and Secret are not configured.")
            return None

        try:
            response = requests.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("access_token")
        except Exception as e:
            logger.error(f"Failed to refresh Spotify access token: {e}")
            return None

    def create_client(self, access_token: str) -> spotipy.Spotify:
        """Create an authenticated spotipy client instance."""
        return spotipy.Spotify(auth=access_token, requests_timeout=15, retries=3)

    def _fetch_saved_artists(self, sp: spotipy.Spotify, limit_batches: int = 4) -> Set[str]:
        """
        Extract artist names from user's Liked Songs (Saved Tracks).
        limit_batches: 4 batches * 50 tracks = up to 200 recent liked songs.
        """
        artists: Set[str] = set()
        offset = 0
        batch_size = 50

        for _ in range(limit_batches):
            try:
                results = sp.current_user_saved_tracks(limit=batch_size, offset=offset)
                items = results.get("items", [])
                if not items:
                    break

                for item in items:
                    track = item.get("track") or item.get("item")
                    if track and track.get("artists"):
                        for art in track["artists"]:
                            norm = normalize_artist_name(art.get("name", ""))
                            if norm:
                                artists.add(norm)

                offset += len(items)
                if len(items) < batch_size:
                    break
            except Exception as e:
                logger.warning(f"Error fetching saved tracks: {e}")
                break

        return artists

    def _fetch_top_artists(self, sp: spotipy.Spotify) -> Set[str]:
        """Extract top artists across short, medium, and long-term listening history."""
        artists: Set[str] = set()
        for time_range in ["short_term", "medium_term", "long_term"]:
            try:
                results = sp.current_user_top_artists(limit=50, time_range=time_range)
                for item in results.get("items", []):
                    norm = normalize_artist_name(item.get("name", ""))
                    if norm:
                        artists.add(norm)
            except Exception as e:
                logger.warning(f"Error fetching top artists for range {time_range}: {e}")
        return artists

    def _fetch_playlist_and_discovery_artists(
        self,
        sp: spotipy.Spotify,
        max_playlists: int = 50,
        tracks_per_playlist: int = 100,
    ) -> tuple[Set[str], Set[str]]:
        """
        Extract artists from personal playlists, and specifically separate
        'Discover Weekly' and 'Release Radar' into discovery_artists.
        """
        playlist_artists: Set[str] = set()
        discovery_artists: Set[str] = set()

        try:
            playlists = sp.current_user_playlists(limit=max_playlists)
            items = playlists.get("items", [])

            for pl in items:
                name = pl.get("name", "").lower()
                playlist_id = pl.get("id")
                if not playlist_id:
                    continue

                is_discovery = "discover weekly" in name or "release radar" in name

                try:
                    tracks_resp = sp.playlist_tracks(playlist_id, limit=tracks_per_playlist)
                    for track_item in tracks_resp.get("items", []):
                        track = track_item.get("track") or track_item.get("item")
                        if track and track.get("artists"):
                            for art in track["artists"]:
                                norm = normalize_artist_name(art.get("name", ""))
                                if norm:
                                    if is_discovery:
                                        discovery_artists.add(norm)
                                    else:
                                        playlist_artists.add(norm)
                except Exception as ex:
                    logger.debug(f"Could not load tracks for playlist '{name}': {ex}")

        except Exception as e:
            logger.warning(f"Error reading user playlists: {e}")

        return playlist_artists, discovery_artists

    def get_user_taste_profile(
        self,
        user_name: str,
        refresh_token: Optional[str],
    ) -> UserTasteProfile:
        """
        Build an individual UserTasteProfile for either Elliott or Chloe.
        If refresh_token is missing or fails, returns an empty profile with warnings.
        """
        if not refresh_token:
            logger.warning(f"No Spotify refresh token provided for {user_name}. Profile will be empty.")
            return UserTasteProfile(user_name=user_name)

        access_token = self.refresh_access_token(refresh_token)
        if not access_token:
            logger.error(f"Could not acquire access token for {user_name}.")
            return UserTasteProfile(user_name=user_name)

        sp = self.create_client(access_token)
        logger.info(f"Ingesting Spotify taste profile for {user_name}...")

        saved = self._fetch_saved_artists(sp)
        top = self._fetch_top_artists(sp)
        playlists, discovery = self._fetch_playlist_and_discovery_artists(sp)

        profile = UserTasteProfile(
            user_name=user_name,
            saved_artists=saved,
            playlist_artists=playlists,
            top_artists=top,
            discovery_artists=discovery,
        )

        logger.info(
            f"✓ Profile for {user_name}: {len(saved)} saved, {len(playlists)} playlist, "
            f"{len(top)} top, {len(discovery)} discovery artists "
            f"({len(profile.all_direct_artists)} unique direct artists)."
        )
        return profile

    def get_combined_taste_profile(
        self,
        elliott_refresh_token: Optional[str] = None,
        chloe_refresh_token: Optional[str] = None,
    ) -> CombinedTasteProfile:
        """Fetch profiles for Elliott and Chloe and return a combined aggregate."""
        e_token = elliott_refresh_token or (getattr(self.config, "elliott_spotify_refresh_token", None) if self.config else None)
        c_token = chloe_refresh_token or (getattr(self.config, "chloe_spotify_refresh_token", None) if self.config else None)

        elliott_profile = self.get_user_taste_profile("Elliott", e_token)
        chloe_profile = self.get_user_taste_profile("Chloe", c_token)

        combined = CombinedTasteProfile(
            elliott=elliott_profile,
            chloe=chloe_profile,
        )

        logger.info(
            f"✓ Combined taste profiles: {len(combined.combined_direct)} unique direct artists, "
            f"{len(combined.combined_discovery)} discovery artists."
        )
        return combined
