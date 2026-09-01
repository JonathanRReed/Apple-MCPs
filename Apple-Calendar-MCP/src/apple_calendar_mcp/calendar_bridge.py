import json
import subprocess
from datetime import datetime
from pathlib import Path

from apple_calendar_mcp.models import CalendarInfo, EventDetail, EventSummary


class CalendarBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class CalendarBridge:
    _JXA_TIMEOUT_SECONDS = 30

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
            payload = self._fallback_events_payload(start_iso, end_iso, calendar_id=calendar_id, limit=limit)
        else:
            try:
                payload = self._run_helper("list-calendar-events", json.dumps(request))
            except CalendarBridgeError as exc:
                if not self._should_use_read_fallback(exc):
                    raise
                payload = self._fallback_events_payload(start_iso, end_iso, calendar_id=calendar_id, limit=limit)
        return [
            self._normalize_summary(item)
            for item in self._dedupe_event_items(payload.get("items", []), limit=limit)
        ]

    def get_event(self, event_id: str) -> EventDetail:
        try:
            payload = self._run_helper("get-calendar-event", event_id)
        except CalendarBridgeError as exc:
            if not self._should_use_fallback(exc):
                raise
            payload = self._fallback_get_event(event_id)
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
        try:
            payload = self._run_helper("create-calendar-event", json.dumps(request))
        except CalendarBridgeError as exc:
            if not self._should_use_fallback(exc):
                raise
            # The identifier came from the JXA read fallback (a calendar NAME,
            # not a real EKCalendar.calendarIdentifier), so the native helper
            # can never resolve it. Create the event by name instead.
            payload = self._fallback_create_event(
                title=title,
                calendar_id=calendar_id,
                start_iso=start_iso,
                end_iso=end_iso,
                notes=notes,
                location=location,
                all_day=all_day,
            )
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
        try:
            payload = self._run_helper("update-calendar-event", event_id, json.dumps(request))
        except CalendarBridgeError as exc:
            if not self._should_use_fallback(exc):
                raise
            payload = self._fallback_update_event(
                event_id,
                title=title,
                calendar_id=calendar_id,
                start_iso=start_iso,
                end_iso=end_iso,
                notes=notes,
                location=location,
                all_day=all_day,
            )
        return self._normalize_detail(payload)

    def delete_event(self, event_id: str) -> bool:
        try:
            payload = self._run_helper("delete-calendar-event", event_id)
        except CalendarBridgeError as exc:
            if not self._should_use_fallback(exc):
                raise
            payload = self._fallback_delete_event(event_id)
        return bool(payload.get("deleted", False))

    def _run_helper(self, command: str, *args: str) -> dict[str, object]:
        self._ensure_helper()
        try:
            completed = subprocess.run(
                [str(self.helper_binary), command, *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise CalendarBridgeError(
                "HELPER_UNAVAILABLE",
                f"Could not run the native helper '{self.helper_binary}': {exc}.",
                "This server requires macOS with the compiled Calendar helper available.",
            ) from exc
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
        try:
            completed = subprocess.run(
                ["swiftc", "-parse-as-library", "-O", str(self.helper_source), "-o", str(self.helper_binary)],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise CalendarBridgeError(
                "SWIFTC_UNAVAILABLE",
                f"Could not run 'swiftc': {exc}.",
                "This server requires macOS with the Swift toolchain (swiftc) available.",
            ) from exc
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

    def _should_use_fallback(self, error: CalendarBridgeError) -> bool:
        # CALENDAR_NOT_FOUND / EVENT_NOT_FOUND on top of the read-fallback
        # codes: when the native EventKit helper only has write-only access
        # (no can_read_events), every id the caller ever saw came from the
        # JXA read fallback below, i.e. a calendar NAME or a synthetic
        # "applescript::..." event id, never a real EKCalendar/EKEvent
        # identifier. The native helper can then never resolve it, no matter
        # how valid the id is, so the same request has to be retried through
        # the JXA fallback instead of surfacing a confusing "not found".
        return self._should_use_read_fallback(error) or error.error_code in {
            "CALENDAR_NOT_FOUND",
            "EVENT_NOT_FOUND",
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
        return self._run_jxa(script, start.isoformat(), end.isoformat(), calendar_id or "", str(limit), timeout=self._JXA_TIMEOUT_SECONDS)

    # Shared by every fallback below: locate an event by the uid the JXA read
    # fallback handed out (or, for delete/update called with a helper-issued
    # "applescript::calendar::start::title" synthetic id, fall back to that
    # composite match too), searching one named calendar first when known,
    # otherwise every calendar.
    _JXA_FIND_EVENT = """
function findEventByUid(app, uid, calendarNameHint) {
  const calendars = calendarNameHint
    ? app.calendars.byName(calendarNameHint) ? [app.calendars.byName(calendarNameHint)] : []
    : app.calendars();
  for (const cal of calendars) {
    const matches = cal.events.whose({uid: uid})();
    if (matches.length > 0) {
      return {calendar: cal, event: matches[0]};
    }
  }
  if (uid.indexOf("applescript::") === 0) {
    const parts = uid.split("::");
    const calName = parts[1];
    const startIso = parts[2];
    const title = parts.slice(3).join("::");
    const targets = calName ? [app.calendars.byName(calName)] : app.calendars();
    for (const cal of targets) {
      const matches = cal.events.whose({summary: title, startDate: new Date(startIso)})();
      if (matches.length > 0) {
        return {calendar: cal, event: matches[0]};
      }
    }
  }
  return null;
}

function eventRecord(cal, evt) {
  const startDate = evt.startDate();
  const endDate = evt.endDate();
  return {
    event_id: evt.uid(),
    title: evt.summary() || "",
    calendar_id: cal.name(),
    calendar_name: cal.name(),
    start: startDate.toISOString(),
    end: endDate.toISOString(),
    all_day: startDate.getHours() === 0 && startDate.getMinutes() === 0 &&
      endDate.getHours() === 23 && endDate.getMinutes() === 59,
    location: evt.location ? (evt.location() || null) : null,
    notes: evt.description ? (evt.description() || null) : null
  };
}
"""

    def _fallback_get_event(self, event_id: str) -> dict[str, object]:
        script = self._JXA_FIND_EVENT + """
function run(argv) {
  const app = Application("Calendar");
  const found = findEventByUid(app, argv[0], "");
  if (!found) {
    return JSON.stringify({__error__: "EVENT_NOT_FOUND"});
  }
  return JSON.stringify(eventRecord(found.calendar, found.event));
}
"""
        return self._run_jxa_event(script, event_id)

    def _fallback_create_event(
        self,
        *,
        title: str,
        calendar_id: str,
        start_iso: str,
        end_iso: str,
        notes: str | None,
        location: str | None,
        all_day: bool,
    ) -> dict[str, object]:
        script = self._JXA_FIND_EVENT + """
function run(argv) {
  const app = Application("Calendar");
  const calName = argv[0];
  const cal = app.calendars.byName(calName);
  if (!cal || !cal.exists()) {
    return JSON.stringify({__error__: "CALENDAR_NOT_FOUND"});
  }
  const newEvent = app.Event({
    summary: argv[1],
    startDate: new Date(argv[2]),
    endDate: new Date(argv[3]),
    location: argv[4],
    description: argv[5]
  });
  cal.events.push(newEvent);
  if (argv[6] === "true") {
    newEvent.alldayEvent = true;
  }
  return JSON.stringify(eventRecord(cal, newEvent));
}
"""
        return self._run_jxa_event(
            script,
            calendar_id,
            title,
            start_iso,
            end_iso,
            location or "",
            notes or "",
            "true" if all_day else "false",
        )

    def _fallback_update_event(
        self,
        event_id: str,
        *,
        title: str | None,
        calendar_id: str | None,
        start_iso: str | None,
        end_iso: str | None,
        notes: str | None,
        location: str | None,
        all_day: bool | None,
    ) -> dict[str, object]:
        fields = {
            "title": title,
            "calendar_id": calendar_id,
            "start": start_iso,
            "end": end_iso,
            "notes": notes,
            "location": location,
            "all_day": all_day,
        }
        script = self._JXA_FIND_EVENT + """
function run(argv) {
  const app = Application("Calendar");
  const eventId = argv[0];
  const fields = JSON.parse(argv[1]);
  const found = findEventByUid(app, eventId, "");
  if (!found) {
    return JSON.stringify({__error__: "EVENT_NOT_FOUND"});
  }
  let cal = found.calendar;
  let evt = found.event;

  const wantsMove = fields.calendar_id && fields.calendar_id !== cal.name();
  if (wantsMove) {
    const targetCal = app.calendars.byName(fields.calendar_id);
    if (!targetCal || !targetCal.exists()) {
      return JSON.stringify({__error__: "CALENDAR_NOT_FOUND"});
    }
    const moved = app.Event({
      summary: fields.title !== null ? fields.title : (evt.summary() || ""),
      startDate: fields.start !== null ? new Date(fields.start) : evt.startDate(),
      endDate: fields.end !== null ? new Date(fields.end) : evt.endDate(),
      location: fields.location !== null ? fields.location : (evt.location ? (evt.location() || "") : ""),
      description: fields.notes !== null ? fields.notes : (evt.description ? (evt.description() || "") : "")
    });
    targetCal.events.push(moved);
    if (fields.all_day !== null) {
      moved.alldayEvent = fields.all_day;
    }
    cal.events.whose({uid: eventId})[0].delete();
    return JSON.stringify(eventRecord(targetCal, moved));
  }

  if (fields.title !== null) { evt.summary = fields.title; }

  // Calendar.app validates every single assignment, so the write order matters
  // whenever both boundaries move. Writing the new start first while the old
  // end is still in place yields start > end when the event is pushed later in
  // the day, and Calendar rejects it with -10025 ("start date must be before
  // end date"). Assign whichever boundary keeps the intermediate state valid.
  const newStart = fields.start !== null ? new Date(fields.start) : null;
  const newEnd = fields.end !== null ? new Date(fields.end) : null;
  if (newStart !== null && newEnd !== null && newStart >= evt.endDate()) {
    // Moving later: widen the end first, then pull the start up behind it.
    evt.endDate = newEnd;
    evt.startDate = newStart;
  } else {
    // Moving earlier or overlapping: start first is always valid here, because
    // the new start stays before the old end.
    if (newStart !== null) { evt.startDate = newStart; }
    if (newEnd !== null) { evt.endDate = newEnd; }
  }

  if (fields.location !== null) { evt.location = fields.location; }
  if (fields.notes !== null) { evt.description = fields.notes; }
  if (fields.all_day !== null) { evt.alldayEvent = fields.all_day; }
  return JSON.stringify(eventRecord(cal, evt));
}
"""
        return self._run_jxa_event(script, event_id, json.dumps(fields))

    def _fallback_delete_event(self, event_id: str) -> dict[str, object]:
        script = self._JXA_FIND_EVENT + """
function run(argv) {
  const app = Application("Calendar");
  const found = findEventByUid(app, argv[0], "");
  if (!found) {
    return JSON.stringify({__error__: "EVENT_NOT_FOUND"});
  }
  found.event.delete();
  return JSON.stringify({deleted: true});
}
"""
        return self._run_jxa_event(script, event_id)

    def _run_jxa_event(self, script: str, *args: str) -> dict[str, object]:
        payload = self._run_jxa(script, *args, timeout=self._JXA_TIMEOUT_SECONDS)
        error_code = payload.get("__error__")
        if error_code:
            raise CalendarBridgeError(
                str(error_code),
                f"No matching calendar item found via the AppleScript fallback (id/name '{args[0] if args else ''}').",
                "List calendars or events first to discover a valid current id.",
            )
        return payload

    def _fallback_events_payload(self, start_iso: str, end_iso: str, calendar_id: str | None = None, limit: int = 100) -> dict[str, object]:
        if calendar_id:
            return self._fallback_list_events(start_iso, end_iso, calendar_id=calendar_id, limit=limit)
        return self._fallback_list_events_across_calendars(start_iso, end_iso, limit=limit)

    def _fallback_list_events_across_calendars(self, start_iso: str, end_iso: str, limit: int = 100) -> dict[str, object]:
        seen_calendar_ids: set[str] = set()
        items: list[dict[str, object]] = []
        for calendar in self.list_calendars():
            calendar_key = calendar.calendar_id or calendar.name
            if not calendar_key or calendar_key in seen_calendar_ids:
                continue
            seen_calendar_ids.add(calendar_key)
            remaining = limit - len(items)
            if remaining <= 0:
                break
            try:
                payload = self._fallback_list_events(start_iso, end_iso, calendar_id=calendar_key, limit=remaining)
            except CalendarBridgeError as exc:
                if exc.error_code in {"APPLESCRIPT_FALLBACK_FAILED", "APPLESCRIPT_FALLBACK_TIMEOUT"}:
                    continue
                raise
            items.extend(self._dedupe_event_items(payload.get("items", []), limit=remaining))
        items.sort(key=lambda item: (str(item.get("start", "")), str(item.get("title", ""))))
        return {"items": self._dedupe_event_items(items, limit=limit)}

    def _dedupe_event_items(self, items: object, *, limit: int | None = None) -> list[dict[str, object]]:
        dedupe_keys: set[tuple[str, str, str, str, str]] = set()
        unique_items: list[dict[str, object]] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            dedupe_key = (
                str(item.get("event_id", "")),
                str(item.get("calendar_id", "")),
                str(item.get("start", "")),
                str(item.get("end", "")),
                str(item.get("title", "")),
            )
            if dedupe_key in dedupe_keys:
                continue
            dedupe_keys.add(dedupe_key)
            unique_items.append(item)
            if limit is not None and len(unique_items) >= limit:
                break
        return unique_items

    def _run_jxa(self, script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        try:
            completed = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script, *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CalendarBridgeError(
                "APPLESCRIPT_FALLBACK_TIMEOUT",
                "Calendar AppleScript fallback timed out.",
                "Retry the request with a narrower calendar scope.",
            ) from exc
        except OSError as exc:
            raise CalendarBridgeError(
                "OSASCRIPT_UNAVAILABLE",
                f"Could not run 'osascript': {exc}.",
                "This server requires macOS with osascript available.",
            ) from exc
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
