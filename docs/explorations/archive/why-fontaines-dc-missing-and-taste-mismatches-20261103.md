---
title: "Exploration: Root Cause of Missing Stadium Shows (Fontaines D.C.) & Spotify Taste Inaccuracies"
date: "2026-11-03"
exploration_type: "investigation"
component: "ticketing-and-spotify-ingestion"
status: "concluded"
time_box: "30m"
outcome: "proceed_to_plan"
last_referenced: "2026-11-03"
tags:
  - exploration
  - fontaines-dc
  - london-stadium
  - songkick
  - spotify-taste
  - mutual-matches
summary: "Investigation into why Fontaines D.C. at London Stadium was omitted from the harvested dataset, why Lambrini Girls was misattributed to Liked Songs, and how to implement true Spotify OAuth syncing and prominent mutual matching."
---

# Exploration: Root Cause of Missing Stadium Shows & Spotify Taste Inaccuracies

> **Date:** 2026-11-03  
> **Workflow:** `/explore`  
> **Author:** Antigravity Engineering Agent  
> **Questions:**  
> 1. *Why wasn't Fontaines D.C. at London Stadium captured in the harvested event listings?*  
> 2. *Why was Lambrini Girls mislabeled as "In Elliott's Liked Songs"?*  
> 3. *How do we ensure genuine Spotify user data is ingested and mutual matches (when both Elliott & Chloe love an artist or lineup) are prominently tagged?*

---

## 1. Executive Summary

This investigation uncovered two distinct root causes across the data ingestion pipeline:

### Root Cause 1: Dead/Obsolete Songkick Venue URL for London Stadium
- In `config/venues.yaml`, London Stadium was mapped to:  
  `https://www.songkick.com/venues/1817448-london-stadium-queen-elizabeth-olympic-park`
- Live inspection revealed this specific Songkick venue ID (`1817448`) is obsolete and mapped to an old 2012 listing with zero current shows.
- Songkick actually maintains the active stadium concert schedule under:  
  **`https://www.songkick.com/venues/3174414-london-stadium-queen-elizabeth`**
- Querying this active URL immediately returned the confirmed stadium show:
  > **Fontaines D.C. (with Little Simz & Viagra Boys)** @ London Stadium, Queen Elizabeth  
  > *Date:* Friday, July 9, 2027, 17:00  
  > *URL:* `https://www.songkick.com/concerts/43397416-fontaines-dc-at-london-stadium-queen-elizabeth`

### Root Cause 2: Synthetic Seed Data Artifacts vs. Real Spotify OAuth
- **Why Lambrini Girls was labeled "Liked Songs":** In `.env`, `SPOTIFY_ELLIOTT_REFRESH_TOKEN` and `SPOTIFY_CHLOE_REFRESH_TOKEN` are empty. The user has not yet authenticated their real Spotify account.
- When generating the offline fallback seed (`data/seed_tastes.json`), the conversion script arbitrarily placed the first half of `config/tastes.yaml` into `saved_artists` ("Liked Songs") and the other half into `playlist_artists`. Because Lambrini Girls was near the top of the seed file, it was synthetically tagged as "Liked Songs".
- To pull Elliott and Chloe's real Spotify Liked Songs, Top Artists, and Playlists, they simply need to run the newly created 1-click authentication script:
  ```bash
  python3 scripts/setup_spotify_auth.py --user elliott
  python3 scripts/setup_spotify_auth.py --user chloe
  ```

### Key Enhancement: First-Class "Mutual Match" Tagging
- When a show matches **both** Elliott and Chloe (or has a lineup featuring artists from both profiles, like Fontaines D.C. for Elliott and Little Simz for Chloe), the classifier must apply a high-visibility badge:
  `🔥 MUTUAL MATCH: Elliott & Chloe` (or `⭐ Both of You Love This!`) rather than just stacking two individual badges.

---

## 2. Deep Root-Cause Trace

### 2.1 The London Stadium Songkick Mismatch & Title Normalization
In `config/venues.yaml`:
```yaml
  - name: "London Stadium"
    platform: "songkick"
    songkick_url: "https://www.songkick.com/venues/1817448-london-stadium-queen-elizabeth-olympic-park" # <-- BROKEN SLUG
```
When `SongkickEngine.fetch_venue_events()` parsed this URL, it extracted 1 obsolete event from 2012 (`The Timewriter @ Nlo Club`).

By contrast, querying Songkick's active venue directory revealed:
- `3174414-london-stadium-queen-elizabeth`: Contains **Fontaines D.C., Little Simz, and Viagra Boys** (July 9, 2027) and **Take That** (June 25, 2026).
- `1874873-london-stadium`: Contains **Metallica** (July 3 & 5, 2026) and **Take That** (June 27, 2026).

Similarly, Tottenham Hotspur Stadium had a 404 URL (`3983276`), whereas its active Songkick slug is `4368336-tottenham-hotspur-stadium`.

#### Secondary Title Normalization Trap:
Songkick Schema.org formats concert titles as `"Artist @ Venue"` (e.g. `Fontaines D.C. @ London Stadium, Queen Elizabeth`).
1. `split_lineup` and `extract_normalized_acts` did not strip the `" @ "` delimiter, resulting in `normalize_artist_name` generating `"fontaines dc london stadium queen elizabeth"` instead of `"fontaines dc"`.
2. Additionally, `data/seed_events.json` previously only saved top-level title strings rather than preserving parsed `performers` (which includes `['Fontaines D.C.', 'Little Simz', 'Viagra Boys']`).

Both fixes are required:
- Update `config/venues.yaml` with active Songkick slugs (`3174414` for London Stadium and `4368336` for Tottenham).
- Strip ` @ Venue` in `split_lineup` and preserve `performers` in `seed_events.json`.

---

### 2.2 The Synthetic Liked Songs Mislabelling
In `src/core/models.py`, `UserTasteProfile` differentiates between:
- `saved_artists`: Artists from Spotify Liked Songs (`user-library-read`).
- `playlist_artists`: Artists found in user's created/followed playlists.
- `top_artists`: Artists from rolling 4-week listening history.

Because no real OAuth tokens were stored in `.env`, the engine fell back to `data/seed_tastes.json`. The generator script split the YAML `direct_artists` list 50/50:
```python
# The flaw in seed generation:
'saved_artists': direct[:len(direct)//2],     # <-- Mislabeled Lambrini Girls as Liked Songs
'playlist_artists': direct[len(direct)//2:]
```
To fix this:
1. **Accurate Seed Categorization:** Update `config/tastes.yaml` so `saved_artists` and `playlist_artists` are explicitly declared rather than split artificially.
2. **Live Spotify Ingestion:** Running `scripts/setup_spotify_auth.py` captures the real Spotify OAuth token, replacing synthetic data with Elliott's actual Liked Songs and Playlists.

---

### 2.3 Mutual Match Tagging Architecture
Currently, in `src/processing/tier_classifier.py`:
```python
elliott_matches = self._check_user_direct_match(self.taste_profile.elliott, norm_acts, "Elliott")
chloe_matches = self._check_user_direct_match(self.taste_profile.chloe, norm_acts, "Chloe")
```
If both match:
- The event currently gets `event.matches = elliott_matches + chloe_matches`.
- In the template, it renders two separate small pills: `[👨‍💻 In Elliott's ...] [👩‍🎨 In Chloe's ...]`.
- There is no overarching indicator that this is a **Mutual Must-See**.

**Proposed Pattern:**
When `len(elliott_matches) > 0 and len(chloe_matches) > 0`:
1. Mark `event.is_mutual = True`.
2. Insert a dedicated `MatchRationale`:
   ```python
   MatchRationale(
       tier=TierCategory.TIER_1_DIRECT,
       source=MatchSource.SPOTIFY_SAVED_TRACKS,
       matched_act=event.primary_act,
       user="Mutual",
       description="🔥 MUTUAL MATCH: In Both Elliott & Chloe's Music!",
   )
   ```
3. In `templates/digest.html`, render a prominent gold/emerald **`🔥 MUTUAL MATCH: Elliott & Chloe`** badge at the very top of the card.
4. On the web app, Fontaines D.C. at London Stadium will shine as the ultimate Mutual Match (Fontaines for Elliott, Little Simz for Chloe).

---

## 3. Recommended Actions

1. **Fix Venue URLs in `config/venues.yaml`:**
   - London Stadium: `https://www.songkick.com/venues/3174414-london-stadium-queen-elizabeth`
   - Tottenham Hotspur Stadium: `https://www.songkick.com/venues/4368336-tottenham-hotspur-stadium`
2. **Re-harvest Stadium Listings:**
   - Run `scripts/harvest_all_venues.py` to ingest Fontaines D.C. + Little Simz + Viagra Boys into `data/seed_events.json`.
3. **Refine `config/tastes.yaml` & `data/seed_tastes.json`:**
   - Remove Lambrini Girls from `saved_artists` (place in general discovery or playlist).
   - Ensure Fontaines D.C. is in Elliott's tastes and Little Simz is in Chloe's tastes.
4. **Implement Mutual Match Engine in `TierClassifier` & `templates/digest.html`:**
   - Detect when an event or its supporting acts match both Elliott and Chloe.
   - Display a distinct, high-priority `🔥 MUTUAL MATCH` badge.
5. **Prompt User for 1-Click Spotify OAuth:**
   - Guide the user to run `python3 scripts/setup_spotify_auth.py --user elliott` so live Liked Songs are queried directly from Spotify.
