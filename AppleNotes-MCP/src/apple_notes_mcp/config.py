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
    allowed_accounts: tuple[str, ...]
    allowed_folders: tuple[str, ...]
    log_level: str
    scripts_dir: Path


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parents[2]
    raw_safety_mode = os.environ.get("APPLE_NOTES_MCP_SAFETY_MODE", "full_access").strip() or "full_access"
    if raw_safety_mode not in VALID_SAFETY_MODES:
        raw_safety_mode = "full_access"

    return Settings(
        server_name="Apple Notes MCP",
        version="0.1.0",
        safety_mode=cast(SafetyMode, raw_safety_mode),
        allowed_accounts=_parse_csv(os.environ.get("APPLE_NOTES_MCP_ALLOWED_ACCOUNTS")),
        allowed_folders=_parse_csv(os.environ.get("APPLE_NOTES_MCP_ALLOWED_FOLDERS")),
        log_level=os.environ.get("APPLE_NOTES_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        scripts_dir=root_dir / "applescripts",
    )
