"""Shared wording for safety-mode blocks, so every server tells users how to fix them.

A blocked tool or a mistyped safety value is often reported to the user by a
small agent that cannot read the docs. These helpers make the error text itself
name the exact environment variable, the value to set, and where to set it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

SAFETY_MODES: tuple[str, ...] = ("safe_readonly", "safe_manage", "full_access")

# Environment variable -> title of the matching setting in the Claude Desktop
# extension (MCPB ``user_config``). Bundle manifests must use these titles.
SAFETY_SETTING_TITLES: dict[str, str] = {
    "APPLE_MAIL_MCP_SAFETY_PROFILE": "Mail safety mode",
    "APPLE_CALENDAR_MCP_SAFETY_MODE": "Calendar safety mode",
    "APPLE_REMINDERS_MCP_SAFETY_MODE": "Reminders safety mode",
    "APPLE_FILES_MCP_SAFETY_MODE": "Files safety mode",
    "APPLE_SYSTEM_MCP_SAFETY_MODE": "System safety mode",
    "APPLE_CONTACTS_MCP_SAFETY_MODE": "Contacts safety mode",
    "APPLE_NOTES_MCP_SAFETY_MODE": "Notes safety mode",
    "APPLE_MESSAGES_MCP_SAFETY_MODE": "Messages safety mode",
    "APPLE_SHORTCUTS_MCP_SAFETY_MODE": "Shortcuts safety mode",
}

def how_to_set(env_var: str, value: str, title: str | None = None) -> str:
    """Describe where to set ``env_var=value`` for env-block clients and Claude Desktop.

    ``title`` names the Claude Desktop extension setting for variables that are
    not safety modes; safety modes default to ``SAFETY_SETTING_TITLES``.
    """
    title = title or SAFETY_SETTING_TITLES.get(env_var)
    desktop = (
        f'in Claude Desktop, open Settings > Extensions, configure this extension and set "{title}" to {value}'
        if title
        else "in Claude Desktop, change it in this extension's settings"
    )
    return f'set {env_var}={value} in the "env" block of this server in your MCP client config ({desktop}), then restart the MCP client'


def _invalid_value_note(env_var: str, effective_mode: str, environ: Mapping[str, str] | None) -> str | None:
    raw = (os.environ if environ is None else environ).get(env_var)
    if raw is None:
        return None
    value = raw.strip()
    if value in SAFETY_MODES or value.lower() == effective_mode:
        return None
    problem = f"{env_var} is set but blank" if not value else f"{env_var} is set to {raw!r}, which is not a valid safety mode"
    return f"{problem} (valid values, lowercase and exact: {', '.join(SAFETY_MODES)}), so this server fell back to {effective_mode}."


def safety_mode_warning(env_var: str, effective_mode: str, environ: Mapping[str, str] | None = None) -> str | None:
    """Explain when a set-but-unrecognized safety value forced ``effective_mode``.

    Returns ``None`` when the variable is unset (the documented default applies),
    holds a valid mode, or was accepted case-insensitively as ``effective_mode``.
    """
    note = _invalid_value_note(env_var, effective_mode, environ)
    if note is None:
        return None
    return f"{note} To fix it, {how_to_set(env_var, '<valid value>')}."


def safety_block_suggestion(env_var: str, required_mode: str, effective_mode: str | None = None) -> str:
    """Tell the user exactly how to allow a tool blocked by the current safety mode.

    ``required_mode`` is the least-privileged mode that allows the tool. When
    ``effective_mode`` came from an invalid value, the typo is explained first.
    """
    note = _invalid_value_note(env_var, effective_mode, None) if effective_mode is not None else None
    allowed = "safe_manage or full_access" if required_mode == "safe_manage" else required_mode
    parts = [note] if note else []
    parts.append(
        f"This tool needs {env_var} to be {allowed}. Ask the user before raising it. "
        f"To allow it, {how_to_set(env_var, required_mode)}."
    )
    return " ".join(parts)
