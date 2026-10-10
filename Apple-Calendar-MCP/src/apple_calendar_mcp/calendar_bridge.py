import json
import os
import plistlib
import subprocess
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from apple_calendar_mcp.alarm_validation import validate_alarms
from apple_calendar_mcp.models import CalendarInfo, EventDetail, EventSummary
from apple_mcp_common.native import NativeHelperError, ensure_swift_helper, swift_helper_path


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
        self._helper_base_binary = helper_binary

    def helper_available(self) -> tuple[bool, bool]:
        source_available = self.helper_source.exists()
        return source_available, source_available and swift_helper_path(self.helper_source, self._helper_base_binary).is_file()

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

    @staticmethod
    def _is_jxa_token(event_id: str) -> bool:
        return event_id.startswith("applescript::v2::%7B")

    @staticmethod
    def _jxa_lookup_corresponds(requested: str, returned: str) -> bool:
        prefix = "applescript::v2::"
        try:
            result = json.loads(unquote(returned[len(prefix):])) if returned.startswith(prefix) else None
            if not isinstance(result, dict) or result.get("v") != 2 or result.get("kind") not in {"uid", "id"}:
                return False
            aliases = (result.get("uid"), result.get("id"))
            if not requested.startswith(prefix):
                return any(value is not None and str(value) == requested for value in aliases)
            query = json.loads(unquote(requested[len(prefix):]))
            if not isinstance(query, dict) or query.get("v") != 2 or query.get("kind") not in {"uid", "id"}:
                return False
            expected = query.get("value")
            actual = result.get(query["kind"])
            if type(expected) is not type(actual) or expected != actual:
                return False
            scope = query.get("calendar")
            return scope == result.get("calendar") or (
                isinstance(scope, dict) and scope.get("kind") == "name"
                and scope.get("value") == result.get("calendar_name")
            )
        except (ValueError, TypeError, AttributeError):
            return False

    def get_event(self, event_id: str) -> EventDetail:
        if self._is_jxa_token(event_id):
            return self._normalize_detail(self._fallback_get_event(event_id), identifier_provider="jxa")
        provider = None
        try:
            payload = self._run_helper("get-calendar-event", event_id)
        except CalendarBridgeError as exc:
            if not self._should_use_fallback(exc):
                raise
            payload = self._fallback_get_event(event_id)
            provider = "jxa"
        return self._normalize_detail(payload, identifier_provider=provider)

    _MAX_BATCH_IDS = 10000
    _MAX_BATCH_PAYLOAD_BYTES = 32768

    def get_events(self, event_ids: Sequence[str]) -> dict[str, EventDetail | None]:
        """Resolve bounded batches without turning unanswered IDs into absence.

        None means a valid explicit native miss confirmed by the existing
        single-get fallback path, or a definitive miss on that path for a
        fallback identifier. Missing keys mean unknown. Malformed, duplicate,
        contradictory or unrequested entries stay unknown; canonical aliases
        require independent single-get confirmation.
        All input is validated before any helper call. Each JSON argv payload
        is at most 32768 UTF-8 bytes; at most 10000 input IDs are accepted.
        """
        if isinstance(event_ids, str | bytes | bytearray) or not isinstance(event_ids, Sequence):
            raise CalendarBridgeError("INVALID_INPUT", "event_ids must be a sequence of non-empty strings.", None)
        if len(event_ids) > self._MAX_BATCH_IDS:
            raise CalendarBridgeError("INVALID_INPUT", "At most 10000 event IDs may be requested.", None)

        ids: list[str] = []
        seen: set[str] = set()
        for event_id in event_ids:
            if not isinstance(event_id, str) or not event_id.strip():
                raise CalendarBridgeError("INVALID_INPUT", "Each event ID must be a non-empty string.", None)
            if len(json.dumps({"event_ids": [event_id]}).encode("utf-8")) > self._MAX_BATCH_PAYLOAD_BYTES:
                raise CalendarBridgeError("INVALID_INPUT", "An event ID exceeds the 32768-byte batch payload budget.", None)
            if event_id not in seen:
                seen.add(event_id)
                ids.append(event_id)
        if not ids:
            return {}

        fallback_ids = [event_id for event_id in ids if event_id.startswith("applescript::")]
        fallback_set = set(fallback_ids)
        # Legacy uid: identifiers have no supported resolver in current main.
        # Keep them unknown instead of manufacturing a definitive miss.
        native_ids = [event_id for event_id in ids if event_id not in fallback_set and not event_id.startswith("uid:")]
        chunks: list[list[str]] = []
        chunk: list[str] = []
        chunk_bytes = len(json.dumps({"event_ids": []}).encode("utf-8"))
        for event_id in native_ids:
            additional = len(json.dumps(event_id).encode("utf-8")) + (2 if chunk else 0)
            if chunk and chunk_bytes + additional > self._MAX_BATCH_PAYLOAD_BYTES:
                chunks.append(chunk)
                chunk = []
                chunk_bytes = len(json.dumps({"event_ids": []}).encode("utf-8"))
                additional = len(json.dumps(event_id).encode("utf-8"))
            chunk.append(event_id)
            chunk_bytes += additional
        if chunk:
            chunks.append(chunk)

        resolved: dict[str, EventDetail | None] = {}
        self._resolve_batch_individually(fallback_ids, resolved)
        for requested in chunks:
            try:
                payload = self._run_helper("get-calendar-events", json.dumps({"event_ids": requested}))
            except CalendarBridgeError as exc:
                if not self._should_use_read_fallback(exc):
                    raise
                self._resolve_batch_individually(requested, resolved, allow_missing=False)
                continue
            candidates = self._validated_batch_entries(payload, set(requested))
            for event_id, event in candidates.items():
                if event is None:
                    # Native absence cannot distinguish a stale EventKit ID
                    # from a live UID previously supplied by JXA.
                    self._resolve_batch_individually([event_id], resolved)
                elif event.event_id == event_id:
                    resolved[event_id] = event
                else:
                    self._confirm_batch_alias(event_id, event.event_id, resolved)
        return {event_id: resolved[event_id] for event_id in ids if event_id in resolved}

    def _resolve_batch_individually(
        self, event_ids: Sequence[str], resolved: dict[str, EventDetail | None],
        *, allow_missing: bool = True,
    ) -> None:
        for event_id in event_ids:
            try:
                event = self.get_event(event_id)
            except CalendarBridgeError as exc:
                if allow_missing and exc.error_code == "EVENT_NOT_FOUND" and (
                    not event_id.startswith("applescript::") or self._is_jxa_token(event_id)
                ):
                    resolved[event_id] = None
                # Permission, transport, or other lookup failures are unknown.
                continue
            except ValueError:
                continue
            # Only our verified JXA lookup may confirm a backend-specific alias;
            # arbitrary helper records cannot claim a differently scoped identity.
            if event.event_id == event_id or (
                event._identifier_provider == "jxa" and self._jxa_lookup_corresponds(event_id, event.event_id)
            ):
                resolved[event_id] = event

    def _confirm_batch_alias(
        self, requested_id: str, canonical_id: str, resolved: dict[str, EventDetail | None],
    ) -> None:
        # A batch's canonical ID may differ from the lookup ID. Confirm their
        # association through a separate lookup; a conflicting miss is unknown.
        try:
            event = self.get_event(requested_id)
        except (CalendarBridgeError, ValueError):
            return
        if event.event_id == canonical_id:
            resolved[requested_id] = event

    def _validated_batch_entries(
        self, payload: object, requested: set[str],
    ) -> dict[str, EventDetail | None]:
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return {}
        candidates: dict[str, EventDetail | None] = {}
        seen: set[str] = set()
        duplicated: set[str] = set()
        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            event_id = item.get("event_id")
            if not isinstance(event_id, str) or event_id not in requested:
                continue
            if event_id in seen:
                duplicated.add(event_id)
                candidates.pop(event_id, None)
                continue
            seen.add(event_id)
            if item.get("found") is True and item.get("error_code") is None:
                raw = item.get("event")
                if not isinstance(raw, dict):
                    continue
                canonical_id = raw.get("event_id")
                if not isinstance(canonical_id, str) or not canonical_id.strip():
                    continue
                try:
                    EventDetail.model_validate(raw, strict=True)
                    candidates[event_id] = self._normalize_detail(raw)
                except ValueError:
                    continue
            elif (
                item.get("found") is False
                and item.get("error_code") == "EVENT_NOT_FOUND"
                and item.get("event") is None
            ):
                candidates[event_id] = None
        for event_id in duplicated:
            candidates.pop(event_id, None)
        return candidates

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
        alarms: list[dict[str, object]] | None = None,
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
        alarms = validate_alarms(alarms)
        if alarms is not None:
            request["alarms"] = alarms
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
                alarms=alarms,
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
        alarms: list[dict[str, object]] | None = None,
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
        alarms = validate_alarms(alarms)
        if alarms is not None:
            request["alarms"] = alarms
        if self._is_jxa_token(event_id):
            if recurrence is not None:
                raise CalendarBridgeError("UNSUPPORTED_OPERATION", "Automation cannot apply recurrence.", None)
            return self._normalize_detail(self._fallback_update_event(
                event_id, title=title, calendar_id=calendar_id, start_iso=start_iso, end_iso=end_iso,
                notes=notes, location=location, all_day=all_day, alarms=alarms,
            ))
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
                alarms=alarms,
            )
        return self._normalize_detail(payload)

    def delete_event(self, event_id: str) -> bool:
        if self._is_jxa_token(event_id):
            return bool(self._fallback_delete_event(event_id).get("deleted", False))
        try:
            payload = self._run_helper("delete-calendar-event", event_id)
        except CalendarBridgeError as exc:
            if not self._should_use_fallback(exc):
                raise
            payload = self._fallback_delete_event(event_id)
        return bool(payload.get("deleted", False))

    def _run_helper(self, command: str, *args: str) -> dict[str, object]:
        helper_binary = self._ensure_helper()
        try:
            completed = subprocess.run(
                [str(helper_binary), command, *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise CalendarBridgeError(
                "HELPER_UNAVAILABLE",
                f"Could not run the native helper '{helper_binary}': {exc}.",
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

    def _ensure_helper(self) -> Path:
        if not self.helper_source.exists():
            raise CalendarBridgeError(
                "HELPER_SOURCE_MISSING",
                f"Missing native helper source at '{self.helper_source}'.",
                "Restore the shared Swift helper and retry.",
            )
        try:
            helper_binary = ensure_swift_helper(self.helper_source, self._helper_base_binary)
        except NativeHelperError as exc:
            raise CalendarBridgeError(exc.error_code, str(exc), exc.suggestion or "Confirm Xcode command line tools and Swift are available, then retry.") from exc
        info_plist = helper_binary.parent.parent / "Info.plist"
        self._write_bundle_info_plist(info_plist)
        self.helper_binary = helper_binary
        return helper_binary

    def _bundle_info_plist_path(self) -> Path:
        return self.helper_binary.parent.parent / "Info.plist"

    def _write_bundle_info_plist(self, plist_path: Path) -> None:
        # A bare CLI Mach-O has no CFBundleIdentifier, so when EventKit needs a real (non-cached)
        # resync it can't attribute the request to us and routes it through Calendar.app instead --
        # which brings Calendar.app to the foreground to service it. Giving the helper real bundle
        # identity (this Info.plist, with LSUIElement so it never wants foreground/dock presence)
        # stops macOS from needing to borrow Calendar.app's identity, so a background poll no
        # longer steals focus from whatever the user is doing.
        plist_data: dict[str, object] = {
            "CFBundleIdentifier": "io.github.jonathanrreed.apple-mcps.calendar-pim-bridge",
            "CFBundleName": self.helper_binary.name,
            "CFBundleExecutable": self.helper_binary.name,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1",
            "LSUIElement": True,
            "LSBackgroundOnly": True,
            "NSCalendarsUsageDescription": "Reads and writes Calendar events for the Apple Calendar MCP server.",
            "NSCalendarsFullAccessUsageDescription": "Reads and writes Calendar events for the Apple Calendar MCP server.",
            "NSRemindersUsageDescription": "Reads and writes Reminders for the Apple Calendar MCP server.",
            "NSRemindersFullAccessUsageDescription": "Reads and writes Reminders for the Apple Calendar MCP server.",
        }
        descriptor, name = tempfile.mkstemp(prefix=".Info.", dir=plist_path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                plistlib.dump(plist_data, stream)
            temporary.replace(plist_path)
        finally:
            temporary.unlink(missing_ok=True)

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
        script = self._JXA_ID_HELPERS + self._JXA_ALARM_HELPERS + """
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
    const events = cal.events.whose({
      startDate: {
        _greaterThan: start,
        _lessThan: end
      }
    })();

    events.forEach(function(evt, eventIndex) {
      const startDate = evt.startDate();
      const endDate = evt.endDate();
      const title = evt.summary() || "";
      const eventId = eventIdentifier(cal, evt, eventIndex);
      items.push({
        event_id: eventId,
        title: title,
        calendar_id: calendarName,
        calendar_name: calendarName,
        start: startDate.toISOString(),
        end: endDate.toISOString(),
        all_day: isAllDay(startDate, endDate),
        location: evt.location ? (evt.location() || null) : null,
        alarms: eventAlarms(evt)
      });
    });
  });

  // Duplicate provider identities are display-only. Retain every row instead
  // of collapsing twins, but do not hand out an actionable ambiguous token.
  const counts = Object.create(null);
  items.forEach(function(item) { counts[item.event_id] = (counts[item.event_id] || 0) + 1; });
  items.forEach(function(item, row) {
    if (counts[item.event_id] <= 1) { return; }
    const token = decodeEventIdentifier(item.event_id);
    token.kind = "weak";
    token.value = null;
    token.row = row;
    token.start = item.start;
    token.end = item.end;
    token.title = item.title;
    item.event_id = "applescript::v2::" + encodeURIComponent(JSON.stringify(token));
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

    # Fallback IDs name their backend, calendar scope, and UID/id namespace.
    # Legacy bare IDs are resolved only when their meanings agree; metadata-only
    # composites are read-only and cannot safely identify a mutation target.
    _JXA_ALARM_HELPERS = """
function readAlarmCollection(evt, kind) {
  // JXA's object-specifier proxy can stall on computed collection access.
  // Use the scripting dictionary's concrete accessors for nested alarms.
  switch (kind) {
    case "displayAlarms": return evt.displayAlarms();
    case "soundAlarms": return evt.soundAlarms();
    case "mailAlarms": return evt.mailAlarms();
    case "openFileAlarms": return evt.openFileAlarms();
  }
  throw new Error("UNSUPPORTED_ALARM_TYPE");
}
function eventAlarms(evt) {
  try {
    const alarms = [];
    ["displayAlarms", "soundAlarms", "mailAlarms", "openFileAlarms"].forEach(function(kind) {
      readAlarmCollection(evt, kind).forEach(function(alarm) {
        const absolute = alarm.triggerDate();
        if (absolute instanceof Date && Number.isFinite(absolute.getTime())) {
          alarms.push({type: "absolute", absolute: absolute.toISOString()});
        } else {
          const offset = alarm.triggerInterval();
          alarms.push({type: "relative", offset_minutes: Number.isSafeInteger(offset) ? offset : null});
        }
      });
    });
    return alarms;
  } catch (error) {
    // Older Calendar scripting dictionaries cannot expose every alarm type.
    return null;
  }
}
function prepareAlarmUpdate(app, evt, alarms) {
  if (alarms === null) { return null; }
  // Existing alarms cannot be removed reliably through Calendar automation on
  // supported host configurations. Refuse before changing any event fields.
  try {
    const kinds = ["displayAlarms", "soundAlarms", "mailAlarms", "openFileAlarms"];
    for (let index = 0; index < kinds.length; index++) {
      const existing = readAlarmCollection(evt, kinds[index]);
      if (!Array.isArray(existing) || existing.length > 0) {
        return {error: "ALARM_EDIT_REQUIRES_NATIVE"};
      }
    }
  } catch (_) {
    return {error: "ALARM_EDIT_REQUIRES_NATIVE"};
  }
  const replacements = alarms.map(function(alarm) {
    return alarm.minutes_before !== undefined
      ? {triggerInterval: -alarm.minutes_before}
      : {triggerDate: new Date(alarm.absolute_iso)};
  });
  return {app: app, replacements: replacements};
}
function applyAlarmUpdate(evt, update) {
  if (update === null) { return; }
  try {
    update.replacements.forEach(function(properties) { evt.displayAlarms.push(update.app.DisplayAlarm(properties)); });
  } catch (error) {
    try {
      ["displayAlarms", "soundAlarms", "mailAlarms"].forEach(function(kind) {
        readAlarmCollection(evt, kind).reverse().forEach(function(alarm) { alarm.delete(); });
      });
    } catch (restoreError) {
      throw new Error("ALARM_RESTORE_FAILED: " + String(error) + "; restore: " + String(restoreError));
    }
    throw error;
  }
}

"""

    _JXA_ID_HELPERS = """
function readIdentifier(obj, field) {
  try { return typeof obj[field] === "function" ? obj[field]() : null; }
  catch (_) { return null; }
}
function usableId(value) {
  return (typeof value === "string" && value.trim().length > 0) ||
    (typeof value === "number" && Number.isSafeInteger(value));
}
function sameId(left, right) { return typeof left === typeof right && left === right; }
function calendarSelector(cal) {
  const id = readIdentifier(cal, "id");
  return usableId(id) ? {kind: "id", value: id} : {kind: "name", value: cal.name()};
}
function eventIdentifier(cal, evt, row) {
  const uid = readIdentifier(evt, "uid");
  const id = readIdentifier(evt, "id");
  const strongUid = typeof uid === "string" && uid.length > 0;
  const payload = {
    v: 2, calendar: calendarSelector(cal), calendar_name: cal.name(),
    kind: strongUid ? "uid" : (usableId(id) ? "id" : "weak"),
    value: strongUid ? uid : (usableId(id) ? id : null),
    uid: strongUid ? uid : null, id: usableId(id) ? id : null
  };
  if (payload.kind === "weak") {
    payload.row = row === undefined ? null : row;
    payload.start = evt.startDate().toISOString();
    payload.end = evt.endDate().toISOString();
    payload.title = evt.summary() || "";
  }
  return "applescript::v2::" + encodeURIComponent(JSON.stringify(payload));
}
function decodeEventIdentifier(value) {
  const prefix = "applescript::v2::";
  if (value.indexOf(prefix + "%7B") !== 0) { return null; }
  const payload = JSON.parse(decodeURIComponent(value.slice(prefix.length)));
  if (!payload || payload.v !== 2 || !payload.calendar ||
      ["id", "name"].indexOf(payload.calendar.kind) < 0 ||
      !usableId(payload.calendar.value) ||
      (payload.calendar.kind === "name" && typeof payload.calendar.value !== "string") ||
      ["uid", "id", "weak"].indexOf(payload.kind) < 0) {
    throw new Error("INVALID_EVENT_IDENTIFIER");
  }
  if ((payload.kind !== "weak" && !usableId(payload.value)) ||
      (payload.kind === "uid" && typeof payload.value !== "string")) {
    throw new Error("INVALID_EVENT_IDENTIFIER");
  }
  return payload;
}
function sameCandidate(left, right) {
  if (left.index !== right.index) { return false; }
  const leftId = readIdentifier(left.event, "id");
  const rightId = readIdentifier(right.event, "id");
  if (usableId(leftId) && usableId(rightId)) {
    return sameId(leftId, rightId) &&
      readIdentifier(left.event, "uid") === readIdentifier(right.event, "uid");
  }
  const leftUid = readIdentifier(left.event, "uid");
  const rightUid = readIdentifier(right.event, "uid");
  return typeof leftUid === "string" && leftUid.length > 0 && leftUid === rightUid;
}
function uniqueCandidates(items) {
  const unique = [];
  items.forEach(function(item) {
    if (!unique.some(function(prior) { return sameCandidate(prior, item); })) { unique.push(item); }
  });
  if (unique.length > 1) { throw new Error("AMBIGUOUS_EVENT_IDENTIFIER"); }
  return unique[0] || null;
}
function identifierMatches(calendars, field, value, strict) {
  const items = [];
  calendars.forEach(function(entry) {
    const query = {};
    query[field] = value;
    const matches = entry.calendar.events.whose(query)();
    if (matches.length > 1000) { throw new Error("IDENTIFIER_LOOKUP_LIMIT"); }
    let verified = 0;
    matches.forEach(function(evt) {
      const actual = readIdentifier(evt, field);
      if (!sameId(actual, value)) {
        if (strict) { throw new Error("UNVERIFIABLE_EVENT_IDENTIFIER"); }
        return;
      }
      verified += 1;
      if (verified > 1) { throw new Error("AMBIGUOUS_EVENT_IDENTIFIER"); }
      items.push({calendar: entry.calendar, event: evt, index: entry.index});
    });
  });
  return items;
}
"""

    _JXA_FIND_EVENT = _JXA_ID_HELPERS + _JXA_ALARM_HELPERS + """
function findEventByUid(app, identifier, calendarNameHint, requireStable) {
  if (identifier.length > 32768) { throw new Error("IDENTIFIER_LOOKUP_LIMIT"); }
  const snapshot = app.calendars();
  if (snapshot.length > 1000) { throw new Error("IDENTIFIER_LOOKUP_LIMIT"); }
  const calendars = snapshot.map(function(cal, index) { return {calendar: cal, index: index}; });
  const token = decodeEventIdentifier(identifier);
  if (token) {
    if (token.kind === "weak") { throw new Error("UNSUPPORTED_EVENT_IDENTIFIER"); }
    const scoped = calendars.filter(function(entry) {
      const actual = token.calendar.kind === "id"
        ? readIdentifier(entry.calendar, "id") : entry.calendar.name();
      return sameId(actual, token.calendar.value);
    });
    if (scoped.length !== 1) { throw new Error("AMBIGUOUS_OR_MISSING_CALENDAR"); }
    if (requireStable && token.calendar_name !== scoped[0].calendar.name()) {
      throw new Error("STALE_CALENDAR_IDENTIFIER");
    }
    const found = uniqueCandidates(identifierMatches(scoped, token.kind, token.value, true));
    // Legacy UID data can resemble the new protocol. Refuse conflicting meanings.
    const legacy = uniqueCandidates(identifierMatches(calendars, "uid", identifier, true));
    if (legacy && (!found || !sameCandidate(legacy, found))) {
      throw new Error("AMBIGUOUS_EVENT_IDENTIFIER");
    }
    return found;
  }
  const scoped = calendarNameHint
    ? calendars.filter(function(entry) { return entry.calendar.name() === calendarNameHint; })
    : calendars;
  const uidMatches = identifierMatches(scoped, "uid", identifier, true);
  const idValues = [identifier];
  const numeric = Number(identifier);
  if (Number.isSafeInteger(numeric) && String(numeric) === identifier) { idValues.push(numeric); }
  let unavailable = false;
  let candidates = uidMatches.slice();
  idValues.forEach(function(value) {
    try { candidates = candidates.concat(identifierMatches(scoped, "id", value, true)); }
    catch (error) {
      if (/AMBIGUOUS|UNVERIFIABLE|LOOKUP_LIMIT/.test(String(error))) { throw error; }
      unavailable = true;
    }
  });
  const strong = uniqueCandidates(candidates);
  if (unavailable) { throw new Error("UNSUPPORTED_IDENTIFIER_NAMESPACE"); }
  if (strong) { return strong; }
  if (identifier.indexOf("applescript::") === 0) {
    if (requireStable) { throw new Error("UNSUPPORTED_WEAK_EVENT_IDENTIFIER"); }
    const parts = identifier.split("::");
    const calName = parts[1];
    const start = new Date(parts[2]);
    const title = parts.slice(3).join("::");
    if (!Number.isFinite(start.getTime())) { throw new Error("INVALID_EVENT_IDENTIFIER"); }
    const found = [];
    calendars.filter(function(entry) { return entry.calendar.name() === calName; }).forEach(function(entry) {
      const matches = entry.calendar.events.whose({summary: title, startDate: start})();
      if (matches.length > 1000) { throw new Error("IDENTIFIER_LOOKUP_LIMIT"); }
      matches.forEach(function(evt) {
        if (evt.summary() !== title || evt.startDate().getTime() !== start.getTime()) {
          throw new Error("UNVERIFIABLE_EVENT_IDENTIFIER");
        }
        found.push({calendar: entry.calendar, event: evt, index: entry.index});
      });
    });
    // Weak identities cannot establish physical equality for duplicate matches.
    if (found.length > 1) { throw new Error("AMBIGUOUS_EVENT_IDENTIFIER"); }
    return found[0] || null;
  }
  return null;
}

function eventRecord(cal, evt) {
  const startDate = evt.startDate();
  const endDate = evt.endDate();
  return {
    event_id: eventIdentifier(cal, evt),
    title: evt.summary() || "",
    calendar_id: cal.name(),
    calendar_name: cal.name(),
    start: startDate.toISOString(),
    end: endDate.toISOString(),
    all_day: startDate.getHours() === 0 && startDate.getMinutes() === 0 &&
      endDate.getHours() === 23 && endDate.getMinutes() === 59,
    location: evt.location ? (evt.location() || null) : null,
    notes: evt.description ? (evt.description() || null) : null,
    alarms: eventAlarms(evt)
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
        alarms: list[dict[str, object]] | None = None,
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
  try {
    if (argv[6] === "true") { newEvent.alldayEvent = true; }
    const alarmUpdate = prepareAlarmUpdate(app, newEvent, JSON.parse(argv[7]));
    if (alarmUpdate !== null && alarmUpdate.error) {
      throw new Error(alarmUpdate.error);
    }
    applyAlarmUpdate(newEvent, alarmUpdate);
    return JSON.stringify(eventRecord(cal, newEvent));
  } catch (error) {
    // Only this newly created event belongs to the failed creation attempt.
    // Never remove inherited/default alerts individually during cleanup.
    try { newEvent.delete(); }
    catch (cleanupError) {
      throw new Error("EVENT_CREATE_CLEANUP_FAILED: " + String(error) + "; cleanup: " + String(cleanupError));
    }
    if (error.message === "ALARM_EDIT_REQUIRES_NATIVE") {
      return JSON.stringify({__error__: "ALARM_EDIT_REQUIRES_NATIVE"});
    }
    throw error;
  }
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
            json.dumps(alarms),
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
        alarms: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        fields = {
            "title": title,
            "calendar_id": calendar_id,
            "start": start_iso,
            "end": end_iso,
            "notes": notes,
            "location": location,
            "all_day": all_day,
            "alarms": alarms,
        }
        script = self._JXA_FIND_EVENT + """
function run(argv) {
  const app = Application("Calendar");
  const eventId = argv[0];
  const fields = JSON.parse(argv[1]);
  const found = findEventByUid(app, eventId, "", true);
  if (!found) {
    return JSON.stringify({__error__: "EVENT_NOT_FOUND"});
  }
  let cal = found.calendar;
  let evt = found.event;

  const wantsMove = fields.calendar_id && fields.calendar_id !== cal.name();
  if (wantsMove) {
    return JSON.stringify({__error__: "UNSUPPORTED_OPERATION"});
  }


  // Calendar.app validates every single assignment, so the write order matters
  // whenever both boundaries move. Writing the new start first while the old
  // end is still in place yields start > end when the event is pushed later in
  // the day, and Calendar rejects it with -10025 ("start date must be before
  // end date"). Assign whichever boundary keeps the intermediate state valid.
  const newStart = fields.start !== null ? new Date(fields.start) : null;
  const newEnd = fields.end !== null ? new Date(fields.end) : null;
  const prospectiveStart = newStart || evt.startDate();
  const prospectiveEnd = newEnd || evt.endDate();
  if (!Number.isFinite(prospectiveStart.getTime()) || !Number.isFinite(prospectiveEnd.getTime()) || prospectiveEnd <= prospectiveStart) {
    return JSON.stringify({__error__: "INVALID_INPUT"});
  }
  const alarmUpdate = prepareAlarmUpdate(app, evt, fields.alarms === undefined ? null : fields.alarms);
  if (alarmUpdate !== null && alarmUpdate.error) {
    return JSON.stringify({__error__: alarmUpdate.error});
  }
  if (fields.title !== null) { evt.summary = fields.title; }

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
  // Complete field writes and fallible record reads before adding initial
  // alarms. A later field error must not leave new alerts on this event.
  const record = eventRecord(cal, evt);
  applyAlarmUpdate(evt, alarmUpdate);
  record.alarms = eventAlarms(evt);
  return JSON.stringify(record);
}
"""
        return self._run_jxa_event(script, event_id, json.dumps(fields))

    def _fallback_delete_event(self, event_id: str) -> dict[str, object]:
        script = self._JXA_FIND_EVENT + """
function run(argv) {
  const app = Application("Calendar");
  const found = findEventByUid(app, argv[0], "", true);
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
        if error_code == "ALARM_EDIT_REQUIRES_NATIVE":
            raise CalendarBridgeError(
                "ALARM_EDIT_REQUIRES_NATIVE",
                "Calendar automation cannot safely replace or clear existing alarms; no event fields were changed.",
                "Use native EventKit access for this alarm edit, or omit alarms to preserve existing alerts.",
            )
        if error_code == "INVALID_INPUT":
            raise CalendarBridgeError("INVALID_INPUT", "The prospective event time window is invalid.", "Use valid dates with end after start; no fallback fields were changed.")
        if error_code == "UNSUPPORTED_OPERATION":
            raise CalendarBridgeError(
                "UNSUPPORTED_OPERATION",
                "Automation cannot safely preserve all event fields during calendar moves.",
                "Use native Calendar access to move this event.",
            )
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

    def _run_jxa(self, script: str, *args: str, timeout: int = _JXA_TIMEOUT_SECONDS) -> dict[str, object]:
        try:
            completed = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script, "--", *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CalendarBridgeError(
                "APPLESCRIPT_FALLBACK_TIMEOUT",
                "Calendar AppleScript fallback timed out.",
                "Use a narrower list window. For event lookup, grant native EventKit full Calendar access, list events again for native identifiers, then retry.",
            ) from exc
        except OSError as exc:
            raise CalendarBridgeError(
                "OSASCRIPT_UNAVAILABLE",
                f"Could not run 'osascript': {exc}.",
                "This server requires macOS with osascript available.",
            ) from exc
        output = completed.stdout.strip()
        if completed.returncode != 0:
            if "EVENT_CREATE_CLEANUP_FAILED" in completed.stderr:
                raise CalendarBridgeError("EVENT_CREATE_CLEANUP_FAILED", "Calendar could not remove the new event after fallback creation failed.", "The creation outcome is unknown. Inspect Calendar.app before retrying.")
            if "ALARM_RESTORE_FAILED" in completed.stderr:
                raise CalendarBridgeError("ALARM_RESTORE_FAILED", "Calendar rejected the alert change and could not remove alerts added during the attempt.", "The alert outcome is unknown. Inspect this event in Calendar.app before retrying.")
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
            alarms=raw_event.get("alarms"),
        )

    def _normalize_detail(
        self, raw_event: dict[str, object], *, identifier_provider: str | None = None,
    ) -> EventDetail:
        summary_dict = self._normalize_summary(raw_event).model_dump()
        summary_dict["notes"] = self._optional_text(raw_event.get("notes"))
        if raw_event.get("recurrence_rule") is not None:
            summary_dict["recurrence_rule"] = raw_event["recurrence_rule"]
        if raw_event.get("attendees") is not None:
            summary_dict["attendees"] = raw_event["attendees"]
        if raw_event.get("alarms") is not None:
            summary_dict["alarms"] = raw_event["alarms"]
        detail = EventDetail.model_validate(summary_dict)
        detail._identifier_provider = identifier_provider
        return detail

    def _optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
