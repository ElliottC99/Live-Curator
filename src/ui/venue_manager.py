"""In-App Venue & Neighbourhood Manager Web UI.

Provides an interactive browser interface to reassign venue neighbourhoods,
add/remove venues, and save changes atomically to config/venues.yaml without editing code.
"""

import json
import logging
import os
import shutil
import socket
import sys
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.core.config import Config, load_config
from src.core.models import Venue

logger = logging.getLogger("VenueManager")

DEFAULT_PORT = 8765

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Live Curator // Venue & Neighbourhood Manager</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: #0c0e14;
      color: #e2e8f0;
      line-height: 1.5;
    }
    header {
      background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
      border-bottom: 2px solid #3b82f6;
      padding: 24px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.5px;
    }
    .badge {
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #60a5fa;
      margin-bottom: 4px;
    }
    .btn {
      cursor: pointer;
      font-size: 13px;
      font-weight: 700;
      border: none;
      border-radius: 6px;
      padding: 8px 16px;
      transition: all 0.2s ease;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .btn-primary {
      background-color: #10b981;
      color: #ffffff;
    }
    .btn-primary:hover { background-color: #059669; }
    .btn-secondary {
      background-color: #3b82f6;
      color: #ffffff;
    }
    .btn-secondary:hover { background-color: #2563eb; }
    .btn-danger {
      background-color: #ef4444;
      color: #ffffff;
      padding: 4px 8px;
      font-size: 11px;
    }
    .btn-danger:hover { background-color: #dc2626; }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px 20px;
    }
    .card {
      background-color: #161a24;
      border: 1px solid #283046;
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 24px;
    }
    .card h2 {
      margin-top: 0;
      font-size: 16px;
      color: #93c5fd;
      text-transform: uppercase;
      letter-spacing: 1px;
      border-bottom: 1px solid #283046;
      padding-bottom: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th {
      text-align: left;
      padding: 10px 12px;
      background-color: #12151e;
      color: #94a3b8;
      font-weight: 700;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
      border-bottom: 2px solid #283046;
    }
    td {
      padding: 10px 12px;
      border-bottom: 1px solid #1f2430;
      vertical-align: middle;
    }
    tr:hover td {
      background-color: #1a202c;
    }
    input[type="text"], select {
      background-color: #1e2433;
      color: #ffffff;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 13px;
      outline: none;
    }
    input[type="text"]:focus, select:focus {
      border-color: #3b82f6;
    }
    .platform-badge {
      display: inline-block;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
    }
    .platform-dice { background-color: #1e1b4b; color: #a5b4fc; border: 1px solid #4338ca; }
    .platform-tm { background-color: #0f172a; color: #38bdf8; border: 1px solid #0284c7; }
    .grid-form {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      align-items: end;
    }
    .form-group label {
      display: block;
      font-size: 11px;
      font-weight: 700;
      color: #94a3b8;
      margin-bottom: 4px;
      text-transform: uppercase;
    }
    .form-group input, .form-group select {
      width: 100%;
    }
    #toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background-color: #064e3b;
      color: #a7f3d0;
      border: 1px solid #10b981;
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      font-weight: 700;
      display: none;
      z-index: 1000;
    }
  </style>
</head>
<body>

  <header>
    <div>
      <div class="badge">LIVE CURATOR ENGINE // CONTROL PANEL</div>
      <h1>Venue &amp; Neighbourhood Manager</h1>
    </div>
    <div style="display: flex; gap: 10px;">
      <button class="btn btn-primary" onclick="saveAllVenues()">&#x1F4BE; Save Changes</button>
      <button class="btn btn-secondary" onclick="triggerRun()">&#x1F680; Save &amp; Run Curator</button>
    </div>
  </header>

  <div class="container">
    
    <!-- Add New Venue Card -->
    <div class="card">
      <h2>&#x2795; Add New Venue</h2>
      <form id="add-venue-form" onsubmit="addNewVenue(event)" class="grid-form">
        <div class="form-group">
          <label>Venue Name</label>
          <input type="text" id="new-name" placeholder="e.g. The Waiting Room" required>
        </div>
        <div class="form-group">
          <label>Platform</label>
          <select id="new-platform" onchange="togglePlatformInputs()">
            <option value="dice">DICE.fm</option>
            <option value="ticketmaster">Ticketmaster</option>
          </select>
        </div>
        <div class="form-group" id="group-slug">
          <label>DICE Slug</label>
          <input type="text" id="new-slug" placeholder="e.g. the-waiting-room-9x9x">
        </div>
        <div class="form-group" id="group-tm" style="display:none;">
          <label>Ticketmaster Keyword</label>
          <input type="text" id="new-tm" placeholder="e.g. London Stadium">
        </div>
        <div class="form-group">
          <label>Neighbourhood / Area</label>
          <input type="text" id="new-area" list="area-datalist" placeholder="e.g. Stoke Newington" required>
          <datalist id="area-datalist"></datalist>
        </div>
        <div class="form-group">
          <label>Address (Optional)</label>
          <input type="text" id="new-address" placeholder="e.g. 175 Stoke Newington High St">
        </div>
        <div class="form-group">
          <button type="submit" class="btn btn-secondary" style="width: 100%;">&#x2795; Add Venue</button>
        </div>
      </form>
    </div>

    <!-- Venue Table Card -->
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h2 style="margin: 0; border: none; padding: 0;">Configured Venues (<span id="venue-count">0</span>)</h2>
        <input type="text" id="search-filter" placeholder="Search venues..." oninput="filterTable()" style="width: 250px;">
      </div>

      <table id="venues-table">
        <thead>
          <tr>
            <th>Venue Name</th>
            <th>Platform</th>
            <th>Neighbourhood (Area)</th>
            <th>Identifier / Slug</th>
            <th>Address</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="venues-tbody">
          <!-- Populated dynamically -->
        </tbody>
      </table>
    </div>

  </div>

  <div id="toast"></div>

  <script>
    var venuesData = [];
    var knownAreas = ["Dalston", "Hackney Central", "Islington & Angel", "Camden", "Stoke Newington", "Shoreditch", "Stadiums & Arenas"];

    function showToast(msg, isError) {
      var t = document.getElementById('toast');
      t.textContent = msg;
      t.style.backgroundColor = isError ? '#991b1b' : '#064e3b';
      t.style.color = isError ? '#fecaca' : '#a7f3d0';
      t.style.borderColor = isError ? '#ef4444' : '#10b981';
      t.style.display = 'block';
      setTimeout(function() { t.style.display = 'none'; }, 3500);
    }

    function togglePlatformInputs() {
      var p = document.getElementById('new-platform').value;
      document.getElementById('group-slug').style.display = (p === 'dice') ? 'block' : 'none';
      document.getElementById('group-tm').style.display = (p === 'ticketmaster') ? 'block' : 'none';
    }

    function loadVenues() {
      fetch('/api/venues')
        .then(function(res) { return res.json(); })
        .then(function(data) {
          venuesData = data.venues || [];
          renderTable();
          updateAreaDatalist();
        })
        .catch(function(err) {
          showToast('Failed to load venues: ' + err, true);
        });
    }

    function updateAreaDatalist() {
      var set = new Set(knownAreas);
      venuesData.forEach(function(v) { if (v.area) set.add(v.area); });
      var dl = document.getElementById('area-datalist');
      dl.innerHTML = '';
      Array.from(set).sort().forEach(function(a) {
        var opt = document.createElement('option');
        opt.value = a;
        dl.appendChild(opt);
      });
    }

    function renderTable() {
      var tbody = document.getElementById('venues-tbody');
      tbody.innerHTML = '';
      document.getElementById('venue-count').textContent = venuesData.length;

      venuesData.forEach(function(venue, index) {
        var tr = document.createElement('tr');
        tr.className = 'venue-row';
        tr.setAttribute('data-name', venue.name.toLowerCase());

        var badgeClass = (venue.platform === 'ticketmaster') ? 'platform-tm' : 'platform-dice';
        var badgeText = (venue.platform === 'ticketmaster') ? 'Ticketmaster' : 'DICE';

        var slugOrKey = venue.dice_slug || venue.tm_keyword || venue.tm_venue_id || '';

        tr.innerHTML = `
          <td><strong>${venue.name}</strong></td>
          <td><span class="platform-badge ${badgeClass}">${badgeText}</span></td>
          <td>
            <input type="text" list="area-datalist" value="${venue.area || ''}" onchange="updateVenueArea(${index}, this.value)" style="width: 180px;">
          </td>
          <td><code style="color: #94a3b8; font-size: 11px;">${slugOrKey}</code></td>
          <td style="color: #94a3b8; font-size: 12px;">${venue.address || '-'}</td>
          <td>
            <button class="btn btn-danger" onclick="deleteVenue(${index})">&#x1F5D1;&#xFE0F; Remove</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function updateVenueArea(index, newArea) {
      if (venuesData[index]) {
        venuesData[index].area = newArea.trim();
        updateAreaDatalist();
      }
    }

    function deleteVenue(index) {
      if (confirm('Are you sure you want to remove "' + venuesData[index].name + '"?')) {
        venuesData.splice(index, 1);
        renderTable();
      }
    }

    function addNewVenue(e) {
      e.preventDefault();
      var name = document.getElementById('new-name').value.trim();
      var platform = document.getElementById('new-platform').value;
      var slug = document.getElementById('new-slug').value.trim();
      var tm = document.getElementById('new-tm').value.trim();
      var area = document.getElementById('new-area').value.trim();
      var address = document.getElementById('new-address').value.trim();

      var newVenue = {
        name: name,
        platform: platform,
        area: area,
        address: address,
        genre_focus: []
      };

      if (platform === 'dice') {
        newVenue.dice_slug = slug;
      } else {
        newVenue.tm_keyword = tm;
      }

      venuesData.unshift(newVenue);
      renderTable();
      updateAreaDatalist();
      document.getElementById('add-venue-form').reset();
      showToast('Added "' + name + '". Click "Save Changes" to persist.');
    }

    function filterTable() {
      var query = document.getElementById('search-filter').value.toLowerCase();
      var rows = document.querySelectorAll('.venue-row');
      rows.forEach(function(row) {
        var name = row.getAttribute('data-name') || '';
        row.style.display = name.includes(query) ? '' : 'none';
      });
    }

    function saveAllVenues() {
      fetch('/api/venues/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ venues: venuesData })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.status === 'ok') {
          showToast('✓ Successfully saved ' + venuesData.length + ' venues to config/venues.yaml!');
        } else {
          showToast('Error: ' + data.message, true);
        }
      })
      .catch(function(err) {
        showToast('Failed to save venues: ' + err, true);
      });
    }

    function triggerRun() {
      saveAllVenues();
      showToast('Running Curator pipeline in background... will open preview.');
      fetch('/api/run', { method: 'POST' })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          showToast('✓ Curator run complete! Preview updated.');
        });
    }

    // Initialize
    loadVenues();
  </script>
</body>
</html>
"""


class VenueManagerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Venue Manager local companion."""

    venues_yaml_path = Path(__file__).resolve().parent.parent.parent / "config" / "venues.yaml"

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            body = HTML_DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/venues":
            venues_list = []
            if self.venues_yaml_path.exists():
                with open(self.venues_yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    venues_list = data.get("venues", [])
            self._send_json({"status": "ok", "venues": venues_list})

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/venues/save":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            try:
                payload = json.loads(post_body.decode("utf-8"))
                venues_to_save = payload.get("venues", [])

                # Clean fields
                cleaned_venues = []
                for v in venues_to_save:
                    item = {
                        "name": v.get("name", "").strip(),
                        "platform": v.get("platform", "dice").strip(),
                        "area": v.get("area", "East London").strip(),
                    }
                    if v.get("dice_slug"):
                        item["dice_slug"] = v["dice_slug"].strip()
                    if v.get("tm_keyword"):
                        item["tm_keyword"] = v["tm_keyword"].strip()
                    if v.get("tm_venue_id"):
                        item["tm_venue_id"] = v["tm_venue_id"].strip()
                    if v.get("address"):
                        item["address"] = v["address"].strip()
                    if v.get("genre_focus"):
                        item["genre_focus"] = v["genre_focus"]
                    cleaned_venues.append(item)

                # Atomic write
                self._atomic_save_venues(cleaned_venues)
                logger.info(f"Updated config/venues.yaml with {len(cleaned_venues)} venues.")
                self._send_json({"status": "ok", "count": len(cleaned_venues)})

            except Exception as e:
                logger.error(f"Error saving venues: {e}")
                self._send_json({"status": "error", "message": str(e)}, status=500)

        elif parsed.path == "/api/run":
            # Re-generate digest preview in background
            try:
                import subprocess
                subprocess.Popen([sys.executable, "main.py", "--preview-html"])
                self._send_json({"status": "ok", "message": "Pipeline started."})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, status=500)
        else:
            self.send_response(404)
            self.end_headers()

    def _atomic_save_venues(self, venues_list: List[Dict[str, Any]]):
        """Atomically persist venues to config/venues.yaml with backup."""
        self.venues_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = self.venues_yaml_path.with_suffix(".yaml.bak")

        # Make backup
        if self.venues_yaml_path.exists():
            shutil.copy2(self.venues_yaml_path, backup_path)

        data = {"venues": venues_list}
        with tempfile.NamedTemporaryFile("w", dir=self.venues_yaml_path.parent, delete=False, encoding="utf-8") as temp:
            yaml.dump(data, temp, sort_keys=False, default_flow_style=False, allow_unicode=True)
            temp_name = temp.name

        os.replace(temp_name, self.venues_yaml_path)


def find_free_port(start_port: int = DEFAULT_PORT) -> int:
    """Find next available TCP port starting from start_port."""
    port = start_port
    while port < start_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
            port += 1
    return start_port


def run_venue_manager_server(port: Optional[int] = None, open_browser: bool = True):
    """Start local venue manager HTTP daemon."""
    server_port = port or find_free_port(DEFAULT_PORT)
    server_address = ("127.0.0.1", server_port)

    server = ThreadingHTTPServer(server_address, VenueManagerHandler)
    url = f"http://127.0.0.1:{server_port}"
    print(f"\n" + "=" * 72)
    print(f"  LIVE CURATOR // VENUE & NEIGHBOURHOOD MANAGER RUNNING")
    print(f"  URL: {url}")
    print("=" * 72 + "\n")

    if open_browser and sys.platform == "darwin":
        import subprocess
        try:
            subprocess.run(["open", url], check=False)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Venue Manager server...")
        server.server_close()
