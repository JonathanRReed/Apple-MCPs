from typing import Any, Literal

from pydantic import BaseModel


class AppleHealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    transport: str
    domains: dict[str, dict[str, Any]]


class AppleOverviewResponse(BaseModel):
    ok: Literal[True] = True
    overview: dict[str, Any]


class PermissionGuideResponse(BaseModel):
    ok: Literal[True] = True
    domain: str
    can_prompt_in_app: bool
    requires_manual_system_settings: bool
    steps: list[str]
    notes: list[str]


class SuggestionListResponse(BaseModel):
    ok: Literal[True] = True
    domain: str
    suggestions: list[str]
    count: int
