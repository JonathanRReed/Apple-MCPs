from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path

from apple_files_mcp.config import load_settings
from apple_files_mcp.models import FileEntry


@dataclass(frozen=True)
class FilesBridgeError(Exception):
    error_code: str
    message: str
    suggestion: str | None = None


def _iso_timestamp(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


class FilesBridge:
    def __init__(self, allowed_roots: tuple[Path, ...]) -> None:
        self.allowed_roots = tuple(path.expanduser().resolve(strict=False) for path in allowed_roots)

    def list_allowed_roots(self) -> list[str]:
        return [str(path) for path in self.allowed_roots]

    def _ensure_allowed(self, path: str, *, allow_missing: bool = False) -> Path:
        candidate = Path(path).expanduser()
        resolved = candidate.resolve(strict=False)
        if not allow_missing and not resolved.exists():
            raise FilesBridgeError("PATH_NOT_FOUND", f"Path does not exist: {resolved}", "Choose an existing file or folder.")
        if allow_missing and not resolved.parent.exists():
            raise FilesBridgeError("PARENT_NOT_FOUND", f"Parent folder does not exist: {resolved.parent}", "Choose a destination inside an existing folder.")
        for root in self.allowed_roots:
            if resolved.is_relative_to(root):
                return resolved
        raise FilesBridgeError(
            "PATH_NOT_ALLOWED",
            f"Path is outside the allowed roots: {resolved}",
            "Use files_list_allowed_roots to find an allowed base path.",
        )

    def _entry(self, path: Path) -> FileEntry:
        stat = path.stat()
        return FileEntry(
            path=str(path),
            name=path.name or str(path),
            parent=str(path.parent),
            is_directory=path.is_dir(),
            size_bytes=None if path.is_dir() else stat.st_size,
            modified_at=_iso_timestamp(stat.st_mtime),
            extension=path.suffix.lower() or None,
        )

    def list_directory(self, path: str) -> list[FileEntry]:
        directory = self._ensure_allowed(path)
        if not directory.is_dir():
            raise FilesBridgeError("NOT_A_DIRECTORY", f"Path is not a directory: {directory}", "Choose a folder path.")
        entries = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        return [self._entry(item) for item in entries]

    def search_files(self, query: str, base_path: str | None = None, limit: int = 25) -> list[FileEntry]:
        needle = query.strip().lower()
        if not needle:
            raise FilesBridgeError("INVALID_INPUT", "query must not be empty", "Provide part of a file or folder name.")
        roots = [self._ensure_allowed(base_path)] if base_path else list(self.allowed_roots)
        matches: list[FileEntry] = []
        for root in roots:
            for current_root, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
                for name in [*dirnames, *filenames]:
                    if needle in name.lower():
                        path = Path(current_root) / name
                        matches.append(self._entry(path))
                        if len(matches) >= limit:
                            return matches
        return matches

    def file_info(self, path: str) -> FileEntry:
        return self._entry(self._ensure_allowed(path))

    def read_text_file(self, path: str, max_bytes: int = 100_000) -> tuple[str, bool]:
        file_path = self._ensure_allowed(path)
        if file_path.is_dir():
            raise FilesBridgeError("NOT_A_FILE", f"Path is a directory: {file_path}", "Choose a text file path.")
        raw = file_path.read_bytes()
        truncated = len(raw) > max_bytes
        payload = raw[:max_bytes]
        try:
            return payload.decode("utf-8"), truncated
        except UnicodeDecodeError:
            try:
                return payload.decode("utf-8", errors="replace"), truncated
            except Exception as exc:  # pragma: no cover
                raise FilesBridgeError("READ_FAILED", f"Unable to decode file: {file_path}", "Choose a UTF-8 text file.") from exc

    def recent_files(self, limit: int = 25) -> list[FileEntry]:
        entries: list[FileEntry] = []
        for root in self.allowed_roots:
            for current_root, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
                for name in filenames:
                    if name.startswith("."):
                        continue
                    path = Path(current_root) / name
                    try:
                        entries.append(self._entry(path))
                    except OSError:
                        continue
        entries.sort(key=lambda item: item.modified_at or "", reverse=True)
        return entries[:limit]

    def create_folder(self, path: str) -> str:
        folder = self._ensure_allowed(path, allow_missing=True)
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder)

    def move_path(self, source: str, destination: str) -> tuple[str, str]:
        source_path = self._ensure_allowed(source)
        destination_path = self._ensure_allowed(destination, allow_missing=True)
        source_path.rename(destination_path)
        return str(source_path), str(destination_path)

    def delete_path(self, path: str) -> str:
        target = self._ensure_allowed(path)
        if target.is_dir():
            if any(target.iterdir()):
                raise FilesBridgeError("DIRECTORY_NOT_EMPTY", f"Directory is not empty: {target}", "Move or delete the contents first.")
            target.rmdir()
        else:
            target.unlink()
        return str(target)


def build_bridge() -> FilesBridge:
    return FilesBridge(load_settings().allowed_roots)
