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
    db_path: Path
    log_level: str
    transport: str


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    raw_safety_mode = os.environ.get("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access").strip() or "full_access"
    if raw_safety_mode not in VALID_SAFETY_MODES:
        raw_safety_mode = "full_access"

    return Settings(
        server_name="Apple Messages MCP",
        version="0.1.0",
        safety_mode=cast(SafetyMode, raw_safety_mode),
        db_path=Path(os.environ.get("APPLE_MESSAGES_MCP_DB_PATH", str(Path.home() / "Library" / "Messages" / "chat.db"))).expanduser(),
        log_level=os.environ.get("APPLE_MESSAGES_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        transport=os.environ.get("APPLE_MESSAGES_MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
    )
