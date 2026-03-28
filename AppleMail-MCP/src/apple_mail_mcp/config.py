from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from apple_mail_mcp.models import SafetyProfile


SUPPORTED_TRANSPORTS = {"stdio", "streamable-http"}


@dataclass(slots=True)
class Settings:
    server_name: str = "Apple Mail MCP"
    version: str = "0.1.0"
    safety_profile: SafetyProfile = SafetyProfile.SAFE_MANAGE
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    allowed_attachment_root: Path | None = None
    default_search_limit: int = 10
    visible_drafts: bool = True


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_transport(value: str | None) -> str:
    if value is None:
        return "stdio"
    normalized = value.strip().lower()
    if normalized in SUPPORTED_TRANSPORTS:
        return normalized
    return "stdio"


def load_settings() -> Settings:
    raw_profile = os.getenv("APPLE_MAIL_MCP_SAFETY_PROFILE", SafetyProfile.SAFE_MANAGE.value)
    try:
        safety_profile = SafetyProfile(raw_profile)
    except ValueError:
        safety_profile = SafetyProfile.SAFE_MANAGE

    raw_port = os.getenv("APPLE_MAIL_MCP_PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError:
        port = 8000

    raw_limit = os.getenv("APPLE_MAIL_MCP_DEFAULT_SEARCH_LIMIT", "10")
    try:
        default_search_limit = max(1, min(int(raw_limit), 100))
    except ValueError:
        default_search_limit = 10

    attachment_root = os.getenv("APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT")
    allowed_attachment_root = Path(attachment_root).expanduser() if attachment_root else None

    return Settings(
        server_name="Apple Mail MCP",
        version="0.1.0",
        safety_profile=safety_profile,
        transport=_parse_transport(os.getenv("APPLE_MAIL_MCP_TRANSPORT")),
        host=os.getenv("APPLE_MAIL_MCP_HOST", "127.0.0.1"),
        port=port,
        log_level=os.getenv("APPLE_MAIL_MCP_LOG_LEVEL", "INFO").upper(),
        allowed_attachment_root=allowed_attachment_root,
        default_search_limit=default_search_limit,
        visible_drafts=_parse_bool(os.getenv("APPLE_MAIL_MCP_VISIBLE_DRAFTS"), True),
    )
