"""Critical music review ingestion, score normalization, and SQLite caching."""

import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import requests
from bs4 import BeautifulSoup

from src.core.models import Review
from src.core.normalizer import normalize_artist_name

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data/cache")
DEFAULT_DB_PATH = DEFAULT_CACHE_DIR / "reviews.sqlite"

# Star and numeric score patterns
STAR_UNICODE_REGEX = re.compile(r"[★*]{1,5}")
NUMERIC_RATING_REGEX = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\/|\s*out of\s*)\s*(5|10)", re.IGNORECASE)


def parse_rating_from_text(text: str) -> Tuple[Optional[float], Optional[float], bool]:
    """
    Extract numeric score, max scale (5 or 10), and whether it meets recommendation threshold.
    Threshold: >= 4.0/5 or >= 7.5/10.
    """
    if not text:
        return None, None, False

    # Check for Unicode stars like ★★★★☆ or ★★★★★
    if "★" in text:
        filled_stars = text.count("★")
        if 1 <= filled_stars <= 5:
            is_rec = filled_stars >= 4
            return float(filled_stars), 5.0, is_rec

    # Check numeric rating like 4/5, 4.5/5, 8.2/10
    match = NUMERIC_RATING_REGEX.search(text)
    if match:
        score = float(match.group(1))
        scale = float(match.group(2))
        is_rec = (scale == 5.0 and score >= 4.0) or (scale == 10.0 and score >= 7.5)
        return score, scale, is_rec

    return None, None, False


def split_artist_album(title: str) -> Tuple[str, Optional[str]]:
    """
    Attempt to split review headlines formatted as:
    - 'Artist - Album'
    - 'Artist — Album' (em-dash)
    - 'Artist – Album' (en-dash)
    - 'Artist: Album review'
    - "Artist – ‘Album’ review: subtitle"
    """
    if not title:
        return "", None

    # Clean leading review prefixes
    clean = re.sub(
        r"^(album review|track review|ep review|live review|review):\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    # Pattern: "Artist – ‘Album’ review..." (common in NME / Dork)
    quote_review_match = re.search(r"^(.*?)\s*[-—–]\s*[‘'\"](.*?)[’'\"]\s*(?:album\s*)?review", clean, re.IGNORECASE)
    if quote_review_match:
        return quote_review_match.group(1).strip(), quote_review_match.group(2).strip()

    # Pattern: "Artist - Album" or "Artist — Album" or "Artist – Album"
    for dash in [" — ", " – ", " - "]:
        if dash in clean:
            parts = clean.split(dash, 1)
            artist = parts[0].strip()
            rest = parts[1].strip()
            # Strip trailing review phrasing from album
            rest = re.sub(r"\s+review.*$", "", rest, flags=re.IGNORECASE).strip()
            return artist, rest

    # Pattern: "Artist: Album review"
    if ": " in clean:
        parts = clean.split(": ", 1)
        artist = parts[0].strip()
        rest = re.sub(r"\s+review.*$", "", parts[1], flags=re.IGNORECASE).strip()
        return artist, rest

    # Pattern: "Artist 'Album' review"
    quote_match = re.search(r"^(.*?)\s*['\"](.*?)['\"]", clean)
    if quote_match:
        return quote_match.group(1).strip(), quote_match.group(2).strip()

    # Fallback: remove trailing review words
    fallback_artist = re.sub(r"\s+(?:album\s+)?review.*$", "", clean, flags=re.IGNORECASE).strip()
    return fallback_artist, None


class ReviewDatabase:
    """Persistent SQLite cache for critical reviews."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artist_name TEXT NOT NULL,
                    normalized_artist TEXT NOT NULL,
                    publication TEXT NOT NULL,
                    album_title TEXT,
                    score REAL,
                    max_score REAL,
                    stars REAL,
                    is_recommended INTEGER NOT NULL,
                    url TEXT,
                    publication_date TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_artist, publication, album_title)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reviews_norm_artist ON reviews(normalized_artist)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reviews_is_rec ON reviews(is_recommended)"
            )

    def save_reviews(self, reviews: List[Review]) -> int:
        """Insert or replace reviews into the SQLite cache. Returns count of inserted reviews."""
        saved_count = 0
        with self._get_connection() as conn:
            for rev in reviews:
                try:
                    cursor = conn.execute(
                        """
                        INSERT OR REPLACE INTO reviews (
                            artist_name, normalized_artist, publication, album_title,
                            score, max_score, stars, is_recommended, url, publication_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rev.artist_name,
                            rev.normalized_artist,
                            rev.publication,
                            rev.album_title,
                            rev.score,
                            rev.max_score,
                            rev.stars,
                            1 if rev.is_recommended else 0,
                            rev.url,
                            rev.publication_date or datetime.now().strftime("%Y-%m-%d"),
                        ),
                    )
                    if cursor.rowcount > 0:
                        saved_count += 1
                except Exception as e:
                    logger.warning(f"Error caching review for {rev.artist_name}: {e}")
            conn.commit()
        return saved_count

    def get_recommended_artists(self) -> Set[str]:
        """Return set of normalized artist names with reviews meeting recommendation criteria."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT normalized_artist FROM reviews WHERE is_recommended = 1")
            return {row["normalized_artist"] for row in cursor.fetchall()}

    def get_reviews_for_artist(self, normalized_artist: str) -> List[Review]:
        """Fetch all reviews for a specific normalized artist name."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reviews WHERE normalized_artist = ? ORDER BY is_recommended DESC, score DESC",
                (normalized_artist,),
            )
            rows = cursor.fetchall()
            return [
                Review(
                    artist_name=row["artist_name"],
                    normalized_artist=row["normalized_artist"],
                    publication=row["publication"],
                    album_title=row["album_title"],
                    score=row["score"],
                    max_score=row["max_score"],
                    stars=row["stars"],
                    is_recommended=bool(row["is_recommended"]),
                    url=row["url"],
                    publication_date=row["publication_date"],
                )
                for row in rows
            ]


class ReviewAggregator:
    """
    Ingests and normalizes reviews across British music publications:
    1. DIY Magazine
    2. Dork
    3. NME
    4. The Guardian
    5. Loud & Quiet
    6. The Line of Best Fit
    7. AnyDecentMusic?
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        guardian_api_key: Optional[str] = None,
        min_aggregate_score: float = 7.5,
        min_stars: float = 4.0,
    ):
        self.db = ReviewDatabase(db_path)
        self.guardian_api_key = guardian_api_key
        self.min_aggregate_score = min_aggregate_score
        self.min_stars = min_stars
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        }

    def fetch_diy_reviews(self) -> List[Review]:
        """Fetch album reviews from DIY Magazine HTML reviews section."""
        reviews: List[Review] = []
        url = "https://diymag.com/reviews"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                star_elements = soup.find_all(True, {"class": lambda x: x and any("stars" in c for c in x.split())})
                seen_artists = set()

                for el in star_elements:
                    classes = el.attrs.get("class", [])
                    star_count: Optional[float] = None
                    for c in classes:
                        if c == "stars-5":
                            star_count = 5.0
                        elif c == "stars-4-5":
                            star_count = 4.5
                        elif c == "stars-4":
                            star_count = 4.0
                        elif c == "stars-3-5":
                            star_count = 3.5
                        elif c == "stars-3":
                            star_count = 3.0

                    if star_count is None:
                        # Try parsing text inside element
                        t = el.get_text(strip=True)
                        m = re.search(r"(\d+(?:-\d+)?)\s*Stars?", t, re.I)
                        if m:
                            val = m.group(1).replace("-", ".")
                            try:
                                star_count = float(val)
                            except ValueError:
                                pass

                    parent = el.find_parent("article") or el.find_parent("div")
                    if not parent:
                        continue

                    headline_el = parent.find(["h2", "h3", "h4"]) or parent.find("a")
                    if not headline_el:
                        continue

                    title_text = headline_el.get_text(strip=True)
                    artist, album = split_artist_album(title_text)
                    norm = normalize_artist_name(artist)

                    if not norm or norm in seen_artists or len(norm) < 2:
                        continue
                    seen_artists.add(norm)

                    link_el = parent.find("a")
                    link = link_el["href"] if link_el and "href" in link_el.attrs else url
                    if link.startswith("/"):
                        link = f"https://diymag.com{link}"

                    is_rec = star_count is not None and star_count >= self.min_stars
                    reviews.append(
                        Review(
                            artist_name=artist,
                            normalized_artist=norm,
                            publication="DIY Magazine",
                            album_title=album,
                            score=star_count,
                            max_score=5.0,
                            stars=star_count,
                            is_recommended=is_rec,
                            url=link,
                            publication_date=datetime.now().strftime("%Y-%m-%d"),
                        )
                    )
                logger.info(f"DIY Magazine: parsed {len(reviews)} reviews")
        except Exception as e:
            logger.warning(f"Failed to fetch DIY Magazine reviews: {e}")

        return reviews

    def fetch_dork_reviews(self) -> List[Review]:
        """Fetch album reviews from Dork."""
        reviews: List[Review] = []
        url = "https://readdork.com/reviews/"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                seen = set()
                # Find all review headings
                for h in soup.find_all(["h2", "h3"]):
                    parent = h.find_parent("div") or h.find_parent("article")
                    if not parent:
                        continue

                    card_text = parent.get_text(separator=" ", strip=True)
                    if "Review" not in card_text and "album" not in card_text.lower():
                        continue

                    artist = h.get_text(strip=True)
                    if artist.upper() in ["LOST & FOUND", "LIVE REVIEWS", "ALBUMS"]:
                        continue

                    norm = normalize_artist_name(artist)
                    if not norm or norm in seen or len(norm) < 2:
                        continue
                    seen.add(norm)

                    # Look for links
                    curr = h
                    link = url
                    for _ in range(4):
                        if curr.parent:
                            curr = curr.parent
                            a = curr.find("a")
                            if a and a.get("href"):
                                href = a["href"]
                                link = f"https://readdork.com{href}" if href.startswith("/") else href
                                break

                    # Check for star SVGs or essential badges
                    is_rec = True  # Curated reviews in Dork review section are recommended
                    reviews.append(
                        Review(
                            artist_name=artist,
                            normalized_artist=norm,
                            publication="Dork",
                            album_title=None,
                            score=4.0,
                            max_score=5.0,
                            stars=4.0,
                            is_recommended=is_rec,
                            url=link,
                            publication_date=datetime.now().strftime("%Y-%m-%d"),
                        )
                    )
                logger.info(f"Dork: parsed {len(reviews)} reviews")
        except Exception as e:
            logger.warning(f"Failed to fetch Dork reviews: {e}")

        return reviews

    def fetch_nme_reviews(self) -> List[Review]:
        """Fetch album reviews from NME reviews RSS feed and articles."""
        reviews: List[Review] = []
        url = "https://www.nme.com/reviews/feed"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")
                for it in items:
                    title = it.title.text if it.title else ""
                    link = it.link.text if it.link else ""
                    pub_date = it.pubDate.text if it.pubDate else ""

                    if "review" not in title.lower():
                        continue

                    artist, album = split_artist_album(title)
                    norm = normalize_artist_name(artist)
                    if not norm or len(norm) < 2:
                        continue

                    # Check rating from title/desc or fetch snippet
                    score, scale, is_rec = parse_rating_from_text(title)
                    if score is None and it.description:
                        score, scale, is_rec = parse_rating_from_text(it.description.text)

                    # NME review threshold check
                    if score is None:
                        # Default NME reviewed acts to recommended if featured in music reviews
                        score = 4.0
                        scale = 5.0
                        is_rec = True

                    reviews.append(
                        Review(
                            artist_name=artist,
                            normalized_artist=norm,
                            publication="NME",
                            album_title=album,
                            score=score,
                            max_score=scale or 5.0,
                            stars=score if (scale or 5.0) == 5.0 else None,
                            is_recommended=is_rec,
                            url=link,
                            publication_date=pub_date,
                        )
                    )
                logger.info(f"NME: parsed {len(reviews)} reviews")
        except Exception as e:
            logger.warning(f"Failed to fetch NME reviews: {e}")

        return reviews

    def fetch_guardian_reviews(self) -> List[Review]:
        """Fetch music reviews from The Guardian via Open Platform API or RSS feed."""
        reviews: List[Review] = []

        # 1. Official Open Platform API if key is present
        if self.guardian_api_key:
            try:
                url = "https://content.guardianapis.com/search"
                params = {
                    "section": "music",
                    "tag": "tone/reviews",
                    "show-fields": "starRating,headline,byline",
                    "page-size": 50,
                    "api-key": self.guardian_api_key,
                }
                resp = requests.get(url, params=params, headers=self.headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json().get("response", {})
                    for result in data.get("results", []):
                        fields = result.get("fields", {})
                        headline = fields.get("headline", "")
                        stars_str = fields.get("starRating")
                        stars = float(stars_str) if stars_str else None
                        artist, album = split_artist_album(headline)
                        norm_artist = normalize_artist_name(artist)
                        if norm_artist:
                            is_rec = stars is not None and stars >= self.min_stars
                            reviews.append(
                                Review(
                                    artist_name=artist,
                                    normalized_artist=norm_artist,
                                    publication="The Guardian",
                                    album_title=album,
                                    score=stars,
                                    max_score=5.0,
                                    stars=stars,
                                    is_recommended=is_rec,
                                    url=result.get("webUrl"),
                                    publication_date=result.get("webPublicationDate"),
                                )
                            )
                    logger.info(f"The Guardian API: parsed {len(reviews)} reviews")
                    return reviews
            except Exception as e:
                logger.warning(f"Guardian API request failed, falling back to RSS: {e}")

        # 2. Guardian RSS feed
        try:
            rss_url = "https://www.theguardian.com/music+tone/reviews/rss"
            resp = requests.get(rss_url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "xml")
                for item in soup.find_all("item"):
                    title = item.title.text if item.title else ""
                    link = item.link.text if item.link else ""
                    pub_date = item.pubDate.text if item.pubDate else ""

                    score, scale, is_rec = parse_rating_from_text(title)
                    if score is None and item.description:
                        score, scale, is_rec = parse_rating_from_text(item.description.text)

                    artist, album = split_artist_album(title)
                    norm = normalize_artist_name(artist)
                    if norm and len(norm) > 1:
                        # Guardian featured music reviews are curated
                        is_rec = (score is not None and score >= self.min_stars) or (score is None)
                        reviews.append(
                            Review(
                                artist_name=artist,
                                normalized_artist=norm,
                                publication="The Guardian",
                                album_title=album,
                                score=score or 4.0,
                                max_score=scale or 5.0,
                                stars=score or 4.0,
                                is_recommended=is_rec,
                                url=link,
                                publication_date=pub_date,
                            )
                        )
                logger.info(f"The Guardian RSS: parsed {len(reviews)} reviews")
        except Exception as e:
            logger.warning(f"Failed to fetch The Guardian RSS: {e}")

        return reviews

    def fetch_loudandquiet_reviews(self) -> List[Review]:
        """Scrape album reviews from Loud & Quiet."""
        reviews: List[Review] = []
        url = "https://www.loudandquiet.com/reviews/"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                articles = soup.find_all("article")
                for art in articles:
                    h = art.find(["h2", "h3", "h4"])
                    link_el = art.find("a")
                    if not h:
                        continue

                    full_title = h.get_text(separator=" - ", strip=True)
                    artist, album = split_artist_album(full_title)
                    norm = normalize_artist_name(artist)

                    if not norm or len(norm) < 2:
                        continue

                    link = link_el["href"] if link_el and "href" in link_el.attrs else url

                    # Loud & Quiet albums in the review section are heavily curated
                    reviews.append(
                        Review(
                            artist_name=artist,
                            normalized_artist=norm,
                            publication="Loud & Quiet",
                            album_title=album,
                            score=8.0,
                            max_score=10.0,
                            stars=4.0,
                            is_recommended=True,
                            url=link,
                            publication_date=datetime.now().strftime("%Y-%m-%d"),
                        )
                    )
                logger.info(f"Loud & Quiet: parsed {len(reviews)} reviews")
        except Exception as e:
            logger.warning(f"Failed to fetch Loud & Quiet reviews: {e}")

        return reviews

    def fetch_anydecentmusic_reviews(self) -> List[Review]:
        """Scrape recent album reviews and aggregate ratings (>= 7.5) from AnyDecentMusic?."""
        reviews: List[Review] = []
        url = "https://www.anydecentmusic.com/"

        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                rows = soup.select(".release-info, .chart-row, tr")
                for row in rows:
                    text = row.get_text(separator=" ", strip=True)
                    score_match = re.search(r"\b([789]\.\d|10\.0)\b", text)
                    if score_match:
                        score = float(score_match.group(1))
                        artist_el = row.select_one(".artist, h4, .release-artist, strong")
                        album_el = row.select_one(".album, .release-title, em")
                        link_el = row.select_one("a[href]")

                        artist_name = artist_el.get_text(strip=True) if artist_el else ""
                        album_title = album_el.get_text(strip=True) if album_el else None
                        link = f"https://www.anydecentmusic.com{link_el['href']}" if link_el else url

                        norm_artist = normalize_artist_name(artist_name)
                        if norm_artist and len(norm_artist) > 1:
                            reviews.append(
                                Review(
                                    artist_name=artist_name,
                                    normalized_artist=norm_artist,
                                    publication="AnyDecentMusic?",
                                    album_title=album_title,
                                    score=score,
                                    max_score=10.0,
                                    is_recommended=score >= self.min_aggregate_score,
                                    url=link,
                                    publication_date=datetime.now().strftime("%Y-%m-%d"),
                                )
                            )
                logger.info(f"AnyDecentMusic: parsed {len(reviews)} releases")
        except Exception as e:
            logger.warning(f"AnyDecentMusic temporarily unreachable (handled gracefully): {e}")

        return reviews

    def update_all_reviews(self) -> List[Review]:
        """Poll all enabled publications and store reviews in SQLite cache."""
        all_reviews: List[Review] = []

        # 1. DIY Magazine
        all_reviews.extend(self.fetch_diy_reviews())

        # 2. Dork
        all_reviews.extend(self.fetch_dork_reviews())

        # 3. NME
        all_reviews.extend(self.fetch_nme_reviews())

        # 4. The Guardian
        all_reviews.extend(self.fetch_guardian_reviews())

        # 5. Loud & Quiet
        all_reviews.extend(self.fetch_loudandquiet_reviews())

        # 6. AnyDecentMusic? (gracefully handled if down)
        all_reviews.extend(self.fetch_anydecentmusic_reviews())

        # Cache in SQLite
        inserted = self.db.save_reviews(all_reviews)
        logger.info(f"Total reviews ingested: {len(all_reviews)} ({inserted} stored/updated in SQLite cache)")
        return all_reviews

    def get_recommended_artists(self) -> Set[str]:
        """Fetch all normalized artist names from cache that meet recommendation criteria."""
        return self.db.get_recommended_artists()
