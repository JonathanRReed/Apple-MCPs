from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
from typing import Literal, cast

SafetyMode = Literal["safe_readonly", "safe_manage", "full_access"]
VALID_SAFETY_MODES = frozenset({"safe_readonly", "safe_manage", "full_access"})


@dataclass(frozen=True)
class Settings:
    server_name: str
    version: str
    safety_mode: SafetyMode
    allowed_calendars: tuple[str, ...]
    log_level: str
    helper_source: Path
    helper_binary: Path


def _parse_allowed_calendars(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parents[2]
    repo_dir = root_dir.parent
    raw_safety_mode = os.environ.get("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage").strip() or "safe_manage"
    if raw_safety_mode not in VALID_SAFETY_MODES:
        raw_safety_mode = "safe_manage"

    return Settings(
        server_name="Apple Calendar MCP",
        version="0.1.0",
        safety_mode=cast(SafetyMode, raw_safety_mode),
        allowed_calendars=_parse_allowed_calendars(os.environ.get("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS")),
        log_level=os.environ.get("APPLE_CALENDAR_MCP_LOG_LEVEL", "INFO").strip() or "INFO",
        helper_source=repo_dir / "SharedAppleBridge" / "apple_pim_bridge.swift",
        helper_binary=repo_dir / ".build" / "apple-pim-bridge",
    )
