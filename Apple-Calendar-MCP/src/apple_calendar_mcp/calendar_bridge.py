from pathlib import Path
import json
import subprocess

from apple_calendar_mcp.models import CalendarInfo, EventDetail, EventSummary


class CalendarBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class CalendarBridge:
    def __init__(self, helper_source: Path, helper_binary: Path) -> None:
        self.helper_source = helper_source
        self.helper_binary = helper_binary

    def helper_available(self) -> tuple[bool, bool]:
        return self.helper_source.exists(), self.helper_binary.exists()

    def list_calendars(self) -> list[CalendarInfo]:
        payload = self._run_helper("list-calendar-calendars")
        calendars = payload.get("items", [])
        return [
            CalendarInfo(
                calendar_id=str(item.get("calendar_id", "")),
                name=str(item.get("title", "")),
                source_title=self._optional_text(item.get("source_title")),
                color_hex=self._optional_text(item.get("color_hex")),
                writable=bool(item.get("allows_content_modifications", False)),
            )
            for item in calendars
            if isinstance(item, dict)
        ]

    def calendar_access_status(self) -> dict[str, object]:
        return self._run_helper("calendar-access-status")

    def list_events(self, start_iso: str, end_iso: str, calendar_id: str | None = None, limit: int = 100) -> list[EventSummary]:
        request = {
            "start": start_iso,
            "end": end_iso,
            "calendar_id": calendar_id,
            "limit": limit,
        }
        payload = self._run_helper("list-calendar-events", json.dumps(request))
        return [self._normalize_summary(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def get_event(self, event_id: str) -> EventDetail:
        payload = self._run_helper("get-calendar-event", event_id)
        return self._normalize_detail(payload)

    def create_event(
        self,
        *,
        title: str,
        calendar_id: str,
        start_iso: str,
        end_iso: str,
        notes: str | None = None,
        location: str | None = None,
        all_day: bool = False,
        recurrence: dict[str, object] | None = None,
    ) -> EventDetail:
        request = {
            "title": title,
            "calendar_id": calendar_id,
            "start": start_iso,
            "end": end_iso,
            "notes": notes,
            "location": location,
            "all_day": all_day,
        }
        if recurrence is not None:
            request["recurrence"] = recurrence
        payload = self._run_helper("create-calendar-event", json.dumps(request))
        return self._normalize_detail(payload)

    def update_event(
        self,
        event_id: str,
        *,
        title: str | None = None,
        calendar_id: str | None = None,
        start_iso: str | None = None,
        end_iso: str | None = None,
        notes: str | None = None,
        location: str | None = None,
        all_day: bool | None = None,
        recurrence: dict[str, object] | None = None,
    ) -> EventDetail:
        request: dict[str, object] = {}
        if title is not None:
            request["title"] = title
        if calendar_id is not None:
            request["calendar_id"] = calendar_id
        if start_iso is not None:
            request["start"] = start_iso
        if end_iso is not None:
            request["end"] = end_iso
        if notes is not None:
            request["notes"] = notes
        if location is not None:
            request["location"] = location
        if all_day is not None:
            request["all_day"] = all_day
        if recurrence is not None:
            request["recurrence"] = recurrence
        payload = self._run_helper("update-calendar-event", event_id, json.dumps(request))
        return self._normalize_detail(payload)

    def delete_event(self, event_id: str) -> bool:
        payload = self._run_helper("delete-calendar-event", event_id)
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
            raise self._map_helper_error(output, completed.stderr.strip())
        if not output:
            return {}

        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise CalendarBridgeError(
                "INVALID_HELPER_OUTPUT",
                f"Native helper returned invalid JSON: {exc.msg}.",
                "Inspect the helper output and retry.",
            ) from exc

        if not isinstance(payload, dict):
            raise CalendarBridgeError(
                "INVALID_HELPER_OUTPUT",
                "Native helper output must decode to a JSON object.",
                "Inspect the helper output and retry.",
            )
        return payload

    def _ensure_helper(self) -> None:
        if not self.helper_source.exists():
            raise CalendarBridgeError(
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
            raise CalendarBridgeError(
                "HELPER_COMPILE_FAILED",
                completed.stderr.strip() or completed.stdout.strip() or "Failed to compile the native helper.",
                "Confirm Xcode command line tools and Swift are available, then retry.",
            )

    def _map_helper_error(self, stdout_text: str, stderr_text: str) -> CalendarBridgeError:
        if stdout_text:
            try:
                payload = json.loads(stdout_text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                return CalendarBridgeError(
                    str(payload.get("error_code", "HELPER_EXECUTION_FAILED")),
                    str(payload.get("message", "Native helper execution failed.")),
                    payload.get("suggestion"),
                )
        return CalendarBridgeError(
            "HELPER_EXECUTION_FAILED",
            stderr_text or stdout_text or "Native helper execution failed.",
            "Inspect helper stderr and retry.",
        )

    def _normalize_summary(self, raw_event: dict[str, object]) -> EventSummary:
        return EventSummary(
            event_id=str(raw_event.get("event_id", "")),
            title=str(raw_event.get("title", "")),
            calendar_id=str(raw_event.get("calendar_id", "")),
            calendar_name=str(raw_event.get("calendar_name", "")),
            start=str(raw_event.get("start", "")),
            end=str(raw_event.get("end", "")),
            all_day=bool(raw_event.get("all_day", False)),
            location=self._optional_text(raw_event.get("location")),
            availability=None,
        )

    def _normalize_detail(self, raw_event: dict[str, object]) -> EventDetail:
        summary_dict = self._normalize_summary(raw_event).model_dump()
        summary_dict["notes"] = self._optional_text(raw_event.get("notes"))
        if raw_event.get("recurrence_rule") is not None:
            summary_dict["recurrence_rule"] = raw_event["recurrence_rule"]
        if raw_event.get("attendees") is not None:
            summary_dict["attendees"] = raw_event["attendees"]
        return EventDetail.model_validate(summary_dict)

    def _optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
