from __future__ import annotations

import json
import subprocess

from apple_mcp_common.discovery import install_search_first_discovery
from mcp.server.fastmcp import FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_maps_mcp.config import load_settings
from apple_maps_mcp.maps_bridge import AppleMapsBridge, MapsBridgeError, build_bridge
from apple_maps_mcp.models import DirectionsResponse, ErrorResponse, HealthResponse, MapsLinkResponse, OpenMapsResponse, PlaceRecord, PlaceSearchResponse, ToolError

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Maps and travel context on macOS. "
    "Search here when the user wants to find a place, estimate travel time, build an Apple Maps link, or open directions in Apple Maps."
)

mcp = FastMCP("Apple Maps MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge() -> AppleMapsBridge:
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


@mcp.resource(
    "maps://status",
    name="maps_status",
    title="Maps Status",
    description="Apple Maps helper availability and supported transport modes.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.75),
)
def maps_status_resource() -> str:
    helper_available, helper_compiled = _bridge().helper_available()
    return _resource_json(
        {
            "helper_available": helper_available,
            "helper_compiled": helper_compiled,
            "supported_transports": ["driving", "walking", "transit"],
        }
    )


@mcp.prompt(name="maps_plan_route", title="Plan Route")
def maps_plan_route_prompt() -> str:
    return (
        "Use Apple Maps to find the right destination, estimate travel time, and choose the right transport mode "
        "before scheduling a meeting or sending directions."
    )


@mcp.tool(
    title="Maps Health",
    description="Report the active Apple Maps MCP configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def maps_health() -> HealthResponse:
    settings = load_settings()
    helper_available, helper_compiled = _bridge().helper_available()
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        helper_available=helper_available,
        helper_compiled=helper_compiled,
        transport=settings.transport,
        capabilities=[
            "search_places",
            "get_directions",
            "build_maps_link",
            "open_directions_in_maps",
            "resources",
            "prompts",
        ],
        supports=["stdio", "streamable-http"],
    )


@mcp.tool(
    title="Maps Permission Guide",
    description="Explain Apple Maps MCP local helper requirements on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def maps_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "maps",
        "can_prompt_in_app": False,
        "requires_manual_system_settings": False,
        "steps": [
            "Apple Maps MCP uses a local Swift helper for search and routing.",
            "If helper compilation fails, install Xcode command line tools and retry.",
            "Opening a route uses the standard macOS open command with an Apple Maps URL.",
        ],
    }


@mcp.tool(
    title="Search Places",
    description="Search Apple Maps for matching places.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def maps_search_places(query: str, limit: int = 5) -> PlaceSearchResponse | ErrorResponse:
    try:
        payload = _bridge().search_places(query=query, limit=limit)
        places = [PlaceRecord(**item) for item in payload.get("places", [])]
        return PlaceSearchResponse(places=places, count=len(places))
    except MapsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Directions",
    description="Get Apple Maps route details between an origin and destination.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def maps_get_directions(origin: str, destination: str, transport: str = "driving") -> DirectionsResponse | ErrorResponse:
    try:
        payload = _bridge().directions(origin=origin, destination=destination, transport=transport)
        return DirectionsResponse(
            origin=PlaceRecord(**payload["origin"]),
            destination=PlaceRecord(**payload["destination"]),
            transport=str(payload["transport"]),
            distance_meters=float(payload["distance_meters"]),
            expected_travel_time_seconds=float(payload["expected_travel_time_seconds"]),
            advisory_notices=[str(item) for item in payload.get("advisory_notices", [])],
            maps_url=str(payload["maps_url"]),
        )
    except MapsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Build Maps Link",
    description="Build an Apple Maps URL for a destination or route.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def maps_build_maps_link(destination: str, origin: str | None = None, transport: str = "driving") -> MapsLinkResponse:
    return MapsLinkResponse(url=_bridge().maps_url(destination=destination, origin=origin, transport=transport))


@mcp.tool(
    title="Open Directions In Maps",
    description="Open directions in the Apple Maps app.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def maps_open_directions_in_maps(destination: str, origin: str | None = None, transport: str = "driving") -> OpenMapsResponse | ErrorResponse:
    try:
        url = _bridge().maps_url(destination=destination, origin=origin, transport=transport)
        subprocess.run(["open", url], capture_output=True, check=True, text=True)
        return OpenMapsResponse(opened=True, url=url)
    except (MapsBridgeError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, MapsBridgeError):
            return _error_response(exc.error_code, exc.message, exc.suggestion)
        return _error_response("OPEN_FAILED", "Failed to open Apple Maps.", "Retry the request.")


def _serialize_prompt_messages(messages: list[object]) -> list[dict[str, object]]:
    return [
        {
            "role": getattr(message, "role", "user"),
            "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
        }
        for message in messages
    ]


@mcp.tool(
    title="Maps List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def maps_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="Maps Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def maps_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _maps_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _maps_unsubscribe_resource(uri) -> None:
    del uri


TOOL_DISCOVERY = install_search_first_discovery(
    mcp,
    server_name="Apple Maps MCP",
    domain="maps",
)


def main() -> None:
    settings = load_settings()
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.settings.host = settings.host
    mcp.settings.port = settings.port
    mcp.settings.log_level = settings.log_level
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    mcp.run(transport="streamable-http")
