#!/usr/bin/env bash
# ==============================================================================
# Live Curator — GitHub Setup & Publishing Helper
# Configures your remote repository on GitHub and pushes the project with tags.
# ==============================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

echo "========================================================================"
echo "  LIVE CURATOR ENGINE // GITHUB REPOSITORY SETUP"
echo "========================================================================"
echo ""

# Check git status
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ Error: Not inside a git repository."
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current || echo "main")
echo "📍 Current Git Branch: ${CURRENT_BRANCH}"
echo ""

# Display current remotes
echo "🔍 Checking existing Git remotes:"
git remote -v || true
echo ""

# Check if origin already exists
if git remote get-url origin >/dev/null 2>&1; then
    ORIGIN_URL=$(git remote get-url origin)
    echo "✅ 'origin' remote is already configured:"
    echo "   ${ORIGIN_URL}"
    echo ""
    echo "To push your current code and tags right now, run:"
    echo "   git push -u origin ${CURRENT_BRANCH} --tags"
    echo ""
    echo "To update the remote URL if needed, run:"
    echo "   git remote set-url origin git@github.com:YOUR_USERNAME/live-curator.git"
    exit 0
fi

echo "ℹ️ No 'origin' remote found. Let's configure it."
echo ""

# Check if GitHub CLI (gh) is available
if command -v gh >/dev/null 2>&1; then
    echo "✨ GitHub CLI (gh) detected!"
    if gh auth status >/dev/null 2>&1; then
        echo "✅ Authenticated with GitHub via gh CLI."
        echo ""
        echo "You can create a private or public repository on GitHub automatically by running:"
        echo "   gh repo create live-curator --private --source=. --remote=origin --push"
        echo ""
    else
        echo "⚠️ gh CLI is installed but not authenticated. Run: gh auth login"
    fi
else
    echo "💡 Note: GitHub CLI (gh) is not installed."
fi

echo "========================================================================"
echo "MANUAL GITHUB SETUP STEPS:"
echo "1. Go to https://github.com/new"
echo "2. Create a repository named 'live-curator' (do not initialize with README/license)"
echo "3. Add the remote in your terminal:"
echo "   git remote add origin git@github.com:YOUR_USERNAME/live-curator.git"
echo "   (or: git remote add origin https://github.com/YOUR_USERNAME/live-curator.git)"
echo "4. Push your branch and initial release tag:"
echo "   git push -u origin ${CURRENT_BRANCH} --tags"
echo "========================================================================"
