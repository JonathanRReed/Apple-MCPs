"""Claude Desktop bundle manifests: settings stay configurable and defaults stay put."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from apple_mcp_common.safety import SAFETY_MODES, SAFETY_SETTING_TITLES

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = sorted(ROOT.glob("*/manifest.json"))
PLACEHOLDER = re.compile(r"^\$\{user_config\.([a-z0-9_]+)\}$")

# Env vars a manifest may hard-code instead of exposing as a setting. Add an
# entry only for values users must never change.
INTENTIONAL_CONSTANTS: dict[str, dict[str, str]] = {}

# What each bundle effectively ran with before settings were configurable
# (v1.1.3). An unconfigured upgrade must keep exactly these values.
PREVIOUS_BUNDLE_ENV: dict[str, dict[str, str]] = {
    "AppleMail-MCP": {"APPLE_MAIL_MCP_SAFETY_PROFILE": "full_access", "APPLE_MAIL_MCP_VISIBLE_DRAFTS": "true"},
    "Apple-Calendar-MCP": {"APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage"},
    "AppleContacts-MCP": {"APPLE_CONTACTS_MCP_SAFETY_MODE": "safe_manage"},
    "AppleFiles-MCP": {
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "~/Desktop,~/Documents,~/Downloads,~/Library/Mobile Documents/com~apple~CloudDocs",
    },
    "AppleMessages-MCP": {"APPLE_MESSAGES_MCP_SAFETY_MODE": "full_access"},
    "AppleNotes-MCP": {"APPLE_NOTES_MCP_SAFETY_MODE": "full_access"},
    "AppleReminders-MCP": {"APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage"},
    "AppleShortcuts-MCP": {"APPLE_SHORTCUTS_MCP_SAFETY_MODE": "full_access"},
    "AppleSystem-MCP": {"APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_manage"},
    "AppleMaps-MCP": {},
    "Apple-Tools-MCP": {
        "APPLE_MAIL_MCP_SAFETY_PROFILE": "full_access",
        "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "~/Desktop,~/Documents,~/Downloads,~/Library/Mobile Documents/com~apple~CloudDocs",
        "APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_CONTACTS_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_NOTES_MCP_SAFETY_MODE": "full_access",
        "APPLE_MESSAGES_MCP_SAFETY_MODE": "full_access",
        "APPLE_SHORTCUTS_MCP_SAFETY_MODE": "full_access",
        "APPLE_MAIL_MCP_VISIBLE_DRAFTS": "true",  # was unset; the code default is true
    },
}

# Settings whose blank value means "no restriction"; blank must equal unset.
BLANK_MEANS_UNSET = {
    "APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT",
    "APPLE_CALENDAR_MCP_ALLOWED_CALENDARS",
    "APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS",
    "APPLE_REMINDERS_MCP_ALLOWED_LISTS",
    "APPLE_NOTES_MCP_ALLOWED_ACCOUNTS",
    "APPLE_NOTES_MCP_ALLOWED_FOLDERS",
}

# Titles quoted by error suggestions, so a user can find the right field.
SUGGESTION_TITLES = {
    "Apple-Calendar-MCP/src/apple_calendar_mcp/permissions.py": ["Allowed calendars", "Calendars the assistant may change"],
    "AppleReminders-MCP/src/apple_reminders_mcp/permissions.py": ["Allowed reminder lists"],
    "AppleNotes-MCP/src/apple_notes_mcp/permissions.py": ["Allowed Notes accounts", "Allowed Notes folders"],
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _env(manifest: dict) -> dict[str, str]:
    return manifest["server"]["mcp_config"].get("env", {})


def _substituted(manifest: dict) -> dict[str, str]:
    """Env as the MCPB reference client builds it when the user changed nothing."""
    defaults = {}
    for key, spec in manifest.get("user_config", {}).items():
        if "default" in spec:
            value = spec["default"]
            defaults[key] = ("true" if value else "false") if isinstance(value, bool) else str(value)
    resolved = {}
    for name, value in _env(manifest).items():
        match = PLACEHOLDER.match(value)
        if match and match.group(1) in defaults:
            resolved[name] = defaults[match.group(1)]
        elif not match:
            resolved[name] = value
    return resolved


class BundleManifestTests(unittest.TestCase):
    def test_every_bundle_is_covered(self) -> None:
        self.assertEqual({path.parent.name for path in MANIFESTS}, set(PREVIOUS_BUNDLE_ENV))
        for path in MANIFESTS:
            self.assertEqual(_load(path)["manifest_version"], "0.4", path)

    def test_every_env_var_is_a_setting_or_an_intentional_constant(self) -> None:
        for path in MANIFESTS:
            manifest = _load(path)
            user_config = manifest.get("user_config", {})
            constants = INTENTIONAL_CONSTANTS.get(path.parent.name, {})
            used = set()
            for name, value in _env(manifest).items():
                match = PLACEHOLDER.match(value)
                if match:
                    self.assertIn(match.group(1), user_config, f"{path}: {name} uses an undeclared setting")
                    used.add(match.group(1))
                else:
                    self.assertEqual(constants.get(name), value, f"{path}: {name} is hard-coded; expose it in user_config")
            self.assertEqual(used, set(user_config), f"{path}: declared settings that no env var uses")

    def test_unconfigured_upgrade_keeps_previous_bundle_behavior(self) -> None:
        for path in MANIFESTS:
            manifest = _load(path)
            resolved = _substituted(manifest)
            expected = PREVIOUS_BUNDLE_ENV[path.parent.name]
            for name, value in expected.items():
                self.assertEqual(resolved.get(name), value, f"{path}: default for {name} changed")
            for name in set(_env(manifest)) - set(expected):
                self.assertIn(name, BLANK_MEANS_UNSET, f"{path}: new setting {name} must default to the unset behavior")
                self.assertIn(resolved.get(name, ""), {""}, f"{path}: {name} must default to blank")

    def test_settings_are_optional_and_safety_modes_are_described(self) -> None:
        for path in MANIFESTS:
            manifest = _load(path)
            for name, value in _env(manifest).items():
                key = PLACEHOLDER.match(value).group(1)
                spec = manifest["user_config"][key]
                self.assertFalse(spec.get("required", False), f"{path}: {key} must be optional")
                self.assertIn(name, spec["description"], f"{path}: {key} description must name {name}")
                if "default" not in spec:
                    # Left unsubstituted by the client; server.py must drop it.
                    self.assertTrue(name.startswith("APPLE_"), f"{path}: {key} needs a default")
                    self.assertIn("drop_unexpanded_user_config()", (path.parent / "server.py").read_text())
                if name in SAFETY_SETTING_TITLES:
                    self.assertEqual(spec["type"], "string")
                    self.assertEqual(spec["title"], SAFETY_SETTING_TITLES[name], f"{path}: title must match error suggestions")
                    self.assertIn(spec["default"], SAFETY_MODES)
                    for mode in SAFETY_MODES:
                        self.assertIn(mode, spec["description"])

    def test_titles_quoted_in_suggestions_exist_in_manifests(self) -> None:
        titles = {spec["title"] for path in MANIFESTS for spec in _load(path).get("user_config", {}).values()}
        for source, quoted in SUGGESTION_TITLES.items():
            text = (ROOT / source).read_text()
            for title in quoted:
                self.assertIn(title, text, source)
                self.assertIn(title, titles, f"{title!r} is quoted by {source} but no manifest uses it")


if __name__ == "__main__":
    unittest.main()
