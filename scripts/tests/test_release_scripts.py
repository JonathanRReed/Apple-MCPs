from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import bump_version  # noqa: E402
import check_release  # noqa: E402


def make_repo(root: Path, *, drift: bool = False) -> None:
    for index, directory in enumerate(bump_version.PACKAGE_DIRS):
        package = root / directory
        package.mkdir()
        dist_name = "apple-mcp-common" if directory == "AppleMCPCommon" else f"package-{index}"
        (package / "pyproject.toml").write_text(f'[project]\nname = "{dist_name}"\nversion = "1.2.3"\n')
        if directory == "AppleMCPCommon":
            continue
        source = package / "src" / f"module_{index}"
        source.mkdir(parents=True)
        default = "1.2.2" if drift and directory == "AppleMail-MCP" else "1.2.3"
        (source / "config.py").write_text(f'class Settings:\n    version: str = "{default}"\n\ndef load():\n    return Settings(version="1.2.3")\n')
        bundle_name = f"bundle-{index}"
        (package / "manifest.json").write_text(json.dumps({"name": bundle_name, "version": "1.2.3", "description": "test"}, indent=2) + "\n")
        server = {
            "version": "1.2.3",
            "packages": [
                {"registryType": "pypi", "version": "1.2.3"},
                {
                    "registryType": "mcpb",
                    "identifier": f"https://example.test/v1.2.2/{bundle_name}-1.2.2.mcpb",
                    "version": "1.2.2",
                    "fileSha256": "a" * 64,
                },
            ],
        }
        (package / "server.json").write_text(json.dumps(server, indent=2) + "\n")


class BumpVersionTests(unittest.TestCase):
    def test_plans_all_edits_before_any_write_and_preserves_mcpb_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_repo(root)
            current, edits = bump_version.plan_edits("1.2.4", root)
            self.assertEqual(current, "1.2.3")
            self.assertEqual(len(edits), 45)
            mail_server = next(edit for edit in edits if edit.path == root / "AppleMail-MCP" / "server.json")
            self.assertIn('"version": "1.2.4"', mail_server.after)
            self.assertIn("bundle-5-1.2.2.mcpb", mail_server.after)
            self.assertIn('"version": "1.2.2"', mail_server.after)
            self.assertEqual((root / "AppleMCPCommon" / "pyproject.toml").read_text(), edits[0].before)

    def test_rejects_typed_config_default_drift_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_repo(root, drift=True)
            before = (root / "AppleMCPCommon" / "pyproject.toml").read_text()
            with self.assertRaisesRegex(bump_version.VersionError, "config versions"):
                bump_version.plan_edits("1.2.4", root)
            self.assertEqual((root / "AppleMCPCommon" / "pyproject.toml").read_text(), before)


class ReleaseCheckTests(unittest.TestCase):
    def test_checks_tag_counts_artifacts_and_generates_exact_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_repo(root)
            self.assertEqual(check_release.validate_source("v1.2.3", root), "1.2.3")
            dist = root / "dist"
            bundles = dist / "mcpb"
            output = root / "metadata"
            bundles.mkdir(parents=True)
            for directory in bump_version.PACKAGE_DIRS:
                name, _ = check_release._project(root / directory / "pyproject.toml")
                stem = name.replace("-", "_")
                (dist / f"{stem}-1.2.3-py3-none-any.whl").write_bytes(b"wheel")
                (dist / f"{stem}-1.2.3.tar.gz").write_bytes(b"sdist")
            for directory in bump_version.SERVER_DIRS:
                manifest = json.loads((root / directory / "manifest.json").read_text())
                (bundles / f"{manifest['name']}-1.2.3.mcpb").write_bytes(directory.encode())
            check_release.validate_artifacts("1.2.3", dist, bundles, output, root)
            metadata = json.loads((output / "AppleMail-MCP.server.json").read_text())
            entry = next(item for item in metadata["packages"] if item["registryType"] == "mcpb")
            bundle = bundles / "bundle-5-1.2.3.mcpb"
            self.assertEqual(entry["fileSha256"], hashlib.sha256(bundle.read_bytes()).hexdigest())
            self.assertTrue(entry["identifier"].endswith("/v1.2.3/bundle-5-1.2.3.mcpb"))

    def test_rejects_wrong_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_repo(root)
            with self.assertRaisesRegex(bump_version.VersionError, "does not match"):
                check_release.validate_source("v1.2.4", root)


if __name__ == "__main__":
    unittest.main()
