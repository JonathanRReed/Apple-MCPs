from __future__ import annotations

from functools import lru_cache
from html import escape as html_escape
from pathlib import Path
import json
import re
import subprocess
import time

from apple_notes_mcp.config import load_settings
from apple_notes_mcp.models import AccountInfo, AttachmentInfo, FolderInfo, NoteDetail, NoteSummary


class NotesBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class AppleNotesBridge:
    def __init__(self, scripts_dir: Path) -> None:
        self.scripts_dir = scripts_dir
        self._body_html_cache: dict[str, str] = {}

    def list_accounts(self) -> list[AccountInfo]:
        payload = self._run_script("list_accounts.applescript")
        return [AccountInfo.model_validate(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def list_folders(self, account_name: str | None = None) -> list[FolderInfo]:
        payload = self._run_script("list_folders.applescript", account_name or "")
        return [FolderInfo.model_validate(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def list_notes(
        self,
        account_name: str | None = None,
        folder_id: str | None = None,
    ) -> list[NoteSummary]:
        payload = self._run_script("list_notes.applescript", account_name or "", folder_id or "")
        return [self._normalize_summary(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def get_note(self, note_id: str) -> NoteDetail:
        payload = self._run_script("get_note.applescript", note_id)
        if not payload.get("found", True):
            raise NotesBridgeError("NOTE_NOT_FOUND", f"No note matched '{note_id}'.", "List notes first to discover valid ids.")
        raw_note = payload.get("note")
        if not isinstance(raw_note, dict):
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", "The get_note AppleScript did not return a note object.", "Inspect the AppleScript output and try again.")
        note_id = str(raw_note.get("note_id", note_id))
        detail = self._normalize_detail(raw_note, body_html_override=self._body_html_cache.get(note_id))
        detail.attachments = self.list_attachments(note_id)
        detail.attachment_count = len(detail.attachments)
        return detail

    def create_note(
        self,
        *,
        title: str,
        folder_id: str,
        body_html: str | None = None,
        tags: list[str] | None = None,
    ) -> NoteDetail:
        prepared_body_html = self._prepare_body_html(title, body_html) if body_html is not None else None
        payload = self._run_script(
            "create_note.applescript",
            title,
            folder_id,
            "",
            "",
        )
        raw_note = payload.get("note")
        if not isinstance(raw_note, dict):
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", "The create_note AppleScript did not return a note object.", "Inspect the AppleScript output and try again.")
        detail = self._normalize_detail(raw_note)
        if body_html or tags:
            last_error: NotesBridgeError | None = None
            for _ in range(3):
                try:
                    time.sleep(0.5)
                    updated = self.update_note(detail.note_id, title=title, body_html=prepared_body_html, tags=tags)
                    if updated.body_html:
                        self._body_html_cache[updated.note_id] = updated.body_html
                    return updated
                except NotesBridgeError as exc:
                    last_error = exc
            if last_error is not None:
                raise last_error
        if detail.body_html:
            self._body_html_cache[detail.note_id] = detail.body_html
        return detail

    def update_note(
        self,
        note_id: str,
        *,
        title: str | None = None,
        body_html: str | None = None,
        folder_id: str | None = None,
        tags: list[str] | None = None,
    ) -> NoteDetail:
        prepared_body_html = body_html
        if title is not None:
            body_source = body_html
            if body_source is None:
                current = self.get_note(note_id)
                body_source = current.body_html or self._html_from_plaintext(current.plaintext)
            prepared_body_html = self._prepare_body_html(title, body_source)
        payload = self._run_script(
            "update_note.applescript",
            note_id,
            title or "",
            prepared_body_html or "",
            folder_id or "",
            ",".join(tags or []),
        )
        raw_note = payload.get("note")
        if not isinstance(raw_note, dict):
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", "The update_note AppleScript did not return a note object.", "Inspect the AppleScript output and try again.")
        detail = self._normalize_detail(raw_note, body_html_override=prepared_body_html)
        if detail.body_html:
            self._body_html_cache[detail.note_id] = detail.body_html
        return detail

    def move_note(self, note_id: str, folder_id: str) -> NoteDetail:
        return self.update_note(note_id, folder_id=folder_id)

    def append_to_note(self, note_id: str, body_html: str) -> NoteDetail:
        current = self.get_note(note_id)
        existing_html = current.body_html or self._html_from_plaintext(current.plaintext)
        combined_html = existing_html + body_html
        return self.update_note(note_id, title=current.title, body_html=combined_html)

    def delete_note(self, note_id: str) -> bool:
        payload = self._run_script("delete_note.applescript", note_id)
        deleted = bool(payload.get("deleted", False))
        if deleted:
            self._body_html_cache.pop(note_id, None)
        return deleted

    def create_folder(self, *, folder_name: str, account_name: str, parent_folder_id: str | None = None) -> FolderInfo:
        payload = self._run_script("create_folder.applescript", folder_name, account_name, parent_folder_id or "")
        raw_folder = payload.get("folder")
        if not isinstance(raw_folder, dict):
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", "The create_folder AppleScript did not return a folder object.", "Inspect the AppleScript output and try again.")
        return FolderInfo.model_validate(raw_folder)

    def rename_folder(self, folder_id: str, folder_name: str) -> FolderInfo:
        payload = self._run_script("rename_folder.applescript", folder_id, folder_name)
        raw_folder = payload.get("folder")
        if not isinstance(raw_folder, dict):
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", "The rename_folder AppleScript did not return a folder object.", "Inspect the AppleScript output and try again.")
        return FolderInfo.model_validate(raw_folder)

    def delete_folder(self, folder_id: str) -> bool:
        payload = self._run_script("delete_folder.applescript", folder_id)
        return bool(payload.get("deleted", False))

    def list_attachments(self, note_id: str) -> list[AttachmentInfo]:
        payload = self._run_script("list_attachments.applescript", note_id)
        return [AttachmentInfo.model_validate(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def search_notes(
        self,
        query: str,
        account_name: str | None = None,
        folder_id: str | None = None,
        limit: int = 25,
    ) -> list[NoteSummary]:
        query_text = query.strip().lower()
        notes = self.list_notes(account_name=account_name, folder_id=folder_id)
        matched: list[NoteSummary] = []
        for note in notes:
            haystack = " ".join(
                [
                    note.title,
                    note.plaintext,
                    note.folder_name,
                    note.account_name,
                    " ".join(note.tags),
                ]
            ).lower()
            if not query_text or query_text in haystack:
                matched.append(note)
        matched.sort(key=lambda item: item.modified_epoch or 0, reverse=True)
        return matched[: max(1, min(limit, 100))]

    def _run_script(self, script_name: str, *args: str) -> dict[str, object]:
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise NotesBridgeError("SCRIPT_NOT_FOUND", f"Missing AppleScript file '{script_name}'.", "Restore the AppleScript file and try again.")

        completed = subprocess.run(["osascript", str(script_path), *args], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise self._map_script_error(completed.stderr.strip() or completed.stdout.strip())

        output = completed.stdout.strip()
        if not output:
            return {}

        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", f"AppleScript returned invalid JSON: {exc.msg}.", "Inspect the AppleScript output and ensure it returns valid JSON.") from exc

        if not isinstance(payload, dict):
            raise NotesBridgeError("INVALID_SCRIPT_OUTPUT", "AppleScript output must decode to a JSON object.", "Inspect the AppleScript output and ensure it returns an object.")
        return payload

    def _map_script_error(self, error_text: str) -> NotesBridgeError:
        lowered = error_text.lower()
        if "not authorized" in lowered or "automation" in lowered:
            return NotesBridgeError("PERMISSION_DENIED", "macOS denied automation access to Notes.", "Allow automation access for the process running this server and retry.")
        if "can't get note" in lowered or "can’t get note" in lowered:
            return NotesBridgeError("NOTE_NOT_FOUND", error_text, "List notes first to discover valid note ids.")
        if "can't get folder" in lowered or "can’t get folder" in lowered:
            return NotesBridgeError("FOLDER_NOT_FOUND", error_text, "List folders first to discover valid folder ids.")
        return NotesBridgeError("APPLESCRIPT_EXECUTION_FAILED", error_text or "AppleScript execution failed.", "Inspect Notes.app state and the AppleScript file, then retry.")

    def _normalize_summary(self, raw_note: dict[str, object], *, body_html_override: str | None = None) -> NoteSummary:
        plaintext = self._optional_text(raw_note.get("plaintext")) or ""
        body_html = self._resolved_body_html(raw_note, body_html_override=body_html_override)
        tags = self._derive_tags(plaintext)
        attachment_count = int(raw_note.get("attachment_count", 0) or 0)
        folder_id = self._optional_text(raw_note.get("folder_id")) or ""
        folder = self._folder_by_id(folder_id)
        account_name = self._optional_text(raw_note.get("account_name")) or (folder.account_name if folder is not None else "")
        account_id = self._optional_text(raw_note.get("account_id")) or (folder.account_id if folder is not None else "")
        folder_name = self._optional_text(raw_note.get("folder_name")) or (folder.name if folder is not None else "")
        return NoteSummary(
            note_id=str(raw_note.get("note_id", "")),
            title=self._optional_text(raw_note.get("title")) or "",
            account_id=account_id,
            account_name=account_name,
            folder_id=folder_id,
            folder_name=folder_name,
            created_epoch=self._optional_int(raw_note.get("created_epoch")),
            modified_epoch=self._optional_int(raw_note.get("modified_epoch")),
            password_protected=bool(raw_note.get("password_protected", False)),
            shared=bool(raw_note.get("shared", False)),
            tags=tags,
            plaintext=plaintext or self._plain_text_from_html(body_html),
            preview=(plaintext or body_html)[:240],
            attachment_count=attachment_count,
        )

    def _normalize_detail(self, raw_note: dict[str, object], *, body_html_override: str | None = None) -> NoteDetail:
        summary = self._normalize_summary(raw_note, body_html_override=body_html_override)
        attachments = [AttachmentInfo.model_validate(item) for item in raw_note.get("attachments", []) if isinstance(item, dict)]
        return NoteDetail(
            **summary.model_dump(),
            body_html=self._resolved_body_html(raw_note, body_html_override=body_html_override),
            attachments=attachments,
        )

    def _folder_by_id(self, folder_id: str) -> FolderInfo | None:
        if not folder_id:
            return None
        for folder in self.list_folders():
            if folder.folder_id == folder_id:
                return folder
        return None

    def _optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _plain_text_from_html(self, html_body: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html_body, flags=re.IGNORECASE)
        text = re.sub(r"</div>|</p>|</h[1-6]>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def _html_from_plaintext(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        lines = plaintext.splitlines() or [plaintext]
        html_lines = []
        for line in lines:
            if line.strip():
                html_lines.append(f"<div>{html_escape(line)}</div>")
            else:
                html_lines.append("<div><br></div>")
        return "".join(html_lines)

    def _resolved_body_html(self, raw_note: dict[str, object], *, body_html_override: str | None = None) -> str:
        body_html = self._optional_text(raw_note.get("body_html"))
        if body_html:
            return body_html
        if body_html_override:
            return body_html_override
        plaintext = self._optional_text(raw_note.get("plaintext")) or ""
        return self._html_from_plaintext(plaintext)

    def _prepare_body_html(self, title: str | None, body_html: str | None) -> str | None:
        if body_html is None:
            return None
        normalized_title = (title or "").strip()
        if not normalized_title:
            return body_html
        first_visible_line = ""
        plaintext = self._plain_text_from_html(body_html)
        for line in plaintext.splitlines():
            stripped = line.strip()
            if stripped:
                first_visible_line = stripped
                break
        if first_visible_line == normalized_title:
            return body_html
        title_block = f"<div>{html_escape(normalized_title)}</div>"
        if not body_html:
            return title_block
        return title_block + "<div><br></div>" + body_html

    def _derive_tags(self, plaintext: str) -> list[str]:
        found = re.findall(r"(?<!\w)#([A-Za-z0-9_-]+)", plaintext)
        seen: list[str] = []
        for tag in found:
            if tag not in seen:
                seen.append(tag)
        return seen


@lru_cache(maxsize=1)
def build_bridge() -> AppleNotesBridge:
    return AppleNotesBridge(load_settings().scripts_dir)
