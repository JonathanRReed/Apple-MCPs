from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    server_name: str
    version: str
    helper_source: Path
    helper_binary: Path
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


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    repo_dir = Path(__file__).resolve().parents[3]
    build_dir = repo_dir / "AppleMaps-MCP" / "build"
    return Settings(
        server_name="Apple Maps MCP",
        version="0.1.0",
        helper_source=repo_dir / "SharedAppleBridge" / "apple_maps_bridge.swift",
        helper_binary=build_dir / "apple_maps_bridge",
        transport=os.environ.get("APPLE_MAPS_MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
        host=os.environ.get("APPLE_MAPS_MCP_HOST", "127.0.0.1"),
        port=_parse_int(os.environ.get("APPLE_MAPS_MCP_PORT"), 8000),
        log_level=os.environ.get("APPLE_MAPS_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
