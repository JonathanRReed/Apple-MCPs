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
    allowed_roots: list[str]
    transport: str
    capabilities: list[str]
    supports: list[str]


class FileEntry(BaseModel):
    path: str
    name: str
    parent: str
    is_directory: bool
    size_bytes: int | None = None
    modified_at: str | None = None
    extension: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_icloud: bool = False
    location_kind: str = "local"


class FileListResponse(BaseModel):
    ok: bool = True
    base_path: str
    entries: list[FileEntry]
    count: int


class FileResponse(BaseModel):
    ok: bool = True
    entry: FileEntry


class FileTextResponse(BaseModel):
    ok: bool = True
    path: str
    text: str
    encoding: str = "utf-8"
    truncated: bool = False


class FileMutationResponse(BaseModel):
    ok: bool = True
    path: str
    action: str
    destination: str | None = None


class FileTagsResponse(BaseModel):
    ok: bool = True
    path: str
    tags: list[str]
    count: int
    is_icloud: bool = False


class FileActionResponse(BaseModel):
    ok: bool = True
    path: str
    action: str
    opened: bool = True
    revealed: bool = False
    is_icloud: bool = False


class ICloudStatusResponse(BaseModel):
    ok: bool = True
    available: bool
    root_path: str | None = None
    allowed_root_present: bool = False
    allowed_roots: list[dict[str, object]] = Field(default_factory=list)


class RecentLocationsResponse(BaseModel):
    ok: bool = True
    locations: list[FileEntry]
    count: int


class RootsResponse(BaseModel):
    ok: bool = True
    roots: list[str]
    count: int
