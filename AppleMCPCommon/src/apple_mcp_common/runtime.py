from __future__ import annotations

import ipaddress
from typing import Any

from mcp_types.version import MODERN_PROTOCOL_VERSIONS


def require_loopback_host(host: str) -> str:
    """Return a normalized loopback HTTP host or reject network exposure."""
    normalized = host.strip()
    if normalized.lower() == "localhost":
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError(f"Streamable HTTP host must be a loopback address, got {host!r}") from exc
    if not address.is_loopback:
        raise ValueError(f"Streamable HTTP host must be a loopback address, got {host!r}")
    return normalized


def _uses_modern_subscriptions(ctx: Any) -> bool:
    return ctx.protocol_version in MODERN_PROTOCOL_VERSIONS


async def notify_resource_updated(ctx: Any, uri: str) -> None:
    """Notify the resource update over the negotiated protocol's API."""
    if _uses_modern_subscriptions(ctx):
        await ctx.notify_resource_updated(uri)
    else:
        await ctx.request_context.session.send_resource_updated(uri)


async def notify_resources_changed(ctx: Any) -> None:
    """Notify the resource-list change over the negotiated protocol's API."""
    if _uses_modern_subscriptions(ctx):
        await ctx.notify_resources_changed()
    else:
        await ctx.request_context.session.send_resource_list_changed()
