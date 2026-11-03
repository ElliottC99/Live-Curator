#!/usr/bin/env python3
"""
Interactive Spotify OAuth setup script for Elliott and Chloe.
Captures long-lived refresh tokens and writes them directly into .env.

Usage:
    .venv/bin/python3 scripts/auth_spotify.py
    .venv/bin/python3 scripts/auth_spotify.py --user Elliott
    .venv/bin/python3 scripts/auth_spotify.py --user Chloe
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import load_config
from src.ingestion.spotify_engine import SPOTIFY_SCOPES

ENV_FILE = PROJECT_ROOT / ".env"


def update_env_variable(key: str, value: str):
    """Update or append an environment variable in .env."""
    lines = []
    found = False

    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def authorize_user(user_name: str, client_id: str, client_secret: str, redirect_uri: str) -> str:
    """Run an interactive OAuth authorization flow for a specific user."""
    print("\n" + "=" * 70)
    print(f"🎵 Authorizing Spotify Account for: {user_name.upper()}")
    print("=" * 70)
    print(f"Opening browser for {user_name} to log in and approve permissions.")
    print("NOTE: If the wrong Spotify user is logged into the browser, please switch accounts on Spotify.\n")

    # Use a temporary cache file specific to this user during initial auth
    cache_path = PROJECT_ROOT / f".spotify_cache_{user_name.lower()}"

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SPOTIFY_SCOPES),
        cache_path=str(cache_path),
        open_browser=True,
        show_dialog=True,  # Forces login dialog so Elliott & Chloe don't mix accounts
    )

    auth_url = sp_oauth.get_authorize_url()
    print(f"If the browser did not open automatically, visit this URL:\n{auth_url}\n")

    # get_access_token handles local callback server automatically
    token_info = sp_oauth.get_access_token(as_dict=True)

    if not token_info or "refresh_token" not in token_info:
        print(f"❌ Failed to obtain refresh token for {user_name}.")
        sys.exit(1)

    refresh_token = token_info["refresh_token"]

    # Clean up temp cache file so credentials live exclusively in .env
    if cache_path.exists():
        cache_path.unlink()

    env_var_name = f"{user_name.upper()}_SPOTIFY_REFRESH_TOKEN"
    update_env_variable(env_var_name, refresh_token)

    print(f"✅ Successfully authorized {user_name}!")
    print(f"   Stored long-lived token in .env as {env_var_name}")
    return refresh_token


def main():
    parser = argparse.ArgumentParser(description="Authenticate Elliott and Chloe on Spotify")
    parser.add_argument("--user", choices=["Elliott", "Chloe", "Both"], default="Both", help="User to authorize")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    config = load_config()

    if not config.spotify_client_id or not config.spotify_client_secret:
        print("\n❌ Error: Spotify credentials not found in environment or .env!")
        print("\nPlease follow these setup steps:")
        print("1. Go to https://developer.spotify.com/dashboard and create an app.")
        print("2. In App Settings, set Redirect URI to: http://127.0.0.1:8888/callback")
        print("3. Copy your Client ID and Client Secret into .env:")
        print("     SPOTIFY_CLIENT_ID=your_id_here")
        print("     SPOTIFY_CLIENT_SECRET=your_secret_here")
        print("4. Re-run this script!\n")
        sys.exit(1)

    users_to_auth = ["Elliott", "Chloe"] if args.user == "Both" else [args.user]

    for user in users_to_auth:
        authorize_user(
            user_name=user,
            client_id=config.spotify_client_id,
            client_secret=config.spotify_client_secret,
            redirect_uri=config.spotify_redirect_uri,
        )

    print("\n🎉 All requested Spotify authorizations are complete!")
    print("The Live Curator Engine can now run headlessly via cron without login prompts.")


if __name__ == "__main__":
    main()
