from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    server_name: str
    version: str
    safety_mode: str
    allowed_roots: tuple[Path, ...]
    transport: str
    host: str
    port: int
    log_level: str


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


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
    if not value:
        return _default_roots()
    roots = []
    for raw in value.split(","):
        path = Path(raw.strip()).expanduser()
        if raw.strip():
            roots.append(path)
    return tuple(roots) or _default_roots()


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings(
        server_name="Apple Files MCP",
        version="0.1.0",
        safety_mode=os.environ.get("APPLE_FILES_MCP_SAFETY_MODE", "safe_manage").strip().lower() or "safe_manage",
        allowed_roots=_parse_roots(os.environ.get("APPLE_FILES_MCP_ALLOWED_ROOTS")),
        transport=os.environ.get("APPLE_FILES_MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
        host=os.environ.get("APPLE_FILES_MCP_HOST", "127.0.0.1"),
        port=_parse_int(os.environ.get("APPLE_FILES_MCP_PORT"), 8000),
        log_level=os.environ.get("APPLE_FILES_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
