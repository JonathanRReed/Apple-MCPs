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
    scripts_dir: Path


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parents[2]
    raw_safety_mode = os.environ.get("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_readonly").strip() or "safe_readonly"
    if raw_safety_mode not in VALID_SAFETY_MODES:
        raw_safety_mode = "safe_readonly"

    return Settings(
        server_name="Apple Contacts",
        version="0.1.0",
        safety_mode=cast(SafetyMode, raw_safety_mode),
        log_level=os.environ.get("APPLE_CONTACTS_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        scripts_dir=root_dir / "applescripts",
    )
