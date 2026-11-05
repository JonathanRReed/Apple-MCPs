import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
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
    allowed_roots: tuple[Path, ...]


def _default_roots() -> tuple[Path, ...]:
    home = Path.home()
    candidates = (
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
    )
    existing = [path for path in candidates if path.exists()]
    return tuple(existing or [home / "Downloads"])


def _parse_roots(value: str | None) -> tuple[Path, ...]:
    # Attachments are sent only from inside these folders. With no Messages
    # setting it follows the Files server's allowed roots, then the same
    # defaults, so the unified server keeps one set of allowed folders.
    roots = tuple(Path(raw.strip()).expanduser() for raw in (value or "").split(",") if raw.strip())
    return roots or _default_roots()


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    raw_safety_mode = os.environ.get("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access").strip()
    if raw_safety_mode not in VALID_SAFETY_MODES:
        raw_safety_mode = "safe_readonly"

    return Settings(
        server_name="Apple Messages MCP",
        version="1.1.5",
        safety_mode=cast(SafetyMode, raw_safety_mode),
        db_path=Path(os.environ.get("APPLE_MESSAGES_MCP_DB_PATH", str(Path.home() / "Library" / "Messages" / "chat.db"))).expanduser(),
        log_level=os.environ.get("APPLE_MESSAGES_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        transport=os.environ.get("APPLE_MESSAGES_MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
        allowed_roots=_parse_roots(
            os.environ.get("APPLE_MESSAGES_MCP_ALLOWED_ROOTS") or os.environ.get("APPLE_FILES_MCP_ALLOWED_ROOTS")
        ),
    )
