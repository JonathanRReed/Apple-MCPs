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
    log_level: str
    transport: str
    host: str
    port: int
    shortcuts_command: str
    command_timeout_seconds: int
    scripts_root: Path


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parents[2]
    raw_safety_mode = os.environ.get("APPLE_SHORTCUTS_MCP_SAFETY_MODE", "full_access").strip() or "full_access"
    if raw_safety_mode not in VALID_SAFETY_MODES:
        raw_safety_mode = "full_access"

    return Settings(
        server_name="Apple Shortcuts MCP",
        version="0.1.0",
        safety_mode=cast(SafetyMode, raw_safety_mode),
        log_level=os.environ.get("APPLE_SHORTCUTS_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        transport=os.environ.get("APPLE_SHORTCUTS_MCP_TRANSPORT", "stdio").strip() or "stdio",
        host=os.environ.get("APPLE_SHORTCUTS_MCP_HOST", "127.0.0.1"),
        port=_parse_int(os.environ.get("APPLE_SHORTCUTS_MCP_PORT"), 8000),
        shortcuts_command=os.environ.get("APPLE_SHORTCUTS_MCP_SHORTCUTS_COMMAND", "shortcuts").strip() or "shortcuts",
        command_timeout_seconds=_parse_int(os.environ.get("APPLE_SHORTCUTS_MCP_COMMAND_TIMEOUT_SECONDS"), 300),
        scripts_root=root_dir,
    )
