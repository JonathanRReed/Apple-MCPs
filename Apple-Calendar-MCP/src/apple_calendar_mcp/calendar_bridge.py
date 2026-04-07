from pathlib import Path
from datetime import datetime
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
        if self._helper_read_blocked():
            payload = self._fallback_list_calendars()
        else:
            try:
                payload = self._run_helper("list-calendar-calendars")
            except CalendarBridgeError as exc:
                if not self._should_use_read_fallback(exc):
                    raise
                payload = self._fallback_list_calendars()
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
        if self._helper_read_blocked():
            payload = self._fallback_list_events(start_iso, end_iso, calendar_id=calendar_id, limit=limit)
        else:
            try:
                payload = self._run_helper("list-calendar-events", json.dumps(request))
            except CalendarBridgeError as exc:
                if not self._should_use_read_fallback(exc):
                    raise
                payload = self._fallback_list_events(start_iso, end_iso, calendar_id=calendar_id, limit=limit)
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

    def _should_use_read_fallback(self, error: CalendarBridgeError) -> bool:
        return error.error_code in {
            "PERMISSION_DENIED",
            "PERMISSION_REQUEST_FAILED",
            "PERMISSION_TIMEOUT",
            "PERMISSION_UNKNOWN",
            "HELPER_SOURCE_MISSING",
            "HELPER_COMPILE_FAILED",
            "HELPER_EXECUTION_FAILED",
        }

    def _helper_read_blocked(self) -> bool:
        try:
            payload = self.calendar_access_status()
        except CalendarBridgeError:
            return False
        return not bool(payload.get("can_read_events", False))

    def _fallback_list_calendars(self) -> dict[str, object]:
        script = """
function run(argv) {
  const app = Application("Calendar");
  const items = app.calendars().map(function(cal) {
    const name = cal.name();
    return {
      calendar_id: name,
      title: name,
      source_title: null,
      color_hex: null,
      allows_content_modifications: null
    };
  });
  return JSON.stringify({items: items});
}
"""
        return self._run_jxa(script)

    def _fallback_list_events(self, start_iso: str, end_iso: str, calendar_id: str | None = None, limit: int = 100) -> dict[str, object]:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        script = """
function isAllDay(startDate, endDate) {
  return startDate.getHours() === 0 &&
    startDate.getMinutes() === 0 &&
    startDate.getSeconds() === 0 &&
    endDate.getHours() === 23 &&
    endDate.getMinutes() === 59;
}

function run(argv) {
  const start = new Date(argv[0]);
  const end = new Date(argv[1]);
  const calendarFilter = argv[2] || "";
  const limit = parseInt(argv[3], 10);
  const app = Application("Calendar");
  const items = [];

  app.calendars().forEach(function(cal) {
    const calendarName = cal.name();
    if (calendarFilter && calendarName !== calendarFilter) {
      return;
    }
    const events = app.calendars.byName(calendarName).events.whose({
      startDate: {
        _greaterThan: start,
        _lessThan: end
      }
    })();

    events.forEach(function(evt) {
      const startDate = evt.startDate();
      const endDate = evt.endDate();
      const title = evt.summary() || "";
      const eventId = evt.uid ? evt.uid() : (evt.id ? evt.id() : null);
      items.push({
        event_id: eventId || ("applescript::" + calendarName + "::" + startDate.toISOString() + "::" + title),
        title: title,
        calendar_id: calendarName,
        calendar_name: calendarName,
        start: startDate.toISOString(),
        end: endDate.toISOString(),
        all_day: isAllDay(startDate, endDate),
        location: evt.location ? (evt.location() || null) : null
      });
    });
  });

  items.sort(function(a, b) {
    const dateOrder = new Date(a.start) - new Date(b.start);
    if (dateOrder !== 0) {
      return dateOrder;
    }
    return a.title.localeCompare(b.title);
  });

  return JSON.stringify({items: items.slice(0, isNaN(limit) ? 100 : limit)});
}
"""
        return self._run_jxa(script, start.isoformat(), end.isoformat(), calendar_id or "", str(limit))

    def _run_jxa(self, script: str, *args: str) -> dict[str, object]:
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        output = completed.stdout.strip()
        if completed.returncode != 0:
            raise CalendarBridgeError(
                "APPLESCRIPT_FALLBACK_FAILED",
                completed.stderr.strip() or output or "Calendar AppleScript fallback failed.",
                "Confirm Calendar.app automation is allowed, then retry.",
            )
        if not output:
            return {}
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise CalendarBridgeError(
                "INVALID_HELPER_OUTPUT",
                f"Calendar AppleScript fallback returned invalid JSON: {exc.msg}.",
                "Inspect the fallback output and retry.",
            ) from exc
        if not isinstance(payload, dict):
            raise CalendarBridgeError(
                "INVALID_HELPER_OUTPUT",
                "Calendar AppleScript fallback output must decode to a JSON object.",
                "Inspect the fallback output and retry.",
            )
        return payload

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
