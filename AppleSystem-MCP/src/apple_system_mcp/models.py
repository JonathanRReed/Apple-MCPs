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
    safety_mode: str
    transport: str
    capabilities: list[str]
    supports: list[str]


class BatteryStatus(BaseModel):
    percentage: int | None = None
    power_source: str | None = None
    charging: bool | None = None
    raw: str


class AppRecord(BaseModel):
    name: str


class ClipboardResponse(BaseModel):
    ok: bool = True
    text: str


class NotificationResponse(BaseModel):
    ok: bool = True
    delivered: bool
    title: str


class OpenAppResponse(BaseModel):
    ok: bool = True
    opened: bool
    application: str


class RunningAppsResponse(BaseModel):
    ok: bool = True
    apps: list[AppRecord]
    count: int


class StatusResponse(BaseModel):
    ok: bool = True
    battery: BatteryStatus | None = None
    frontmost_app: str | None = None
    running_apps_count: int | None = None


class SettingsDomainsResponse(BaseModel):
    ok: bool = True
    domains: list[dict[str, str]]
    count: int


class SettingsSectionResponse(BaseModel):
    ok: bool = True
    section: str
    values: dict[str, object]


class SettingsSnapshotResponse(BaseModel):
    ok: bool = True
    appearance: dict[str, object]
    accessibility: dict[str, object]
    dock: dict[str, object]
    finder: dict[str, object]


class PreferenceDomainResponse(BaseModel):
    ok: bool = True
    domain: str
    current_host: bool = False
    values: dict[str, object]


class SettingMutationResponse(BaseModel):
    ok: bool = True
    section: str
    setting: str
    requested_value: bool | str
    observed_value: bool | str | None = None
    restarted_processes: list[str] = Field(default_factory=list)
    used_gui_fallback: bool = False


class GuiMenuItemsResponse(BaseModel):
    ok: bool = True
    application: str
    menu_bar_items: list[str]
    count: int
    used_gui_fallback: bool = True


class GuiActionResponse(BaseModel):
    ok: bool = True
    action: str
    application: str | None = None
    target: str | None = None
    value: bool | str | list[str] | None = None
    used_gui_fallback: bool = True
