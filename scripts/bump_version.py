#!/usr/bin/env python3
"""Bump the suite version across every package in one step.

The version string lives in four places per package (pyproject.toml,
src/*/config.py, manifest.json, server.json), so a release touches ~40 files.
This script rewrites every exact occurrence of the current version, reading
the current version from AppleMCPCommon/pyproject.toml as the canonical
source, and fails loudly if any expected file has drifted.

Usage:
    python3 scripts/bump_version.py 1.0.3 [--dry-run]

Afterwards: add the release heading to CHANGELOG.md, run
`uv sync --all-packages` to refresh the lockfile, run the test suites, commit,
and tag `vX.Y.Z` to trigger the release workflow (see docs/publishing.md).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PACKAGE_DIRS = (
    "AppleMCPCommon",
    "Apple-Tools-MCP",
    "Apple-Calendar-MCP",
    "AppleContacts-MCP",
    "AppleFiles-MCP",
    "AppleMail-MCP",
    "AppleMaps-MCP",
    "AppleMessages-MCP",
    "AppleNotes-MCP",
    "AppleReminders-MCP",
    "AppleShortcuts-MCP",
    "AppleSystem-MCP",
)


def read_current_version() -> str:
    canonical = ROOT / "AppleMCPCommon" / "pyproject.toml"
    match = re.search(r'^version = "([0-9]+\.[0-9]+\.[0-9]+)"$', canonical.read_text(), re.MULTILINE)
    if match is None:
        sys.exit(f"Could not find a version line in {canonical}")
    return match.group(1)


def candidate_files(package_dir: Path) -> list[Path]:
    files = [package_dir / "pyproject.toml"]
    files.extend(sorted(package_dir.glob("src/*/config.py")))
    for name in ("manifest.json", "server.json"):
        path = package_dir / name
        if path.exists():
            files.append(path)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("new_version", help="new semantic version, e.g. 1.0.3")
    parser.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    args = parser.parse_args()

    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.new_version) is None:
        sys.exit(f"'{args.new_version}' is not a plain X.Y.Z version")

    current = read_current_version()
    if current == args.new_version:
        sys.exit(f"Packages are already at {current}")

    # Exact patterns only: dependency ranges, spec dates, and manifest schema
    # versions never match the quoted current version, so nothing else moves.
    patterns = (
        f'version = "{current}"',
        f'version="{current}"',
        f'"version": "{current}"',
    )

    total = 0
    for dir_name in PACKAGE_DIRS:
        package_dir = ROOT / dir_name
        if not package_dir.is_dir():
            sys.exit(f"Expected package directory missing: {package_dir}")
        for path in candidate_files(package_dir):
            if not path.exists():
                sys.exit(f"Expected file missing: {path}")
            text = path.read_text()
            count = sum(text.count(pattern) for pattern in patterns)
            if count == 0:
                sys.exit(f"{path} contains no '{current}' version string; fix the drift before bumping")
            for pattern in patterns:
                text = text.replace(pattern, pattern.replace(current, args.new_version))
            if not args.dry_run:
                path.write_text(text)
            total += count
            print(f"{path.relative_to(ROOT)}: {count} occurrence(s)")

    action = "Would update" if args.dry_run else "Updated"
    print(f"\n{action} {total} version strings: {current} -> {args.new_version}")
    if not args.dry_run:
        print("Next: update CHANGELOG.md, run `uv sync --all-packages`, run tests, commit, then tag")
        print(f"  git tag v{args.new_version} && git push origin v{args.new_version}")


if __name__ == "__main__":
    main()
