from __future__ import annotations

import ipaddress


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
