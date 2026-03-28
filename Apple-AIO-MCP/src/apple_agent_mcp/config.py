from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    server_name: str
    version: str
    transport: str
    log_level: str
    host: str
    port: int


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings(
        server_name="Apple-Tools-MCP",
        version="0.1.0",
        transport=os.environ.get("APPLE_AGENT_MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
        log_level=os.environ.get("APPLE_AGENT_MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        host=os.environ.get("APPLE_AGENT_MCP_HOST", "127.0.0.1"),
        port=_parse_int(os.environ.get("APPLE_AGENT_MCP_PORT"), 8000),
    )
