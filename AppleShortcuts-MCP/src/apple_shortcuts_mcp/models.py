from typing import Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(default=None, description="Suggested next step")


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ToolError


class ShortcutPermissionStatus(BaseModel):
    shortcuts_cli_available: bool
    shortcuts_command: str
    command_timeout_seconds: int


class HealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    safety_mode: str
    transport: str
    capabilities: list[str]
    permissions: ShortcutPermissionStatus
    transport_support: list[str]


class ShortcutInfo(BaseModel):
    name: str
    identifier: str | None = None
    folder_name: str | None = None


class ShortcutFolderInfo(BaseModel):
    folder_name: str
    shortcut_count: int = 0


class ShortcutArtifact(BaseModel):
    path: str
    exists: bool = False
    kind: str = "file"
    size_bytes: int | None = None


class ShortcutListResponse(BaseModel):
    ok: Literal[True] = True
    shortcuts: list[ShortcutInfo]
    count: int


class ShortcutFolderListResponse(BaseModel):
    ok: Literal[True] = True
    folders: list[ShortcutFolderInfo]
    count: int


class ViewShortcutResponse(BaseModel):
    ok: Literal[True] = True
    shortcut: ShortcutInfo
    opened: bool = True


class ShortcutRunResponse(BaseModel):
    ok: Literal[True] = True
    shortcut_name: str
    shortcut_identifier: str | None = None
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    artifacts: list[ShortcutArtifact] = Field(default_factory=list)
