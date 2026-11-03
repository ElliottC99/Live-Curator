#!/usr/bin/env bash
#
# setup_cron.sh — Configure automated monthly dispatch for Live Curator Engine on macOS
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_EXEC="$PROJECT_ROOT/.venv/bin/python3"
MAIN_SCRIPT="$PROJECT_ROOT/main.py"
LOG_DIR="$PROJECT_ROOT/data/logs"
STDOUT_LOG="$LOG_DIR/monthly_digest.log"
STDERR_LOG="$LOG_DIR/monthly_digest_error.log"

mkdir -p "$LOG_DIR"

echo "======================================================================"
echo "Live Curator Engine — macOS Automation Setup"
echo "======================================================================"
echo "Project Root: $PROJECT_ROOT"
echo "Python Exec:  $PYTHON_EXEC"
echo "Main Script:  $MAIN_SCRIPT"
echo "Logs:         $LOG_DIR"
echo ""

# 1. macOS launchd Plist (Recommended for macOS because it wakes on sleep)
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.livecurator.monthly.plist"

mkdir -p "$PLIST_DIR"

cat <<EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.livecurator.monthly</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_EXEC</string>
        <string>$MAIN_SCRIPT</string>
        <string>--send-email</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$STDOUT_LOG</string>
    <key>StandardErrorPath</key>
    <string>$STDERR_LOG</string>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>
</dict>
</plist>
EOF

echo "✓ Created launchd configuration at:"
echo "  $PLIST_FILE"
echo ""
echo "To load and activate the launchd service right now, run:"
echo "  launchctl unload \"$PLIST_FILE\" 2>/dev/null || true"
echo "  launchctl load \"$PLIST_FILE\""
echo ""
echo "----------------------------------------------------------------------"
echo "Alternative: Standard Unix Crontab"
echo "If you prefer traditional crontab (note: crontab may not fire if Mac is asleep):"
echo "Add this line using 'crontab -e':"
echo ""
echo "0 9 1 * * cd \"$PROJECT_ROOT\" && \"$PYTHON_EXEC\" \"$MAIN_SCRIPT\" --send-email >> \"$STDOUT_LOG\" 2>&1"
echo "======================================================================"
