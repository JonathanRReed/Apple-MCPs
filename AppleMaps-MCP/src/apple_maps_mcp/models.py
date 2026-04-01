from __future__ import annotations

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(default=None, description="Suggested next step")


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ToolError


class HealthResponse(BaseModel):
    ok: bool = True
    server_name: str
    version: str
    helper_available: bool
    helper_compiled: bool
    transport: str
    capabilities: list[str]
    supports: list[str]


class PlaceRecord(BaseModel):
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    url: str | None = None


class PlaceSearchResponse(BaseModel):
    ok: bool = True
    places: list[PlaceRecord]
    count: int


class DirectionsResponse(BaseModel):
    ok: bool = True
    origin: PlaceRecord
    destination: PlaceRecord
    transport: str
    distance_meters: float
    expected_travel_time_seconds: float
    advisory_notices: list[str]
    maps_url: str


class MapsLinkResponse(BaseModel):
    ok: bool = True
    url: str


class OpenMapsResponse(BaseModel):
    ok: bool = True
    opened: bool
    url: str
