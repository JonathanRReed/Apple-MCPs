#!/usr/bin/env python3
"""Validate release versions and built artifacts, then write registry metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from bump_version import (
    PACKAGE_DIRS,
    REQUIRED_INTERNAL_DEPENDENCIES,
    ROOT,
    SERVER_DIRS,
    VersionError,
    dependency_spec,
    read_current_version,
)


def _project(path: Path) -> tuple[str, str]:
    text = path.read_text()
    name = re.search(r'^name = "([^"]+)"$', text, re.MULTILINE)
    version = re.search(r'^version = "([0-9]+\.[0-9]+\.[0-9]+)"$', text, re.MULTILINE)
    if not name or not version:
        raise VersionError(f"{path}: missing project name or version")
    return name.group(1), version.group(1)


def validate_source(tag: str | None, root: Path = ROOT) -> str:
    version = read_current_version(root)
    if tag and tag != f"v{version}":
        raise VersionError(f"tag {tag!r} does not match source version v{version}")
    for directory in PACKAGE_DIRS:
        package = root / directory
        pyproject = package / "pyproject.toml"
        _, found = _project(pyproject)
        if found != version:
            raise VersionError(f"{pyproject}: version {found}, expected {version}")
        dependency_versions = {
            dependency: spec
            for dependency, spec in re.findall(
                r'^  "(apple-[a-z-]+)(>=[0-9]+\.[0-9]+\.[0-9]+,<[0-9]+)",$',
                pyproject.read_text(),
                re.MULTILINE,
            )
        }
        required = REQUIRED_INTERNAL_DEPENDENCIES[directory]
        if set(dependency_versions) != required or any(spec != dependency_spec(version) for spec in dependency_versions.values()):
            raise VersionError(
                f"{pyproject}: internal dependencies {dependency_versions!r}, "
                f"expected {sorted(required)!r} at {dependency_spec(version)}"
            )
        if directory == "AppleMCPCommon":
            continue
        manifest = json.loads((package / "manifest.json").read_text())
        server = json.loads((package / "server.json").read_text())
        configs = list(package.glob("src/*/config.py"))
        if len(configs) != 1:
            raise VersionError(f"{package}: expected one config.py, found {len(configs)}")
        config_versions = re.findall(r'\bversion(?::\s*str)?\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', configs[0].read_text())
        pypi = [entry for entry in server.get("packages", []) if entry.get("registryType") == "pypi"]
        if manifest.get("version") != version or server.get("version") != version or len(pypi) != 1 or pypi[0].get("version") != version or not config_versions or any(item != version for item in config_versions):
            raise VersionError(f"{package}: manifest, server, PyPI, or config version does not match {version}")
        mcpb = [entry for entry in server.get("packages", []) if entry.get("registryType") == "mcpb"]
        if len(mcpb) != 1:
            raise VersionError(f"{package / 'server.json'}: expected one MCPB entry")
        asset = Path(urlparse(mcpb[0].get("identifier", "")).path).name
        artifact_version = mcpb[0].get("version")
        if not artifact_version or f"-{artifact_version}.mcpb" not in asset or not re.fullmatch(r"[0-9a-f]{64}", mcpb[0].get("fileSha256", "")):
            raise VersionError(f"{package / 'server.json'}: MCPB URL, version, and hash are inconsistent")
    return version


def validate_artifacts(version: str, dist: Path, bundles: Path, output: Path, root: Path = ROOT) -> None:
    expected_dists: set[str] = set()
    for directory in PACKAGE_DIRS:
        name, _ = _project(root / directory / "pyproject.toml")
        stem = re.sub(r"[-_.]+", "_", name)
        expected_dists.update((f"{stem}-{version}-py3-none-any.whl", f"{stem}-{version}.tar.gz"))
    found_dists = {
        path.name
        for path in dist.iterdir()
        if path.is_file() and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
    }
    if found_dists != expected_dists:
        raise VersionError(f"distribution set mismatch; missing={sorted(expected_dists - found_dists)}, extra={sorted(found_dists - expected_dists)}")
    expected_bundles: dict[str, Path] = {}
    for directory in SERVER_DIRS:
        manifest = json.loads((root / directory / "manifest.json").read_text())
        expected_bundles[directory] = bundles / f"{manifest['name']}-{version}.mcpb"
    found_bundles = {path.name for path in bundles.glob("*.mcpb")}
    expected_names = {path.name for path in expected_bundles.values()}
    if found_bundles != expected_names:
        raise VersionError(f"bundle set mismatch; missing={sorted(expected_names - found_bundles)}, extra={sorted(found_bundles - expected_names)}")
    output.mkdir(parents=True, exist_ok=True)
    for directory, bundle in expected_bundles.items():
        server = json.loads((root / directory / "server.json").read_text())
        entry = next(item for item in server["packages"] if item["registryType"] == "mcpb")
        entry.update(identifier=f"https://github.com/JonathanRReed/Apple-MCPs/releases/download/v{version}/{bundle.name}", version=version, fileSha256=hashlib.sha256(bundle.read_bytes()).hexdigest())
        (output / f"{directory}.server.json").write_text(json.dumps(server, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="release tag, normally GITHUB_REF_NAME")
    parser.add_argument("--artifacts", action="store_true", help="verify built distributions and bundles")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / "dist" / "mcpb")
    parser.add_argument("--metadata-dir", type=Path, default=ROOT / "release-metadata")
    args = parser.parse_args()
    try:
        version = validate_source(args.tag)
        if args.artifacts:
            validate_artifacts(version, args.dist_dir, args.bundle_dir, args.metadata_dir)
    except (VersionError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"Release preflight passed for v{version}: 12 packages and 11 servers")


if __name__ == "__main__":
    main()
