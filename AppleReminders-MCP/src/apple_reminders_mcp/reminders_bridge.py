from __future__ import annotations

from pathlib import Path
import json
import subprocess

from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.models import ReminderDetail, ReminderListInfo, ReminderSummary


class RemindersBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class RemindersBridge:
    def __init__(self, helper_source: Path, helper_binary: Path) -> None:
        self.helper_source = helper_source
        self.helper_binary = helper_binary

    def helper_available(self) -> tuple[bool, bool]:
        return self.helper_source.exists(), self.helper_binary.exists()

    def list_lists(self) -> list[ReminderListInfo]:
        payload = self._run_helper("list-reminder-lists")
        return [ReminderListInfo.model_validate(item) for item in payload.get("items", [])]

    def list_reminders(
        self,
        *,
        list_id: str | None = None,
        include_completed: bool = True,
        limit: int = 100,
        search: str | None = None,
        due_after: str | None = None,
        due_before: str | None = None,
    ) -> list[ReminderSummary]:
        request = {
            "list_id": list_id,
            "include_completed": include_completed,
            "limit": limit,
            "search": search,
            "due_after": due_after,
            "due_before": due_before,
        }
        payload = self._run_helper("list-reminders", json.dumps(request))
        return [self._to_summary(item) for item in payload.get("items", [])]

    def get_reminder(self, reminder_id: str) -> ReminderDetail:
        payload = self._run_helper("get-reminder", reminder_id)
        return ReminderDetail.model_validate(payload)

    def create_reminder(
        self,
        *,
        title: str,
        list_id: str,
        notes: str | None = None,
        due_date: str | None = None,
        due_all_day: bool = False,
        remind_at: str | None = None,
        priority: int = 0,
    ) -> ReminderDetail:
        request = {
            "title": title,
            "list_id": list_id,
            "notes": notes,
            "due_date": due_date,
            "due_all_day": due_all_day,
            "remind_at": remind_at,
            "priority": priority,
        }
        payload = self._run_helper("create-reminder", json.dumps(request))
        return ReminderDetail.model_validate(payload)

    def update_reminder(
        self,
        reminder_id: str,
        *,
        title: str | None = None,
        list_id: str | None = None,
        notes: str | None = None,
        due_date: str | None = None,
        due_all_day: bool | None = None,
        remind_at: str | None = None,
        priority: int | None = None,
        completed: bool | None = None,
    ) -> ReminderDetail:
        request: dict[str, object] = {}
        if title is not None:
            request["title"] = title
        if list_id is not None:
            request["list_id"] = list_id
        if notes is not None:
            request["notes"] = notes
        if due_date is not None:
            request["due_date"] = due_date
        if due_all_day is not None:
            request["due_all_day"] = due_all_day
        if remind_at is not None:
            request["remind_at"] = remind_at
        if priority is not None:
            request["priority"] = priority
        if completed is not None:
            request["completed"] = completed
        payload = self._run_helper("update-reminder", reminder_id, json.dumps(request))
        return ReminderDetail.model_validate(payload)

    def set_completed(self, reminder_id: str, completed: bool) -> ReminderDetail:
        payload = self._run_helper("set-reminder-completed", reminder_id, "true" if completed else "false")
        return ReminderDetail.model_validate(payload)

    def delete_reminder(self, reminder_id: str) -> bool:
        payload = self._run_helper("delete-reminder", reminder_id)
        return bool(payload.get("deleted", False))

    def _run_helper(self, command: str, *args: str) -> dict[str, object]:
        self._ensure_helper()
        completed = subprocess.run(
            [str(self.helper_binary), command, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        output = completed.stdout.strip()
        if completed.returncode != 0:
            self._raise_helper_error(output, completed.stderr.strip())

        if not output:
            return {}

        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RemindersBridgeError(
                "INVALID_HELPER_OUTPUT",
                f"Native helper returned invalid JSON: {exc.msg}.",
                "Inspect the helper output and retry.",
            ) from exc

        if not isinstance(payload, dict):
            raise RemindersBridgeError(
                "INVALID_HELPER_OUTPUT",
                "Native helper output must be a JSON object.",
                "Inspect the helper output and retry.",
            )
        return payload

    def _ensure_helper(self) -> None:
        if not self.helper_source.exists():
            raise RemindersBridgeError(
                "HELPER_SOURCE_MISSING",
                f"Missing native helper source at '{self.helper_source}'.",
                "Restore the shared Swift helper and retry.",
            )
        if self.helper_binary.exists() and self.helper_binary.stat().st_mtime >= self.helper_source.stat().st_mtime:
            return

        self.helper_binary.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["swiftc", "-parse-as-library", "-O", str(self.helper_source), "-o", str(self.helper_binary)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RemindersBridgeError(
                "HELPER_COMPILE_FAILED",
                completed.stderr.strip() or completed.stdout.strip() or "Failed to compile the native helper.",
                "Confirm Xcode command line tools and Swift are available, then retry.",
            )

    def _raise_helper_error(self, stdout_text: str, stderr_text: str) -> None:
        if stdout_text:
            try:
                payload = json.loads(stdout_text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                raise RemindersBridgeError(
                    str(payload.get("error_code", "HELPER_EXECUTION_FAILED")),
                    str(payload.get("message", "Native helper execution failed.")),
                    payload.get("suggestion"),
                )
        raise RemindersBridgeError(
            "HELPER_EXECUTION_FAILED",
            stderr_text or stdout_text or "Native helper execution failed.",
            "Inspect helper stderr and retry.",
        )

    def _to_summary(self, payload: object) -> ReminderSummary:
        return ReminderSummary.model_validate(payload)


def build_bridge() -> RemindersBridge:
    settings = load_settings()
    return RemindersBridge(settings.helper_source, settings.helper_binary)
