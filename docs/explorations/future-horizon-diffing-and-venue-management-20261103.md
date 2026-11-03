---
date: "2026-11-03"
exploration_type: research
component: "digest-orchestration-and-venue-management"
status: concluded
time_box: "45m"
outcome: proceed_to_plan
last_referenced: "2026-11-03"
tags:
  - rolling-horizon
  - delta-highlighting
  - event-diffing
  - in-app-venue-management
  - ticketmaster-portal
---

# Exploration: Rolling Future Horizon, Delta Announcement Highlighting & In-App Venue Management

## Question
1. How should the Live Curator Engine transition from a strict single-month window to an open-ended rolling future horizon while statefully tracking and highlighting newly announced shows against the previous digest?
2. How can Elliott & Chloe manage and reassign venues and neighbourhoods directly in a user-friendly app UI (without editing YAML or code)?
3. Why did the Ticketmaster developer portal direct link return a 404 error, and what is the exact foolproof path to acquire the Consumer Key?

---

## Scope
- **Time-box:** 45 minutes
- **Success Criteria:**
  - Clear architectural design for persistent event delta tracking (`seen_events` SQLite table) and `[🔥 NEW ANNOUNCEMENT]` badges.
  - User-friendly UI pattern for venue and neighbourhood management with atomic YAML updates.
  - Exact navigation path and troubleshooting for Ticketmaster Developer Portal.
- **Out of Scope:** Multi-tenant cloud hosting; authentication for local web management.

---

## Best Practices Research

### 1. Rolling Future Horizon vs. Single Month
- **Industry Standard (Songkick, Bandsintown, Dice, Resident Advisor):**
  - Touring concert tours and headliner arena dates are announced 3 to 12 months in advance.
  - Filtering strictly by "November 2026" causes major missed opportunities because fans cannot buy tickets for spring/summer shows before they sell out.
  - Standard practice: The discovery horizon encompasses **all upcoming events** ($\text{date} \ge \text{today}$), grouped by month or chronologically, with an option to filter by month.

### 2. Event Delta Highlighting & Digest Diffing
- **Industry Standard (Substack, Product Hunt, Event Newsletter Curators):**
  - The single highest-value signal for recurring digest subscribers is: *"What is new since the last edition?"*
  - Recommended mechanisms:
    - **Visual Prominence:** A vibrant, distinct badge (`🔥 NEW ANNOUNCEMENT` or `🆕 JUST ADDED`) next to newly discovered shows.
    - **Dedicated Quick Filter:** A tab or filter button `[🆕 New Since Last Digest (N)]` so users can scan newly added shows in 10 seconds.
    - **Subject Line Lead:** Highlighting new announcements in the email subject (e.g. `[Live Curator London] 14 New Shows Added — Oasis, Greg Mendez`).
  - **State Tracking Pattern:**
    - An event is uniquely identified by its platform UID or canonical hash: `sha256(venue_name + title + date_str)`.
    - Persist seen events in SQLite with `first_seen_at`, `last_seen_at`, and `digest_run_id`.
    - Events discovered during the current run that have no record in the database prior to the run are flagged as `is_new_announcement = True`.

### 3. In-App User-Friendly Configuration Management
- **Local Tool / CLI Companion UI Best Practices:**
  - Non-technical users find editing YAML, JSON, or code friction-heavy and error-prone (indentation bugs, accidental syntax corruption).
  - Best-in-class pattern: A lightweight local web UI companion (via Python's built-in `http.server` or `FastAPI`/`Flask`).
  - When the user runs the engine with `--ui` (or clicks "⚙️ Manage Venues" in the preview), a local lightweight management interface allows:
    - Reassigning any venue's neighbourhood from a dropdown.
    - Adding new venues (Name, Platform, Slug/Keyword, Area).
    - Toggling venues active/inactive.
    - Saving changes atomically back to `config/venues.yaml`.

---

## Multi-Order Analysis (Think Hard)

### Direct Effects (1st Order)
- Events announced for future months (e.g., December, January, next summer) will appear in the digest rather than being discarded.
- First-time runs will track all current shows; subsequent runs will identify and spotlight newly announced events.
- Users can customize neighbourhood assignments via point-and-click dropdowns without opening code editors.

### Ripple Effects (2nd-4th Order)
- **2nd Order:** Email size could grow if too many future events are included without pagination or tier filtering. The tabbed single-page UI helps isolate high-tier shows from long lists.
- **3rd Order:** SQLite state persistence ensures idempotent digest generation. If run multiple times in a single day, the same run ID avoids false "new" triggers.
- **4th Order:** The engine evolves from a monthly batch script into an ongoing live concert intelligence engine for Elliott & Chloe.

### Stakeholder Impact Matrix
| Stakeholder | Potential Impact | Severity |
|-------------|-----------------|----------|
| Elliott & Chloe | Can grab tickets for newly announced shows immediately; easily rearrange neighbourhoods via UI | High Positive |
| Engine Performance | Ingesting multi-month listings requires efficient SQLite caching and pagination | Low / Managed |
| System Maintainability | Clean separation between SQLite state cache and YAML configuration | Neutral |

---

## Findings & Architectural Blueprint

### Component 1: Event Diffing & Delta Persistence
Create `src/processing/event_diff_engine.py`:
- SQLite database table `seen_events`:
  ```sql
  CREATE TABLE IF NOT EXISTS seen_events (
      event_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      venue_name TEXT NOT NULL,
      venue_area TEXT NOT NULL,
      start_time TEXT NOT NULL,
      ticket_url TEXT NOT NULL,
      platform TEXT NOT NULL,
      first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      first_digest_date TEXT NOT NULL
  );
  ```
- During classification:
  - Check each event against `seen_events`.
  - If not previously seen, tag `event.is_new = True`.
  - In `templates/digest.html`, render a glowing `🔥 NEW ANNOUNCEMENT` pill and support a `[🆕 New (N)]` quick filter tab.

### Component 2: In-App Venue & Neighbourhood Manager
Implement a lightweight local web management interface:
- Launch via `python main.py --ui` or a built-in server in `main.py`.
- Interface features:
  - Clean web dashboard at `http://127.0.0.1:8765`.
  - List of all 50 venues with neighbourhood dropdowns (*Dalston*, *Islington & Angel*, *Camden*, *Stoke Newington*, *Shoreditch*, *Stadiums & Arenas*).
  - Ability to create custom neighbourhood names on the fly.
  - "Add Venue" form (Name, Platform, DICE Slug / TM Keyword, Area).
  - "Save & Re-run Curator" button that writes directly to `config/venues.yaml` and refreshes the preview.

### Component 3: Ticketmaster Developer Portal 404 Resolution
- **Root Cause of 404:** The URL `https://developer.ticketmaster.com/apps/` is an authenticated route. When accessed in a browser without an active session cookie, Ticketmaster's web router fails to redirect to the authentication gateway and instead outputs a standard `404 Not Found`.
- **Guaranteed Navigation Path:**
  1. Visit root: `https://developer.ticketmaster.com/`
  2. Click **"Sign In"** in the top navigation bar.
  3. Enter credentials (or Register if new).
  4. Once signed in, click your name/email in the top-right navigation bar $\rightarrow$ select **"My Apps"** from the dropdown menu.
  5. Select the application (or click "+ Create New App").
  6. Look for **"Consumer Key"** under App Keys (this 32-character string is the API Key).

---

## Long-Term Implications
- **6 months:** Historical digest database enables tracking ticket sell-out rates and artist return intervals.
- **1 year:** Provides complete archive of London live music attendance and discovery history.
- **Reversibility:** High (Type 2 decision). SQLite database is a cache that can be reset or rebuilt at any time.

---

## Decision & Recommendation
- **Decision:** Proceed with `/plan` to implement:
  1. Rolling future horizon and SQLite delta tracking (`seen_events`) with `[🔥 NEW ANNOUNCEMENT]` badges and filter tab.
  2. In-app local web UI (`main.py --ui`) for point-and-click venue and neighbourhood management.
  3. Clear step-by-step guidance for the Ticketmaster portal.

---

## References
- [ADR-001: Live Curator Engine Architecture and Ingestion Strategy](../decisions/001-engine-architecture-and-data-ingestion.md)
- [ADR-002: Ticketmaster Discovery Ingestion and Single-Page Tier Cycling](../decisions/002-ticketmaster-discovery-and-single-page-tier-cycling.md)
- [Live Curator Solution Architecture](../solutions/integration_issue/live-curator-engine-architecture.md)
