#!/usr/bin/env python3
"""Interactive 1-click Spotify OAuth setup tool for Elliott and Chloe.

Opens a local browser authorization window, exchanges the OAuth code,
and updates SPOTIFY_ELLIOTT_REFRESH_TOKEN or SPOTIFY_CHLOE_REFRESH_TOKEN in .env.
"""

import argparse
import http.server
import logging
import os
import re
import socketserver
import urllib.parse
import webbrowser
from pathlib import Path
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SpotifySetup")

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES = "user-library-read playlist-read-private playlist-read-collaborative user-top-read"
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTH_URL = "https://accounts.spotify.com/authorize"


def update_env_file(key: str, value: str):
    """Write or update a key-value pair in .env file."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    content = ENV_PATH.read_text(encoding="utf-8")
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, content, flags=re.MULTILINE):
        new_content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\n{key}={value}\n"

    ENV_PATH.write_text(new_content, encoding="utf-8")
    logger.info(f"Updated {key} in .env")


def run_auth_flow(user_name: str):
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n❌ Error: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET is missing from .env.")
        print("Please set your Spotify Developer App credentials in .env first.")
        return

    user_clean = user_name.strip().lower()
    env_key = "SPOTIFY_ELLIOTT_REFRESH_TOKEN" if "elliott" in user_clean else "SPOTIFY_CHLOE_REFRESH_TOKEN"
    display_name = "Elliott" if "elliott" in user_clean else "Chloe"

    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
        "show_dialog": "true",
    }
    target_url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    auth_code_holder = {}

    class CallbackHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/callback":
                qs = urllib.parse.parse_qs(parsed.query)
                if "code" in qs:
                    auth_code_holder["code"] = qs["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    html = f"""
                    <html>
                    <body style="font-family: system-ui; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 90vh;">
                        <div style="background: #1e293b; padding: 32px 48px; border-radius: 12px; border: 1px solid #334155; text-align: center;">
                            <h2 style="color: #10b981;">✓ Spotify Connected for {display_name}!</h2>
                            <p style="color: #94a3b8;">You can now close this tab and return to the terminal.</p>
                        </div>
                    </body>
                    </html>
                    """
                    self.wfile.write(html.encode("utf-8"))
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Authorization code not found.")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            return  # Suppress request logging

    print(f"\n=======================================================")
    print(f"  SPOTIFY 1-CLICK AUTHENTICATION FOR {display_name.upper()}")
    print(f"=======================================================")
    print(f"Opening browser for Spotify authorization...")
    print(f"If the browser doesn't open automatically, visit:")
    print(f"  {target_url}\n")

    webbrowser.open(target_url)

    with socketserver.TCPServer(("127.0.0.1", 8888), CallbackHandler) as httpd:
        httpd.timeout = 60
        httpd.handle_request()

    code = auth_code_holder.get("code")
    if not code:
        print("❌ Authorization timed out or failed. Please try again.")
        return

    print("✓ Received authorization code. Exchanging for refresh token...")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"❌ Failed to exchange code for token: {resp.text}")
        return

    token_data = resp.json()
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        print("❌ No refresh token returned in response.")
        return

    update_env_file(env_key, refresh_token)
    print(f"\n🎉 SUCCESS! {env_key} has been saved to .env.")
    print(f"Live Curator will now dynamically sync {display_name}'s Spotify listening history before each digest.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spotify OAuth Setup Tool")
    parser.add_argument(
        "--user",
        choices=["elliott", "chloe"],
        default="elliott",
        help="Target user to authenticate (elliott or chloe)",
    )
    args = parser.parse_args()
    run_auth_flow(args.user)
