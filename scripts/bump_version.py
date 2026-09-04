#!/usr/bin/env python3
"""Bump package source versions without rewriting MCPB artifact records."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIRS = ("AppleMCPCommon", "Apple-Tools-MCP", "Apple-Calendar-MCP", "AppleContacts-MCP", "AppleFiles-MCP", "AppleMail-MCP", "AppleMaps-MCP", "AppleMessages-MCP", "AppleNotes-MCP", "AppleReminders-MCP", "AppleShortcuts-MCP", "AppleSystem-MCP")
SERVER_DIRS = tuple(name for name in PACKAGE_DIRS if name != "AppleMCPCommon")
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


class VersionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Edit:
    path: Path
    before: str
    after: str
    count: int


def _one(pattern: str, text: str, path: Path, label: str) -> str:
    matches = re.findall(pattern, text, re.MULTILINE)
    if len(matches) != 1:
        raise VersionError(f"{path}: expected one {label}, found {len(matches)}")
    return matches[0]


def read_current_version(root: Path = ROOT) -> str:
    path = root / "AppleMCPCommon" / "pyproject.toml"
    return _one(r'^version = "([0-9]+\.[0-9]+\.[0-9]+)"$', path.read_text(), path, "project version")


def plan_edits(new_version: str, root: Path = ROOT) -> tuple[str, list[Edit]]:
    if SEMVER.fullmatch(new_version) is None:
        raise VersionError(f"'{new_version}' is not a plain X.Y.Z version")
    current = read_current_version(root)
    if current == new_version:
        raise VersionError(f"Packages are already at {current}")
    edits: list[Edit] = []
    for name in PACKAGE_DIRS:
        package = root / name
        if not package.is_dir():
            raise VersionError(f"Expected package directory missing: {package}")
        paths = [package / "pyproject.toml"]
        if name != "AppleMCPCommon":
            configs = sorted(package.glob("src/*/config.py"))
            if len(configs) != 1:
                raise VersionError(f"{package}: expected one config.py, found {len(configs)}")
            paths.extend((configs[0], package / "manifest.json", package / "server.json"))
        for path in paths:
            if not path.is_file():
                raise VersionError(f"Expected file missing: {path}")
            before = path.read_text()
            after = before
            if path.name == "pyproject.toml":
                found = _one(r'^version = "([0-9]+\.[0-9]+\.[0-9]+)"$', before, path, "project version")
                if found != current:
                    raise VersionError(f"{path}: project version is {found}, expected {current}")
                after, count = re.subn(r'^(version = ")' + re.escape(current) + r'("$)', rf"\g<1>{new_version}\2", before, flags=re.MULTILINE)
            elif path.name == "config.py":
                versions = re.findall(r'\bversion(?::\s*str)?\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', before)
                if not versions or any(version != current for version in versions):
                    raise VersionError(f"{path}: config versions {versions!r}, expected only {current}")
                after, count = re.subn(r'(\bversion(?::\s*str)?\s*=\s*")' + re.escape(current) + r'(")', rf"\g<1>{new_version}\2", before)
            elif path.name == "manifest.json":
                found = _one(r'^  "version": "([0-9]+\.[0-9]+\.[0-9]+)",$', before, path, "manifest version")
                if found != current:
                    raise VersionError(f"{path}: manifest version is {found}, expected {current}")
                after, count = re.subn(r'^(  "version": ")' + re.escape(current) + r'(",$)', rf"\g<1>{new_version}\2", before, flags=re.MULTILINE)
            else:
                marker = before.find('"registryType": "mcpb"')
                if marker < 0:
                    raise VersionError(f"{path}: missing MCPB package entry")
                prefix, suffix = before[:marker], before[marker:]
                versions = re.findall(r'"version": "([0-9]+\.[0-9]+\.[0-9]+)"', prefix)
                if versions != [current, current]:
                    raise VersionError(f"{path}: server/PyPI versions are {versions!r}, expected [{current!r}, {current!r}]")
                prefix, count = re.subn(r'("version": ")' + re.escape(current) + r'(")', rf"\g<1>{new_version}\2", prefix)
                if count != 2:
                    raise VersionError(f"{path}: expected two source version fields, found {count}")
                after = prefix + suffix
            edits.append(Edit(path, before, after, count))
    return current, edits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_version", help="new semantic version, e.g. 1.0.4")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = parser.parse_args()
    try:
        current, edits = plan_edits(args.new_version)
    except VersionError as exc:
        parser.error(str(exc))
    for edit in edits:
        print(f"{edit.path.relative_to(ROOT)}: {edit.count} occurrence(s)")
    if not args.dry_run:
        for edit in edits:
            edit.path.write_text(edit.after)
    action = "Would update" if args.dry_run else "Updated"
    print(f"\n{action} {sum(edit.count for edit in edits)} source version fields: {current} -> {args.new_version}")


if __name__ == "__main__":
    main()
