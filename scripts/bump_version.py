#!/usr/bin/env python3
"""Semantic version bumping utility for Live Curator Engine.

Usage:
    python3 scripts/bump_version.py [--patch | --minor | --major | --set 0.0.2] [--git]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "src" / "__version__.py"


def read_current_version() -> str:
    if not VERSION_FILE.exists():
        return "0.0.1"
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError(f"Could not find __version__ in {VERSION_FILE}")
    return match.group(1)


def write_version(new_version: str):
    content = f'"""Live Curator version specification."""\n\n__version__ = "{new_version}"\n'
    VERSION_FILE.write_text(content, encoding="utf-8")


def bump(current: str, part: str) -> str:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", current)
    if not m:
        raise ValueError(f"Version string '{current}' is not valid standard semver (X.Y.Z)")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown part: {part}")


def main():
    parser = argparse.ArgumentParser(description="Bump Live Curator version.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--patch", action="store_true", help="Bump patch version (0.0.X)")
    group.add_argument("--minor", action="store_true", help="Bump minor version (0.X.0)")
    group.add_argument("--major", action="store_true", help="Bump major version (X.0.0)")
    group.add_argument("--set", type=str, help="Set explicit version string (e.g. 0.1.0)")
    parser.add_argument("--git", action="store_true", help="Create git commit and annotated tag")

    args = parser.parse_args()

    current_ver = read_current_version()

    if args.set:
        new_ver = args.set.strip()
    elif args.major:
        new_ver = bump(current_ver, "major")
    elif args.minor:
        new_ver = bump(current_ver, "minor")
    else:
        # Default is patch
        new_ver = bump(current_ver, "patch")

    write_version(new_ver)
    print(f"Bumped version: {current_ver} -> {new_ver} (written to {VERSION_FILE.relative_to(Path.cwd())})")

    if args.git:
        subprocess.run(["git", "add", str(VERSION_FILE)], check=True)
        subprocess.run(["git", "commit", "-m", f"chore(release): bump version to v{new_ver}"], check=True)
        subprocess.run(["git", "tag", "-a", f"v{new_ver}", "-m", f"Release v{new_ver}"], check=True)
        print(f"Created git commit and tag v{new_ver}")


if __name__ == "__main__":
    main()
