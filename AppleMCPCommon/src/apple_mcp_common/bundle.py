"""Helpers for servers launched from a Claude Desktop (MCPB) bundle."""

from __future__ import annotations

import os
from collections.abc import MutableMapping

_PLACEHOLDER_PREFIX = "${user_config."


def drop_unexpanded_user_config(environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Remove env vars whose value is a literal, unsubstituted ``${user_config.*}``.

    A client that leaves an optional, unset bundle setting unsubstituted would
    otherwise pass the placeholder text through as a real value (for example as
    an allowlist entry that matches nothing). Dropping it restores the server's
    documented default. Returns the removed variable names.
    """
    env = os.environ if environ is None else environ
    removed = [key for key, value in env.items() if key.startswith("APPLE_") and value.strip().startswith(_PLACEHOLDER_PREFIX)]
    for key in removed:
        del env[key]
    return removed
