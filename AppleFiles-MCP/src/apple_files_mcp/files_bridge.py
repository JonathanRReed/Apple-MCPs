from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import heapq
import os
from pathlib import Path
import plistlib
import subprocess

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
    _ICLOUD_SUFFIX = Path("Library/Mobile Documents/com~apple~CloudDocs")

    def __init__(self, allowed_roots: tuple[Path, ...]) -> None:
        self.allowed_roots = tuple(path.expanduser().resolve(strict=False) for path in allowed_roots)

    def list_allowed_roots(self) -> list[str]:
        return [str(path) for path in self.allowed_roots]

    def _icloud_root(self) -> Path | None:
        root = Path.home() / self._ICLOUD_SUFFIX
        return root if root.exists() else None

    def _is_icloud_path(self, path: Path) -> bool:
        icloud_root = self._icloud_root()
        return icloud_root is not None and path.is_relative_to(icloud_root)

    def _location_kind(self, path: Path) -> str:
        return "icloud" if self._is_icloud_path(path) else "local"

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
            tags=[],
            is_icloud=self._is_icloud_path(path),
            location_kind=self._location_kind(path),
        )

    def _run(self, *command: str) -> str:
        try:
            result = subprocess.run(
                list(command),
                capture_output=True,
                check=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError as exc:
            raise FilesBridgeError("COMMAND_NOT_FOUND", f"Missing command: {command[0]}", "Run this server on macOS.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip()
            raise FilesBridgeError("COMMAND_FAILED", stderr or "File system command failed.", "Retry the request.") from exc
        except subprocess.TimeoutExpired as exc:
            raise FilesBridgeError("COMMAND_TIMEOUT", f"Timed out while running {command[0]}.", "Retry the request.") from exc
        return result.stdout.strip()

    def _read_tag_attribute(self, path: Path) -> list[str]:
        try:
            raw = self._run("xattr", "-px", "com.apple.metadata:_kMDItemUserTags", str(path))
        except FilesBridgeError as exc:
            if exc.error_code == "COMMAND_FAILED" and "no such xattr" in exc.message.lower():
                return []
            raise
        if not raw:
            return []
        payload = bytes.fromhex("".join(raw.split()))
        try:
            values = plistlib.loads(payload)
        except Exception as exc:
            raise FilesBridgeError("TAG_READ_FAILED", f"Could not decode Finder tags for {path}.", "Retry the request.") from exc
        if not isinstance(values, list):
            return []
        tags: list[str] = []
        for item in values:
            if not isinstance(item, str):
                continue
            visible = item.split("\n", 1)[0].strip()
            if visible and visible not in tags:
                tags.append(visible)
        return tags

    def _write_tag_attribute(self, path: Path, tags: list[str]) -> None:
        normalized = []
        seen: set[str] = set()
        for tag in tags:
            cleaned = tag.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        if not normalized:
            try:
                self._run("xattr", "-d", "com.apple.metadata:_kMDItemUserTags", str(path))
            except FilesBridgeError as exc:
                if exc.error_code == "COMMAND_FAILED" and "no such xattr" in exc.message.lower():
                    return
                raise
            return
        payload = plistlib.dumps(normalized, fmt=plistlib.FMT_BINARY).hex()
        self._run("xattr", "-wx", "com.apple.metadata:_kMDItemUserTags", payload, str(path))

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
        if limit <= 0:
            return []
        newest: list[tuple[float, str]] = []
        for root in self.allowed_roots:
            try:
                candidates = self._recent_files_for_root(root)
            except FilesBridgeError as exc:
                if exc.error_code in {"COMMAND_TIMEOUT", "COMMAND_FAILED"}:
                    continue
                raise
            for modified_ts, path_text in candidates:
                if len(newest) < limit:
                    heapq.heappush(newest, (modified_ts, path_text))
                else:
                    heapq.heappushpop(newest, (modified_ts, path_text))
        entries: list[FileEntry] = []
        seen_paths: set[str] = set()
        for _, path_text in sorted(newest, reverse=True):
            if path_text in seen_paths:
                continue
            seen_paths.add(path_text)
            try:
                entries.append(self._entry(Path(path_text)))
            except OSError:
                continue
        return entries[:limit]

    def _recent_files_for_root(self, root: Path) -> list[tuple[float, str]]:
        if not root.exists():
            return []
        try:
            completed = subprocess.run(
                [
                    "find",
                    str(root),
                    "-type",
                    "d",
                    "-name",
                    ".*",
                    "-prune",
                    "-o",
                    "-type",
                    "f",
                    "!",
                    "-name",
                    ".*",
                    "-exec",
                    "stat",
                    "-f",
                    "%m\t%N",
                    "{}",
                    "+",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=8,
            )
        except FileNotFoundError as exc:
            raise FilesBridgeError("COMMAND_NOT_FOUND", "Missing find/stat command.", "Run this server on macOS.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip()
            raise FilesBridgeError("COMMAND_FAILED", stderr or f"Recent file scan failed for {root}.", "Retry the request.") from exc
        except subprocess.TimeoutExpired as exc:
            raise FilesBridgeError("COMMAND_TIMEOUT", f"Recent file scan timed out for {root}.", "Retry the request with fewer allowed roots.") from exc
        candidates: list[tuple[float, str]] = []
        for line in completed.stdout.splitlines():
            if "\t" not in line:
                continue
            modified_text, path_text = line.split("\t", 1)
            cleaned_path = path_text.strip().strip('"')
            if not cleaned_path:
                continue
            try:
                modified_ts = float(modified_text)
            except ValueError:
                continue
            candidates.append((modified_ts, cleaned_path))
        return candidates

    def open_path(self, path: str) -> str:
        target = self._ensure_allowed(path)
        self._run("open", str(target))
        return str(target)

    def reveal_in_finder(self, path: str) -> str:
        target = self._ensure_allowed(path)
        self._run("open", "-R", str(target))
        return str(target)

    def get_tags(self, path: str) -> tuple[str, list[str], bool]:
        target = self._ensure_allowed(path)
        tags = self._read_tag_attribute(target)
        return str(target), tags, self._is_icloud_path(target)

    def set_tags(self, path: str, tags: list[str]) -> tuple[str, list[str], bool]:
        target = self._ensure_allowed(path)
        self._write_tag_attribute(target, tags)
        current_tags = self._read_tag_attribute(target)
        return str(target), current_tags, self._is_icloud_path(target)

    def add_tags(self, path: str, tags: list[str]) -> tuple[str, list[str], bool]:
        target = self._ensure_allowed(path)
        current = self._read_tag_attribute(target)
        merged = [*current]
        for tag in tags:
            cleaned = tag.strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
        self._write_tag_attribute(target, merged)
        return str(target), self._read_tag_attribute(target), self._is_icloud_path(target)

    def remove_tags(self, path: str, tags: list[str]) -> tuple[str, list[str], bool]:
        target = self._ensure_allowed(path)
        remove_set = {tag.strip() for tag in tags if tag.strip()}
        current = [tag for tag in self._read_tag_attribute(target) if tag not in remove_set]
        self._write_tag_attribute(target, current)
        return str(target), self._read_tag_attribute(target), self._is_icloud_path(target)

    def list_recent_locations(self, limit: int = 15) -> list[FileEntry]:
        files = self.recent_files(limit=max(limit * 4, limit))
        latest_by_parent: dict[str, FileEntry] = {}
        for item in files:
            parent_path = Path(item.parent)
            parent_key = str(parent_path)
            if parent_key not in latest_by_parent:
                latest_by_parent[parent_key] = self._entry(parent_path)
            if len(latest_by_parent) >= limit:
                break
        locations = list(latest_by_parent.values())
        locations.sort(key=lambda item: item.modified_at or "", reverse=True)
        return locations[:limit]

    def icloud_status(self) -> dict[str, object]:
        icloud_root = self._icloud_root()
        allowed_roots = []
        for root in self.allowed_roots:
            allowed_roots.append(
                {
                    "path": str(root),
                    "is_icloud": self._is_icloud_path(root),
                    "location_kind": self._location_kind(root),
                }
            )
        return {
            "available": icloud_root is not None,
            "root_path": str(icloud_root) if icloud_root is not None else None,
            "allowed_root_present": any(item["is_icloud"] for item in allowed_roots),
            "allowed_roots": allowed_roots,
        }

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
