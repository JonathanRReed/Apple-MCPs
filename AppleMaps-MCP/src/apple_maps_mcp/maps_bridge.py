from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode, quote_plus

from apple_maps_mcp.config import load_settings


@dataclass(frozen=True)
class MapsBridgeError(Exception):
    error_code: str
    message: str
    suggestion: str | None = None


class AppleMapsBridge:
    def __init__(self, helper_source: Path, helper_binary: Path) -> None:
        self.helper_source = helper_source
        self.helper_binary = helper_binary

    def helper_available(self) -> tuple[bool, bool]:
        return self.helper_source.exists(), self.helper_binary.exists()

    def _ensure_helper(self) -> None:
        self.helper_binary.parent.mkdir(parents=True, exist_ok=True)
        if self.helper_binary.exists() and self.helper_binary.stat().st_mtime >= self.helper_source.stat().st_mtime:
            return
        try:
            subprocess.run(
                ["swiftc", "-parse-as-library", "-O", str(self.helper_source), "-o", str(self.helper_binary)],
                capture_output=True,
                check=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
            raise MapsBridgeError(
                "HELPER_COMPILE_FAILED",
                stderr or "Failed to compile the Apple Maps helper.",
                "Install Xcode command line tools and retry.",
            ) from exc

    def _run_helper(self, command: str, payload: dict[str, object]) -> dict[str, object]:
        self._ensure_helper()
        try:
            result = subprocess.run(
                [str(self.helper_binary), command, json.dumps(payload)],
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip()
            raise MapsBridgeError("HELPER_FAILED", stderr or "Apple Maps helper failed.", "Retry the request.") from exc
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MapsBridgeError("INVALID_RESPONSE", "Apple Maps helper returned invalid JSON.", "Retry the request.") from exc

    def search_places(self, query: str, limit: int = 5) -> dict[str, object]:
        return self._run_helper("search-places", {"query": query, "limit": limit})

    def directions(self, origin: str, destination: str, transport: str = "driving") -> dict[str, object]:
        payload = self._run_helper("directions", {"origin": origin, "destination": destination, "transport": transport})
        payload["maps_url"] = self.maps_url(destination=destination, origin=origin, transport=transport)
        return payload

    def maps_url(self, destination: str, origin: str | None = None, transport: str = "driving") -> str:
        params = {"daddr": destination}
        if origin:
            params["saddr"] = origin
        transport_flag = {"driving": "d", "walking": "w", "transit": "r"}.get(transport, "d")
        params["dirflg"] = transport_flag
        return f"https://maps.apple.com/?{urlencode(params, quote_via=quote_plus)}"


def build_bridge() -> AppleMapsBridge:
    settings = load_settings()
    return AppleMapsBridge(settings.helper_source, settings.helper_binary)
