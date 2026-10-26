import CoreFoundation
import Darwin
import EventKit
import Foundation

// BEGIN SHARED HELPER RESPONSIBILITY
// Keep this block identical in apple_pim_bridge.swift and contacts_bridge.swift;
// scripts/check_bridge_sync.sh compares the copies.
//
// macOS privacy (TCC) decides access for the *responsible* process, not for this
// helper. A helper spawned by an MCP server inherits the app that started the
// server (Claude, Terminal, an Electron editor), so that app's grant and its
// Info.plist usage descriptions decide. An app without a Contacts or Reminders
// usage description can never be prompted and never appears in System Settings.
// When the launching app has no grant, the helper re-runs itself with
// responsibility disclaimed, so macOS evaluates this signed helper bundle and its
// own usage descriptions instead. Apps that already have access keep working
// unchanged because the helper only relaunches when access is missing.
let selfResponsibleEnvironmentKey = "APPLE_MCPS_HELPER_SELF_RESPONSIBLE"
var selfResponsibleChild: pid_t = 0

func responsibleProcessID() -> pid_t? {
    typealias ResponsibleFor = @convention(c) (pid_t) -> pid_t
    guard let symbol = dlsym(UnsafeMutableRawPointer(bitPattern: -2), "responsibility_get_pid_responsible_for_pid") else {
        return nil
    }
    let pid = unsafeBitCast(symbol, to: ResponsibleFor.self)(getpid())
    return pid > 0 ? pid : nil
}

/// True when macOS attributes privacy requests to this helper itself.
func helperIsSelfResponsible() -> Bool {
    guard let responsible = responsibleProcessID() else {
        return getenv(selfResponsibleEnvironmentKey) != nil
    }
    return responsible == getpid()
}

func helperDisplayName() -> String {
    let info = Bundle.main.infoDictionary ?? [:]
    return (info["CFBundleDisplayName"] as? String) ?? (info["CFBundleName"] as? String) ?? ProcessInfo.processInfo.processName
}

func helperBundleIdentifier() -> String {
    Bundle.main.bundleIdentifier ?? ProcessInfo.processInfo.processName
}

/// The name System Settings shows for the app macOS holds responsible, for messages.
func responsibleAppName() -> String {
    if helperIsSelfResponsible() {
        return helperDisplayName()
    }
    guard let pid = responsibleProcessID() else {
        return "the app that started this MCP server"
    }
    var buffer = [CChar](repeating: 0, count: 4096)
    guard proc_pidpath(pid, &buffer, UInt32(buffer.count)) > 0 else {
        return "the app that started this MCP server"
    }
    let path = String(cString: buffer)
    if let range = path.range(of: ".app/", options: .backwards) {
        let bundlePath = String(path[..<range.lowerBound])
        return (bundlePath as NSString).lastPathComponent
    }
    return (path as NSString).lastPathComponent
}

/// Where to grant access, written for a person or an agent relaying it.
func privacyGuidance(pane: String, tccService: String) -> String {
    let helper = helperDisplayName()
    if helperIsSelfResponsible() {
        return "Open System Settings > Privacy & Security > \(pane) and turn on '\(helper)'. "
            + "If '\(helper)' is not listed, run `tccutil reset \(tccService) \(helperBundleIdentifier())` in Terminal, "
            + "then retry this tool and choose Allow in the macOS prompt."
    }
    let host = responsibleAppName()
    return "Open System Settings > Privacy & Security > \(pane) and turn on '\(host)', the app macOS holds responsible for this MCP server. "
        + "If '\(host)' is not listed, it cannot ask for \(pane) access (its Info.plist has no \(pane) usage description) "
        + "and this macOS version did not let the helper ask for itself; start the MCP server from an app that can, then retry."
}

/// Re-runs this helper as its own responsible process and exits with its status.
/// Returns only when that is impossible (already self-responsible, or the
/// private responsibility API is unavailable), so callers fall back to the
/// launching app's permission.
func relaunchAsSelfResponsible() {
    guard getenv(selfResponsibleEnvironmentKey) == nil, !helperIsSelfResponsible() else {
        return
    }
    typealias SetDisclaim = @convention(c) (UnsafeMutablePointer<posix_spawnattr_t?>, Bool) -> Int32
    guard let symbol = dlsym(UnsafeMutableRawPointer(bitPattern: -2), "responsibility_spawnattrs_setdisclaim"),
          let executable = Bundle.main.executablePath ?? CommandLine.arguments.first else {
        return
    }
    var attributes: posix_spawnattr_t?
    guard posix_spawnattr_init(&attributes) == 0 else {
        return
    }
    defer { posix_spawnattr_destroy(&attributes) }
    guard unsafeBitCast(symbol, to: SetDisclaim.self)(&attributes, true) == 0 else {
        return
    }
    var environment = ProcessInfo.processInfo.environment
    environment[selfResponsibleEnvironmentKey] = "1"
    let argv: [UnsafeMutablePointer<CChar>?] = ([executable] + CommandLine.arguments.dropFirst()).map { strdup($0) } + [nil]
    let envp: [UnsafeMutablePointer<CChar>?] = environment.map { strdup("\($0.key)=\($0.value)") } + [nil]
    defer {
        argv.forEach { free($0) }
        envp.forEach { free($0) }
    }
    var child: pid_t = 0
    // The child inherits stdin, stdout and stderr, so callers see its output unchanged.
    guard posix_spawn(&child, executable, nil, &attributes, argv, envp) == 0 else {
        return
    }
    selfResponsibleChild = child
    for signalNumber in [SIGTERM, SIGINT, SIGHUP] {
        signal(signalNumber) { received in
            if selfResponsibleChild > 0 {
                kill(selfResponsibleChild, received)
            }
        }
    }
    var status: Int32 = 0
    while waitpid(child, &status, 0) == -1 {
        if errno != EINTR {
            Foundation.exit(70)
        }
    }
    let terminatingSignal = status & 0x7f
    Foundation.exit(terminatingSignal == 0 ? (status >> 8) & 0xff : 128 + terminatingSignal)
}
// END SHARED HELPER RESPONSIBILITY

struct BridgeFailure: Error {
    let errorCode: String
    let message: String
    let suggestion: String?
}

struct ErrorPayload: Encodable {
    let ok = false
    let error_code: String
    let message: String
    let suggestion: String?
}

struct ReminderListRecord: Encodable {
    let list_id: String
    let title: String
    let source_title: String?
    let allows_content_modifications: Bool
    let color_hex: String?
}

struct ReminderRecord: Encodable {
    let reminder_id: String
    let title: String
    let list_id: String
    let list_name: String
    let notes: String?
    let due_date: String?
    let due_all_day: Bool
    let remind_at: String?
    let priority: Int
    let completed: Bool
    let completion_date: String?
    let creation_date: String?
    let modification_date: String?
    let tags: [String]
    let subtask_ids: [String]
}

struct CalendarRecord: Encodable {
    let calendar_id: String
    let title: String
    let source_title: String?
    let allows_content_modifications: Bool
    let color_hex: String?
}

struct EventRecord: Encodable {
    let event_id: String
    let title: String
    let calendar_id: String
    let calendar_name: String
    let start: String
    let end: String
    let all_day: Bool
    let location: String?
    let notes: String?
    let recurrence_rule: RecurrenceInfo?
    let recurring: Bool
    let attendees: [AttendeeInfo]?
    let alarms: [AlarmInfo]?
}

struct AlarmInfo: Encodable {
    // Relative offsets are signed minutes. Location offsets are raw EventKit
    // values, not a guaranteed travel-time estimate. An unrepresentable offset
    // is omitted rather than trapping while serializing an external alarm.
    let type: String
    let offset_minutes: Int?
    let absolute: String?
    let proximity: String?
    let location_title: String?
}

struct RecurrenceInfo: Encodable {
    let frequency: String
    let interval: Int
    let end_date: String?
}

struct AttendeeInfo: Encodable {
    let name: String?
    let email: String?
    let status: String
}

struct ReminderListMutationPayload: Encodable {
    let list_id: String
    let title: String
    let created: Bool
}

struct BooleanMutationPayload: Encodable {
    let deleted: Bool
    let object_id: String
}

struct EventDeletionPayload: Encodable {
    let deleted: Bool
    let object_id: String
    let scope: String?
    let occurrence_start: String?
}

// Which events of a repeating series a write applies to. EventKit has only
// this-event and future-events spans; `series` is future-events applied from the
// series' first occurrence.
enum EventScope: String {
    case occurrence
    case following
    case series
}

struct ListPayload<T: Encodable>: Encodable {
    let count: Int
    let items: [T]
}

// One entry per requested id in a `get-calendar-events` batch. A batch is a
// convenience over N `get-calendar-event` calls -- the expensive part of this
// binary is process launch plus EKEventStore() setup, paid once per invocation
// rather than per id -- so a missing id must stay a per-entry outcome here
// instead of failing the whole call the way the single-event command does.
struct BatchEventRecord: Encodable {
    let event_id: String
    let found: Bool
    let event: EventRecord?
    let error_code: String?
}

struct AccessStatusPayload: Encodable {
    let ok = true
    let domain: String
    let status: String
    let can_read_events: Bool
    let can_write_events: Bool
    let message: String?
    let suggestion: String?
    // The app macOS checks for this access, and whether that is the helper itself.
    var tcc_client: String = responsibleAppName()
    var helper_is_responsible: Bool = helperIsSelfResponsible()
}

@main
struct ApplePIMBridge {
    static let outputEncoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }()

    static let isoFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withDashSeparatorInDate, .withColonSeparatorInTime, .withColonSeparatorInTimeZone]
        return formatter
    }()

    static let isoFormatterWithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withDashSeparatorInDate, .withColonSeparatorInTime, .withColonSeparatorInTimeZone, .withFractionalSeconds]
        return formatter
    }()

    static let localCalendar = Calendar.current

    static func main() {
        do {
            let arguments = Array(CommandLine.arguments.dropFirst())
            guard let command = arguments.first else {
                throw BridgeFailure(
                    errorCode: "USAGE_ERROR",
                    message: "Missing command.",
                    suggestion: "Pass a supported bridge command."
                )
            }

            let data = try handle(command: command, arguments: Array(arguments.dropFirst()))
            FileHandle.standardOutput.write(data)
        } catch let failure as BridgeFailure {
            writeErrorAndExit(failure)
        } catch {
            writeErrorAndExit(
                BridgeFailure(
                    errorCode: "UNEXPECTED_ERROR",
                    message: String(describing: error),
                    suggestion: "Inspect the helper command and retry."
                )
            )
        }
    }

    static func handle(command: String, arguments: [String]) throws -> Data {
        switch command {
        case "list-reminder-lists":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            let lists = store.calendars(for: .reminder).map(reminderListRecord).sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }
            return try encode(ListPayload(count: lists.count, items: lists))
        case "list-reminders":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            let payload = try decodeObjectArgument(arguments, expectedCount: 1)
            let reminders = try listReminders(store: store, payload: payload)
            return try encode(ListPayload(count: reminders.count, items: reminders))
        case "get-reminder":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            guard arguments.count == 1 else {
                throw usageError(command)
            }
            return try encode(try getReminder(store: store, reminderID: arguments[0]))
        case "create-reminder":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            let payload = try decodeObjectArgument(arguments, expectedCount: 1)
            return try encode(try createReminder(store: store, payload: payload))
        case "update-reminder":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            guard arguments.count == 2 else {
                throw usageError(command)
            }
            let payload = try decodeJSONObject(arguments[1])
            return try encode(try updateReminder(store: store, reminderID: arguments[0], payload: payload))
        case "set-reminder-completed":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            guard arguments.count == 2 else {
                throw usageError(command)
            }
            let completed = try boolArgument(arguments[1], field: "completed")
            return try encode(try setReminderCompleted(store: store, reminderID: arguments[0], completed: completed))
        case "delete-reminder":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            guard arguments.count == 1 else {
                throw usageError(command)
            }
            return try encode(try deleteReminder(store: store, reminderID: arguments[0]))
        case "list-calendar-calendars":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            let calendars = store.calendars(for: .event).map(calendarRecord).sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }
            return try encode(ListPayload(count: calendars.count, items: calendars))
        case "calendar-access-status":
            relaunchIfAccessMissing(.event)
            return try encode(calendarAccessStatus())
        case "reminders-access-status":
            relaunchIfAccessMissing(.reminder)
            return try encode(remindersAccessStatus())
        case "list-calendar-events":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            let payload = try decodeObjectArgument(arguments, expectedCount: 1)
            let events = try listEvents(store: store, payload: payload)
            return try encode(ListPayload(count: events.count, items: events))
        case "get-calendar-event":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            guard arguments.count == 1 else {
                throw usageError(command)
            }
            return try encode(try getEvent(store: store, eventID: arguments[0]))
        case "get-calendar-events":
            guard arguments.count == 1, arguments[0].utf8.count <= 32768 else {
                throw BridgeFailure(errorCode: "INVALID_INPUT", message: "Batch payload must be one JSON argument of at most 32768 bytes.", suggestion: nil)
            }
            let payload = try decodeObjectArgument(arguments, expectedCount: 1)
            guard let eventIDs = payload["event_ids"] as? [String], eventIDs.count <= 10000,
                  eventIDs.allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) else {
                throw BridgeFailure(errorCode: "INVALID_INPUT", message: "event_ids must contain at most 10000 non-empty strings.", suggestion: nil)
            }
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            let records = getEvents(store: store, eventIDs: eventIDs)
            return try encode(ListPayload(count: records.count, items: records))
        case "create-calendar-event":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            let payload = try decodeObjectArgument(arguments, expectedCount: 1)
            return try encode(try createEvent(store: store, payload: payload))
        case "update-calendar-event":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            guard arguments.count == 2 else {
                throw usageError(command)
            }
            let payload = try decodeJSONObject(arguments[1])
            return try encode(try updateEvent(store: store, eventID: arguments[0], payload: payload))
        case "delete-calendar-event":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .event)
            guard arguments.count == 1 || arguments.count == 2 else {
                throw usageError(command)
            }
            let options = arguments.count == 2 ? try decodeJSONObject(arguments[1]) : [:]
            return try encode(try deleteEvent(store: store, eventID: arguments[0], options: options))
        case "create-reminder-list":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            let payload = try decodeObjectArgument(arguments, expectedCount: 1)
            return try encode(try createReminderList(store: store, payload: payload))
        case "delete-reminder-list":
            let store = EKEventStore()
            try ensureAccess(store: store, entityType: .reminder)
            guard arguments.count == 1 else {
                throw usageError(command)
            }
            return try encode(try deleteReminderList(store: store, listID: arguments[0]))
        default:
            throw BridgeFailure(
                errorCode: "UNKNOWN_COMMAND",
                message: "Unknown command '\(command)'.",
                suggestion: "Use a supported bridge command."
            )
        }
    }

    static func listReminders(store: EKEventStore, payload: [String: Any]) throws -> [ReminderRecord] {
        let listID = stringValue(payload, field: "list_id")
        let includeCompleted = payload["include_completed"] as? Bool ?? true
        let limit = min(max(intValue(payload, field: "limit") ?? 100, 1), 500)
        let search = stringValue(payload, field: "search")?.lowercased()
        let dueAfter = try optionalDate(payload, field: "due_after")
        let dueBefore = try optionalDate(payload, field: "due_before")

        let calendars = try reminderCalendars(store: store, listID: listID)
        let fetched = try fetchReminders(store: store, calendars: calendars)

        var filtered = fetched.filter { reminder in
            if !includeCompleted && reminder.isCompleted {
                return false
            }
            if let search, !search.isEmpty {
                let haystacks = [reminder.title.lowercased(), (reminder.notes ?? "").lowercased()]
                if !haystacks.contains(where: { $0.contains(search) }) {
                    return false
                }
            }

            let dueDate = reminder.dueDateComponents?.date
            if let dueAfter {
                guard let dueDate, dueDate >= dueAfter else {
                    return false
                }
            }
            if let dueBefore {
                guard let dueDate, dueDate <= dueBefore else {
                    return false
                }
            }
            return true
        }

        filtered.sort { left, right in
            let leftDate = left.dueDateComponents?.date ?? .distantFuture
            let rightDate = right.dueDateComponents?.date ?? .distantFuture
            if leftDate != rightDate {
                return leftDate < rightDate
            }
            return left.title.localizedCaseInsensitiveCompare(right.title) == .orderedAscending
        }

        return filtered.prefix(limit).map(reminderRecord)
    }

    static func getReminder(store: EKEventStore, reminderID: String) throws -> ReminderRecord {
        let nativeID = nativeReminderIdentifier(reminderID)
        guard let reminder = store.calendarItem(withIdentifier: nativeID) as? EKReminder else {
            throw BridgeFailure(
                errorCode: "REMINDER_NOT_FOUND",
                message: "No reminder matched '\(reminderID)'.",
                suggestion: "List reminders first to discover valid ids."
            )
        }
        return reminderRecord(reminder)
    }

    static func createReminder(store: EKEventStore, payload: [String: Any]) throws -> ReminderRecord {
        let listID = try requiredString(payload, field: "list_id")
        let title = try requiredString(payload, field: "title")
        let calendar = try reminderCalendar(store: store, listID: listID)

        let reminder = EKReminder(eventStore: store)
        reminder.calendar = calendar
        reminder.title = title
        try applyReminderFields(store: store, reminder: reminder, payload: payload, isCreate: true)
        try store.save(reminder, commit: true)
        return reminderRecord(reminder)
    }

    static func updateReminder(store: EKEventStore, reminderID: String, payload: [String: Any]) throws -> ReminderRecord {
        let nativeID = nativeReminderIdentifier(reminderID)
        guard let reminder = store.calendarItem(withIdentifier: nativeID) as? EKReminder else {
            throw BridgeFailure(
                errorCode: "REMINDER_NOT_FOUND",
                message: "No reminder matched '\(reminderID)'.",
                suggestion: "List reminders first to discover valid ids."
            )
        }
        try applyReminderFields(store: store, reminder: reminder, payload: payload, isCreate: false)
        try store.save(reminder, commit: true)
        return reminderRecord(reminder)
    }

    static func setReminderCompleted(store: EKEventStore, reminderID: String, completed: Bool) throws -> ReminderRecord {
        let nativeID = nativeReminderIdentifier(reminderID)
        guard let reminder = store.calendarItem(withIdentifier: nativeID) as? EKReminder else {
            throw BridgeFailure(
                errorCode: "REMINDER_NOT_FOUND",
                message: "No reminder matched '\(reminderID)'.",
                suggestion: "List reminders first to discover valid ids."
            )
        }
        reminder.isCompleted = completed
        try store.save(reminder, commit: true)
        return reminderRecord(reminder)
    }

    static func deleteReminder(store: EKEventStore, reminderID: String) throws -> BooleanMutationPayload {
        let nativeID = nativeReminderIdentifier(reminderID)
        guard let reminder = store.calendarItem(withIdentifier: nativeID) as? EKReminder else {
            return BooleanMutationPayload(deleted: false, object_id: reminderID)
        }
        try store.remove(reminder, commit: true)
        return BooleanMutationPayload(deleted: true, object_id: reminderID)
    }

    static func listEvents(store: EKEventStore, payload: [String: Any]) throws -> [EventRecord] {
        let start = try requiredDate(payload, field: "start")
        let end = try requiredDate(payload, field: "end")
        guard end > start else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "The end date must be later than the start date.",
                suggestion: "Provide a valid time window."
            )
        }

        let calendarID = stringValue(payload, field: "calendar_id")
        let limit = min(max(intValue(payload, field: "limit") ?? 100, 1), 500)
        let calendars = try eventCalendars(store: store, calendarID: calendarID)
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: calendars)
        let events = store.events(matching: predicate)
            .sorted { $0.startDate < $1.startDate }
            .prefix(limit)
            .map(eventRecord)
        return Array(events)
    }

    // Native identifiers first, then Calendar.app UIDs, which EventKit exposes as
    // external identifiers. Earlier releases handed out bare UIDs as event ids
    // under write-only access, so they must keep resolving once full access is
    // granted. A UID shared by several events (detached recurrence occurrences)
    // is reported as ambiguous so the caller can fall back to automation.
    static func resolveEvent(store: EKEventStore, eventID: String) throws -> EKEvent {
        if let event = store.event(withIdentifier: eventID) {
            return event
        }
        if !eventID.hasPrefix("applescript::") {
            var seen = Set<String>()
            let matches = store.calendarItems(withExternalIdentifier: eventID)
                .compactMap { $0 as? EKEvent }
                .filter { seen.insert($0.eventIdentifier ?? $0.calendarItemIdentifier).inserted }
            if matches.count == 1 {
                return matches[0]
            }
            if matches.count > 1 {
                throw BridgeFailure(
                    errorCode: "EVENT_ID_AMBIGUOUS",
                    message: "Calendar UID '\(eventID)' matches \(matches.count) events.",
                    suggestion: "List calendar events and use the returned event_id."
                )
            }
        }
        throw BridgeFailure(
            errorCode: "EVENT_NOT_FOUND",
            message: "No event matched '\(eventID)'.",
            suggestion: "List calendar events first to discover valid ids."
        )
    }

    static func getEvent(store: EKEventStore, eventID: String) throws -> EventRecord {
        let event = try resolveEvent(store: store, eventID: eventID)
        return eventRecord(event)
    }

    // Deliberately non-throwing: one unresolvable id must not discard the
    // lookups that succeeded. Native misses must still be confirmed through
    // the Python bridge's existing single-get/JXA fallback before inferring absence.
    static func getEvents(store: EKEventStore, eventIDs: [String]) -> [BatchEventRecord] {
        eventIDs.map { eventID in
            if eventID.hasPrefix("applescript::") || eventID.hasPrefix("uid:") {
                return BatchEventRecord(event_id: eventID, found: false, event: nil, error_code: "UNSUPPORTED_IDENTIFIER")
            }
            guard let event = store.event(withIdentifier: eventID) else {
                return BatchEventRecord(
                    event_id: eventID,
                    found: false,
                    event: nil,
                    error_code: "EVENT_NOT_FOUND"
                )
            }
            return BatchEventRecord(
                event_id: eventID,
                found: true,
                event: eventRecord(event),
                error_code: nil
            )
        }
    }

    static func createEvent(store: EKEventStore, payload: [String: Any]) throws -> EventRecord {
        let calendarID = try requiredString(payload, field: "calendar_id")
        let title = try requiredString(payload, field: "title")
        let start = try requiredDate(payload, field: "start")
        let end = try requiredDate(payload, field: "end")
        guard end > start else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "The end date must be later than the start date.",
                suggestion: "Provide a valid start and end."
            )
        }

        let calendar = try eventCalendar(store: store, calendarID: calendarID)
        let event = EKEvent(eventStore: store)
        event.calendar = calendar
        event.title = title
        event.startDate = start
        event.endDate = end
        try applyEventFields(store: store, event: event, payload: payload, isCreate: true)
        try store.save(event, span: .thisEvent, commit: true)
        return eventRecord(event)
    }

    static func updateEvent(store: EKEventStore, eventID: String, payload: [String: Any]) throws -> EventRecord {
        let event = try resolveEvent(store: store, eventID: eventID)
        let (target, scope) = try scopedEvent(store: store, event: event, options: payload, action: "updated")
        var fields = payload
        let saveTarget: EKEvent
        if scope == .series {
            let first = try seriesFirstOccurrence(store: store, event: event)
            // Times given for one occurrence move the whole series by the same amount.
            if let start = try optionalDate(payload, field: "start") {
                fields["start"] = isoString(first.startDate.addingTimeInterval(start.timeIntervalSince(target.startDate)))
            }
            if let end = try optionalDate(payload, field: "end") {
                fields["end"] = isoString(first.endDate.addingTimeInterval(end.timeIntervalSince(target.endDate)))
            }
            saveTarget = first
        } else {
            saveTarget = target
        }
        try applyEventFields(store: store, event: saveTarget, payload: fields, isCreate: false)
        guard saveTarget.endDate > saveTarget.startDate else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "The end date must be later than the start date.",
                suggestion: "Provide a valid start and end."
            )
        }
        try store.save(saveTarget, span: span(for: scope), commit: true)
        return eventRecord(saveTarget)
    }

    static func deleteEvent(store: EKEventStore, eventID: String, options: [String: Any]) throws -> EventDeletionPayload {
        let event = try resolveEvent(store: store, eventID: eventID)
        let (target, scope) = try scopedEvent(store: store, event: event, options: options, action: "deleted")
        let occurrenceStart: Date? = scope == .series || scope == nil ? nil : target.startDate
        let removed = scope == .series ? try seriesFirstOccurrence(store: store, event: event) : target
        let calendar: EKCalendar = event.calendar
        let key = seriesKey(event)
        let removedItem = removed.calendarItemIdentifier
        try store.remove(removed, span: span(for: scope), commit: true)
        store.reset()
        // Report what is actually gone: the targeted occurrence, or the whole event or series.
        let survived: Bool
        if let occurrenceStart {
            survived = occurrences(store: store, calendar: calendar, seriesKey: key, start: occurrenceStart)
                .contains { $0.calendarItemIdentifier == removedItem }
        } else if scope == .series {
            survived = !seriesEvents(store: store, calendar: calendar, seriesKey: key).isEmpty
        } else {
            survived = (try? resolveEvent(store: store, eventID: eventID)) != nil
        }
        return EventDeletionPayload(
            deleted: !survived,
            object_id: eventID,
            scope: scope?.rawValue,
            occurrence_start: occurrenceStart.map(isoString)
        )
    }

    static func span(for scope: EventScope?) -> EKSpan {
        switch scope {
        case .following, .series: return .futureEvents
        case .occurrence, nil: return .thisEvent
        }
    }

    // A write to a repeating event must say which occurrences it covers, so a
    // caller cannot change or delete the wrong ones by passing only the series id.
    // Non-repeating events ignore the scope.
    static func scopedEvent(
        store: EKEventStore, event: EKEvent, options: [String: Any], action: String
    ) throws -> (EKEvent, EventScope?) {
        var scope: EventScope? = nil
        if let raw = stringValue(options, field: "scope") {
            guard let parsed = EventScope(rawValue: raw) else {
                throw BridgeFailure(
                    errorCode: "INVALID_INPUT",
                    message: "Unknown scope '\(raw)'.",
                    suggestion: "Use scope 'occurrence', 'following' or 'series'."
                )
            }
            scope = parsed
        }
        guard isInSeries(event) else {
            return (event, nil)
        }
        let title = event.title ?? "This event"
        guard let scope else {
            throw BridgeFailure(
                errorCode: "RECURRING_EVENT_SCOPE_REQUIRED",
                message: "'\(title)' repeats, so nothing was \(action).",
                suggestion: "Ask the user whether they mean one occurrence, that occurrence and all following ones, or the whole series. "
                    + "Then call again with scope 'occurrence', 'following' or 'series', and for 'occurrence' or 'following' "
                    + "pass occurrence_start_iso set to that occurrence's start from calendar_list_events."
            )
        }
        guard let rawStart = stringValue(options, field: "occurrence_start") else {
            // A detached occurrence's own id already names one occurrence.
            if scope == .series || event.isDetached {
                return (event, scope)
            }
            throw BridgeFailure(
                errorCode: "OCCURRENCE_REQUIRED",
                message: "'\(title)' repeats; scope '\(scope.rawValue)' needs the occurrence to start from, so nothing was \(action).",
                suggestion: "Pass occurrence_start_iso set to the occurrence's start from calendar_list_events, or use scope 'series' for every occurrence."
            )
        }
        return (try eventOccurrence(store: store, event: event, start: try parseDate(rawStart)), scope)
    }

    // Calendar.app's UID, shared by a series and its detached occurrences (which
    // get their own calendar item identifiers once edited on their own). Local
    // calendars append "/RID=<recurrence id>" to a detached occurrence's UID.
    static func seriesKey(_ event: EKEvent) -> String {
        guard let external = event.calendarItemExternalIdentifier else {
            return event.calendarItemIdentifier
        }
        return external.components(separatedBy: "/RID=").first ?? external
    }

    static func isInSeries(_ event: EKEvent) -> Bool {
        event.hasRecurrenceRules || event.isDetached
    }

    static func seriesEvents(store: EKEventStore, calendar: EKCalendar, seriesKey: String) -> [EKEvent] {
        store.calendarItems(withExternalIdentifier: seriesKey)
            .compactMap { $0 as? EKEvent }
            .filter { $0.calendar.calendarIdentifier == calendar.calendarIdentifier }
    }

    // The series' own first occurrence, reached even from a detached occurrence,
    // so a series-wide write covers every occurrence rather than starting midway.
    static func seriesFirstOccurrence(store: EKEventStore, event: EKEvent) throws -> EKEvent {
        guard event.isDetached else {
            return event
        }
        let candidates = seriesEvents(store: store, calendar: event.calendar, seriesKey: seriesKey(event))
            .filter { !$0.isDetached }
        guard let first = candidates.min(by: { $0.startDate < $1.startDate }) else {
            throw BridgeFailure(
                errorCode: "EVENT_NOT_FOUND",
                message: "Could not find the series that '\(event.title ?? "this event")' belongs to.",
                suggestion: "List calendar events again and retry with an event_id from the series."
            )
        }
        return first
    }

    // The occurrence of `event`'s series that starts, or originally started, at `start`.
    // An edited occurrence moved onto another occurrence's start matches too, so the
    // event the caller named wins, and a remaining tie is refused rather than guessed.
    static func eventOccurrence(store: EKEventStore, event: EKEvent, start: Date) throws -> EKEvent {
        let matches = occurrences(store: store, calendar: event.calendar, seriesKey: seriesKey(event), start: start)
        let named = matches.filter { $0.calendarItemIdentifier == event.calendarItemIdentifier }
        let candidates = named.isEmpty ? matches : named
        guard candidates.count == 1 else {
            let title = event.title ?? "This event"
            if candidates.isEmpty {
                throw BridgeFailure(
                    errorCode: "OCCURRENCE_NOT_FOUND",
                    message: "'\(title)' has no occurrence starting at \(isoString(start)).",
                    suggestion: "List calendar events and pass that occurrence's start exactly as occurrence_start_iso."
                )
            }
            throw BridgeFailure(
                errorCode: "OCCURRENCE_AMBIGUOUS",
                message: "\(candidates.count) occurrences of '\(title)' start at \(isoString(start)).",
                suggestion: "List calendar events and pass the event_id of the occurrence you mean; an occurrence edited on its own has its own event_id."
            )
        }
        return candidates[0]
    }

    static func occurrences(store: EKEventStore, calendar: EKCalendar, seriesKey: String, start: Date) -> [EKEvent] {
        let window = store.predicateForEvents(
            withStart: start.addingTimeInterval(-86_400),
            end: start.addingTimeInterval(86_400),
            calendars: [calendar]
        )
        let startsAt = { (date: Date?) in date.map { abs($0.timeIntervalSince(start)) < 1 } ?? false }
        return store.events(matching: window).filter { candidate in
            Self.seriesKey(candidate) == seriesKey && (startsAt(candidate.startDate) || startsAt(candidate.occurrenceDate))
        }
    }

    static func applyReminderFields(store: EKEventStore, reminder: EKReminder, payload: [String: Any], isCreate: Bool) throws {
        if isCreate || payload.keys.contains("title") {
            reminder.title = stringValue(payload, field: "title") ?? reminder.title
        }
        if isCreate || payload.keys.contains("notes") {
            reminder.notes = nullableStringValue(payload, field: "notes")
        }
        if isCreate || payload.keys.contains("priority") {
            reminder.priority = intValue(payload, field: "priority") ?? 0
        }
        if payload.keys.contains("list_id"), let listID = stringValue(payload, field: "list_id") {
            reminder.calendar = try reminderCalendar(store: store, listID: listID)
        }
        if payload.keys.contains("due_date") || payload.keys.contains("due_all_day") {
            let dueAllDay = payload["due_all_day"] as? Bool ?? false
            if let rawDueDate = stringValue(payload, field: "due_date") {
                let date = try parseDate(rawDueDate)
                reminder.dueDateComponents = dateComponents(for: date, allDay: dueAllDay)
            } else if payload["due_date"] is NSNull {
                reminder.dueDateComponents = nil
            }
        }
        if payload.keys.contains("remind_at") {
            if let rawReminderDate = stringValue(payload, field: "remind_at") {
                let date = try parseDate(rawReminderDate)
                reminder.alarms = [EKAlarm(absoluteDate: date)]
            } else if payload["remind_at"] is NSNull {
                reminder.alarms = nil
            }
        }
        if payload.keys.contains("completed") {
            reminder.isCompleted = payload["completed"] as? Bool ?? false
        }
    }

    static func applyEventFields(store: EKEventStore, event: EKEvent, payload: [String: Any], isCreate: Bool) throws {
        if isCreate || payload.keys.contains("title") {
            event.title = stringValue(payload, field: "title") ?? event.title
        }
        if isCreate || payload.keys.contains("start") {
            event.startDate = try requiredDate(payload, field: "start")
        }
        if isCreate || payload.keys.contains("end") {
            event.endDate = try requiredDate(payload, field: "end")
        }
        if isCreate || payload.keys.contains("location") {
            event.location = nullableStringValue(payload, field: "location")
        }
        if isCreate || payload.keys.contains("notes") {
            event.notes = nullableStringValue(payload, field: "notes")
        }
        if isCreate || payload.keys.contains("all_day") {
            event.isAllDay = payload["all_day"] as? Bool ?? false
        }
        if payload.keys.contains("calendar_id"), let calendarID = stringValue(payload, field: "calendar_id") {
            event.calendar = try eventCalendar(store: store, calendarID: calendarID)
        }
        if payload.keys.contains("recurrence") {
            if let recurrencePayload = payload["recurrence"] as? [String: Any] {
                let freqString = stringValue(recurrencePayload, field: "frequency") ?? "weekly"
                let interval = intValue(recurrencePayload, field: "interval") ?? 1
                let frequency: EKRecurrenceFrequency
                switch freqString.lowercased() {
                case "daily": frequency = .daily
                case "weekly": frequency = .weekly
                case "monthly": frequency = .monthly
                case "yearly": frequency = .yearly
                default: frequency = .weekly
                }
                var recurrenceEnd: EKRecurrenceEnd? = nil
                if let endDateStr = stringValue(recurrencePayload, field: "end_date") {
                    let endDate = try parseDate(endDateStr)
                    recurrenceEnd = EKRecurrenceEnd(end: endDate)
                }
                let rule = EKRecurrenceRule(
                    recurrenceWith: frequency,
                    interval: interval,
                    end: recurrenceEnd
                )
                event.recurrenceRules = [rule]
            } else if payload["recurrence"] is NSNull {
                event.recurrenceRules = nil
            }
        }
        if let rawAlarms = payload["alarms"] {
            let alarms = try eventAlarms(rawAlarms)
            event.alarms = alarms.isEmpty ? nil : alarms
        }
    }

    static let maxAlarmMinutes = 525600.0
    static let maxEventAlarms = 100

    static func eventAlarms(_ rawAlarms: Any) throws -> [EKAlarm] {
        guard let entries = rawAlarms as? [[String: Any]], entries.count <= maxEventAlarms else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "alarms must be an array of at most 100 objects; use [] to clear.",
                suggestion: "Omit alarms to leave them unchanged."
            )
        }
        return try entries.map { entry in
            guard entry.count == 1 else {
                throw BridgeFailure(errorCode: "INVALID_INPUT", message: "Each alarm requires exactly one supported field.", suggestion: nil)
            }
            if let rawMinutes = entry["minutes_before"] {
                let minutes: Double?
                if let number = rawMinutes as? NSNumber {
                    // JSON booleans bridge to NSNumber; never accept them as offsets.
                    guard CFGetTypeID(number) != CFBooleanGetTypeID() else {
                        throw BridgeFailure(errorCode: "INVALID_INPUT", message: "minutes_before must be a number, not a boolean.", suggestion: nil)
                    }
                    minutes = number.doubleValue
                } else if let text = rawMinutes as? String {
                    minutes = Double(text.trimmingCharacters(in: .whitespacesAndNewlines))
                } else {
                    minutes = nil
                }
                guard let value = minutes, value.isFinite, value >= 0,
                      value <= maxAlarmMinutes, value.rounded(.towardZero) == value else {
                    throw BridgeFailure(
                        errorCode: "INVALID_INPUT",
                        message: "minutes_before must be a whole number from 0 through 525600.",
                        suggestion: nil
                    )
                }
                return EKAlarm(relativeOffset: -value * 60)
            }
            if let rawDate = entry["absolute_iso"] as? String, !rawDate.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return EKAlarm(absoluteDate: try parseDate(rawDate.trimmingCharacters(in: .whitespacesAndNewlines)))
            }
            throw BridgeFailure(errorCode: "INVALID_INPUT", message: "Each alarm requires minutes_before or a non-empty absolute_iso string.", suggestion: nil)
        }
    }

    static func safeAlarmOffsetMinutes(_ seconds: Double) -> Int? {
        let minutes = seconds / 60
        guard minutes.isFinite else { return nil }
        return Int(exactly: minutes.rounded(.towardZero))
    }

    static func reminderListRecord(_ calendar: EKCalendar) -> ReminderListRecord {
        ReminderListRecord(
            list_id: calendar.calendarIdentifier,
            title: calendar.title,
            source_title: calendar.source.title,
            allows_content_modifications: calendar.allowsContentModifications,
            color_hex: calendar.cgColor?.hexString
        )
    }

    static func reminderRecord(_ reminder: EKReminder) -> ReminderRecord {
        let dueComponents = reminder.dueDateComponents
        let dueDate = dueComponents?.date
        let dueAllDay = isAllDay(components: dueComponents)
        let remindAt = reminder.alarms?.first(where: { $0.absoluteDate != nil })?.absoluteDate
        let tags = parseTags(from: reminder.notes)
        let subtaskIds: [String] = []
        return ReminderRecord(
            reminder_id: reminderIdentifier(reminder.calendarItemIdentifier),
            title: reminder.title,
            list_id: reminder.calendar.calendarIdentifier,
            list_name: reminder.calendar.title,
            notes: emptyToNil(reminder.notes),
            due_date: dueDateText(dueDate, dueAllDay: dueAllDay),
            due_all_day: dueAllDay,
            remind_at: remindAt.map(isoString),
            priority: reminder.priority,
            completed: reminder.isCompleted,
            completion_date: reminder.completionDate.map(isoString),
            creation_date: reminder.creationDate.map(isoString),
            modification_date: reminder.lastModifiedDate.map(isoString),
            tags: tags,
            subtask_ids: subtaskIds
        )
    }

    static func calendarRecord(_ calendar: EKCalendar) -> CalendarRecord {
        CalendarRecord(
            calendar_id: calendar.calendarIdentifier,
            title: calendar.title,
            source_title: calendar.source.title,
            allows_content_modifications: calendar.allowsContentModifications,
            color_hex: calendar.cgColor?.hexString
        )
    }

    static func eventRecord(_ event: EKEvent) -> EventRecord {
        let recurrence = event.recurrenceRules?.first.map(recurrenceInfo)
        let attendeeList = event.attendees?.map(attendeeInfo)
        let alarmList = (event.alarms ?? []).map(alarmInfo)
        return EventRecord(
            event_id: event.calendarItemIdentifier,
            title: event.title,
            calendar_id: event.calendar.calendarIdentifier,
            calendar_name: event.calendar.title,
            start: isoString(event.startDate),
            end: isoString(event.endDate),
            all_day: event.isAllDay,
            location: emptyToNil(event.location),
            notes: emptyToNil(event.notes),
            recurrence_rule: recurrence,
            recurring: isInSeries(event),
            attendees: attendeeList,
            alarms: alarmList
        )
    }

    static func alarmInfo(_ alarm: EKAlarm) -> AlarmInfo {
        if let absoluteDate = alarm.absoluteDate {
            return AlarmInfo(type: "absolute", offset_minutes: nil, absolute: isoString(absoluteDate), proximity: nil, location_title: nil)
        }
        if alarm.proximity != .none || alarm.structuredLocation != nil {
            let proximityStr: String
            switch alarm.proximity {
            case .enter: proximityStr = "enter"
            case .leave: proximityStr = "leave"
            @unknown default: proximityStr = "none"
            }
            return AlarmInfo(
                type: "location",
                offset_minutes: safeAlarmOffsetMinutes(alarm.relativeOffset),
                absolute: nil,
                proximity: proximityStr,
                location_title: alarm.structuredLocation?.title
            )
        }
        return AlarmInfo(type: "relative", offset_minutes: safeAlarmOffsetMinutes(alarm.relativeOffset), absolute: nil, proximity: nil, location_title: nil)
    }

    static func recurrenceInfo(_ rule: EKRecurrenceRule) -> RecurrenceInfo {
        let frequency: String
        switch rule.frequency {
        case .daily: frequency = "daily"
        case .weekly: frequency = "weekly"
        case .monthly: frequency = "monthly"
        case .yearly: frequency = "yearly"
        @unknown default: frequency = "unknown"
        }
        let endDate = rule.recurrenceEnd?.endDate.map(isoString)
        return RecurrenceInfo(frequency: frequency, interval: rule.interval, end_date: endDate)
    }

    static func attendeeInfo(_ participant: EKParticipant) -> AttendeeInfo {
        let status: String
        switch participant.participantStatus {
        case .accepted: status = "accepted"
        case .declined: status = "declined"
        case .tentative: status = "tentative"
        case .pending: status = "pending"
        default: status = "unknown"
        }
        return AttendeeInfo(
            name: participant.name,
            email: participant.url.absoluteString.replacingOccurrences(of: "mailto:", with: ""),
            status: status
        )
    }

    static func reminderCalendar(store: EKEventStore, listID: String) throws -> EKCalendar {
        guard let calendar = store.calendar(withIdentifier: listID) else {
            throw BridgeFailure(
                errorCode: "LIST_NOT_FOUND",
                message: "No reminder list matched '\(listID)'.",
                suggestion: "List reminder lists first to discover valid ids."
            )
        }
        return calendar
    }

    static func reminderCalendars(store: EKEventStore, listID: String?) throws -> [EKCalendar]? {
        guard let listID else {
            return nil
        }
        return [try reminderCalendar(store: store, listID: listID)]
    }

    static func eventCalendar(store: EKEventStore, calendarID: String) throws -> EKCalendar {
        guard let calendar = store.calendar(withIdentifier: calendarID) else {
            throw BridgeFailure(
                errorCode: "CALENDAR_NOT_FOUND",
                message: "No calendar matched '\(calendarID)'.",
                suggestion: "List calendars first to discover valid ids."
            )
        }
        return calendar
    }

    static func eventCalendars(store: EKEventStore, calendarID: String?) throws -> [EKCalendar]? {
        guard let calendarID else {
            return nil
        }
        return [try eventCalendar(store: store, calendarID: calendarID)]
    }

    static func fetchReminders(store: EKEventStore, calendars: [EKCalendar]?) throws -> [EKReminder] {
        let semaphore = DispatchSemaphore(value: 0)
        let predicate = store.predicateForReminders(in: calendars)
        var results: [EKReminder] = []
        store.fetchReminders(matching: predicate) { reminders in
            results = reminders ?? []
            semaphore.signal()
        }
        let waitResult = semaphore.wait(timeout: .now() + 30)
        if waitResult == .timedOut {
            throw BridgeFailure(
                errorCode: "BACKEND_TIMEOUT",
                message: "Timed out while fetching reminders.",
                suggestion: "Retry the request."
            )
        }
        return results
    }

    static func calendarAccessStatus() -> AccessStatusPayload {
        switch EKEventStore.authorizationStatus(for: .event) {
        case .authorized:
            return AccessStatusPayload(
                domain: "calendar",
                status: "authorized",
                can_read_events: true,
                can_write_events: true,
                message: nil,
                suggestion: nil
            )
        case .fullAccess:
            return AccessStatusPayload(
                domain: "calendar",
                status: "full_access",
                can_read_events: true,
                can_write_events: true,
                message: nil,
                suggestion: nil
            )
        case .writeOnly:
            return AccessStatusPayload(
                domain: "calendar",
                status: "write_only",
                can_read_events: false,
                can_write_events: true,
                message: "Calendar access is limited to write-only.",
                suggestion: "Allow full Calendar access in System Settings and retry."
            )
        case .notDetermined:
            return AccessStatusPayload(
                domain: "calendar",
                status: "not_determined",
                can_read_events: false,
                can_write_events: false,
                message: "Calendar access has not been granted yet.",
                suggestion: "Run a Calendar tool and approve the macOS permission prompt."
            )
        case .restricted:
            return AccessStatusPayload(
                domain: "calendar",
                status: "restricted",
                can_read_events: false,
                can_write_events: false,
                message: "macOS restricted access to Calendar.",
                suggestion: "Allow Calendar access in System Settings and retry."
            )
        case .denied:
            return AccessStatusPayload(
                domain: "calendar",
                status: "denied",
                can_read_events: false,
                can_write_events: false,
                message: "macOS denied access to Calendar.",
                suggestion: "Allow Calendar access in System Settings and retry."
            )
        @unknown default:
            return AccessStatusPayload(
                domain: "calendar",
                status: "unknown",
                can_read_events: false,
                can_write_events: false,
                message: "Calendar authorization status is unknown.",
                suggestion: "Retry after checking macOS privacy settings."
            )
        }
    }

    static func remindersAccessStatus() -> AccessStatusPayload {
        let status = EKEventStore.authorizationStatus(for: .reminder)
        let granted = status == .authorized || status == .fullAccess
        let label: String
        switch status {
        case .authorized: label = "authorized"
        case .fullAccess: label = "full_access"
        case .writeOnly: label = "write_only"
        case .notDetermined: label = "not_determined"
        case .restricted: label = "restricted"
        case .denied: label = "denied"
        @unknown default: label = "unknown"
        }
        return AccessStatusPayload(
            domain: "reminders",
            status: label,
            can_read_events: granted,
            can_write_events: granted,
            message: granted ? nil : (status == .notDetermined
                ? "Reminders access has not been granted yet."
                : "macOS has not granted Reminders access to \(responsibleAppName())."),
            suggestion: granted ? nil : (status == .notDetermined
                ? "Run a Reminders tool and choose Allow in the macOS prompt for '\(responsibleAppName())'."
                : privacyGuidance(pane: "Reminders", tccService: "Reminders"))
        )
    }

    static func privacyPane(_ entityType: EKEntityType) -> (pane: String, service: String) {
        entityType == .reminder ? ("Reminders", "Reminders") : ("Calendars", "Calendar")
    }

    /// Hands the command to a self-responsible copy of the helper when the
    /// launching app has no grant. Never returns when the relaunch happens.
    static func relaunchIfAccessMissing(_ entityType: EKEntityType) {
        let status = EKEventStore.authorizationStatus(for: entityType)
        if status == .notDetermined || status == .denied {
            relaunchAsSelfResponsible()
        }
    }

    static func deniedFailure(_ entityType: EKEntityType, prompted: Bool = true) -> BridgeFailure {
        let (pane, service) = privacyPane(entityType)
        let client = responsibleAppName()
        return BridgeFailure(
            errorCode: "PERMISSION_DENIED",
            message: prompted
                ? "macOS denied \(entityName(entityType)) access to '\(client)'."
                : "macOS refused to show a \(entityName(entityType)) permission prompt for '\(client)'.",
            suggestion: privacyGuidance(pane: pane, tccService: service)
        )
    }

    static func ensureAccess(store: EKEventStore, entityType: EKEntityType) throws {
        let status = EKEventStore.authorizationStatus(for: entityType)
        switch status {
        case .authorized:
            return
        case .fullAccess:
            return
        case .writeOnly:
            return
        case .restricted:
            throw BridgeFailure(
                errorCode: "PERMISSION_DENIED",
                message: "macOS restricts \(entityName(entityType)) access on this Mac.",
                suggestion: "A configuration profile or Screen Time setting blocks \(entityName(entityType)) access. Ask the Mac's administrator to allow it."
            )
        case .denied:
            relaunchIfAccessMissing(entityType)
            throw deniedFailure(entityType)
        case .notDetermined:
            relaunchIfAccessMissing(entityType)
            try requestAccess(store: store, entityType: entityType)
        @unknown default:
            throw BridgeFailure(
                errorCode: "PERMISSION_UNKNOWN",
                message: "Unknown authorization state for \(entityName(entityType)).",
                suggestion: "Retry after granting access in System Settings."
            )
        }
    }

    static func requestAccess(store: EKEventStore, entityType: EKEntityType) throws {
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        var capturedError: Error?

        if #available(macOS 14.0, *) {
            switch entityType {
            case .reminder:
                store.requestFullAccessToReminders { allowed, error in
                    granted = allowed
                    capturedError = error
                    semaphore.signal()
                }
            case .event:
                store.requestFullAccessToEvents { allowed, error in
                    granted = allowed
                    capturedError = error
                    semaphore.signal()
                }
            @unknown default:
                store.requestAccess(to: entityType) { allowed, error in
                    granted = allowed
                    capturedError = error
                    semaphore.signal()
                }
            }
        } else {
            store.requestAccess(to: entityType) { allowed, error in
                granted = allowed
                capturedError = error
                semaphore.signal()
            }
        }

        let waitResult = semaphore.wait(timeout: .now() + 30)
        if waitResult == .timedOut {
            throw BridgeFailure(
                errorCode: "PERMISSION_TIMEOUT",
                message: "Timed out while requesting access to \(entityName(entityType)).",
                suggestion: "Retry and choose Allow in the macOS prompt for '\(responsibleAppName())'."
            )
        }
        if let capturedError {
            throw BridgeFailure(
                errorCode: "PERMISSION_REQUEST_FAILED",
                message: String(describing: capturedError),
                suggestion: "Retry after checking macOS privacy settings."
            )
        }
        if !granted {
            // Still undetermined after a refused request means macOS never showed a prompt.
            throw deniedFailure(entityType, prompted: EKEventStore.authorizationStatus(for: entityType) != .notDetermined)
        }
    }

    static func requiredDate(_ payload: [String: Any], field: String) throws -> Date {
        guard let raw = stringValue(payload, field: field) else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "Missing required field '\(field)'.",
                suggestion: "Provide '\(field)' in ISO 8601 format."
            )
        }
        return try parseDate(raw)
    }

    static func optionalDate(_ payload: [String: Any], field: String) throws -> Date? {
        guard let raw = stringValue(payload, field: field) else {
            return nil
        }
        return try parseDate(raw)
    }

    static func parseDate(_ raw: String) throws -> Date {
        if let date = isoFormatterWithFractional.date(from: raw) ?? isoFormatter.date(from: raw) {
            return date
        }

        let dayFormatter = DateFormatter()
        dayFormatter.calendar = localCalendar
        dayFormatter.locale = Locale(identifier: "en_US_POSIX")
        dayFormatter.timeZone = localCalendar.timeZone
        dayFormatter.dateFormat = "yyyy-MM-dd"
        if let date = dayFormatter.date(from: raw) {
            return date
        }

        throw BridgeFailure(
            errorCode: "INVALID_INPUT",
            message: "Invalid ISO 8601 date '\(raw)'.",
            suggestion: "Use a full ISO timestamp or a yyyy-MM-dd date."
        )
    }

    static func dateComponents(for date: Date, allDay: Bool) -> DateComponents {
        if allDay {
            return localCalendar.dateComponents([.year, .month, .day], from: date)
        }
        return localCalendar.dateComponents([.year, .month, .day, .hour, .minute, .second, .timeZone], from: date)
    }

    static func dueDateText(_ date: Date?, dueAllDay: Bool) -> String? {
        guard let date else {
            return nil
        }
        if dueAllDay {
            let formatter = DateFormatter()
            formatter.calendar = localCalendar
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = localCalendar.timeZone
            formatter.dateFormat = "yyyy-MM-dd"
            return formatter.string(from: date)
        }
        return isoString(date)
    }

    static func isAllDay(components: DateComponents?) -> Bool {
        guard let components else {
            return false
        }
        return components.hour == nil && components.minute == nil && components.second == nil
    }

    static func requiredString(_ payload: [String: Any], field: String) throws -> String {
        guard let value = stringValue(payload, field: field), !value.isEmpty else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "Missing required field '\(field)'.",
                suggestion: "Provide a non-empty '\(field)'."
            )
        }
        return value
    }

    static func stringValue(_ payload: [String: Any], field: String) -> String? {
        guard let value = payload[field], !(value is NSNull) else {
            return nil
        }
        let text = String(describing: value).trimmingCharacters(in: .whitespacesAndNewlines)
        return text.isEmpty ? nil : text
    }

    static func nullableStringValue(_ payload: [String: Any], field: String) -> String? {
        if payload[field] is NSNull {
            return nil
        }
        return stringValue(payload, field: field)
    }

    static func intValue(_ payload: [String: Any], field: String) -> Int? {
        if let value = payload[field] as? Int {
            return value
        }
        if let value = payload[field] as? NSNumber {
            return value.intValue
        }
        if let value = payload[field] as? String {
            return Int(value)
        }
        return nil
    }

    static func boolArgument(_ raw: String, field: String) throws -> Bool {
        switch raw.lowercased() {
        case "true", "1", "yes", "on":
            return true
        case "false", "0", "no", "off":
            return false
        default:
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "Field '\(field)' must be a boolean.",
                suggestion: "Use true or false."
            )
        }
    }

    static func decodeObjectArgument(_ arguments: [String], expectedCount: Int) throws -> [String: Any] {
        guard arguments.count == expectedCount, let raw = arguments.first else {
            throw usageError("payload")
        }
        return try decodeJSONObject(raw)
    }

    static func decodeJSONObject(_ raw: String) throws -> [String: Any] {
        guard let data = raw.data(using: .utf8) else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "Payload was not valid UTF-8.",
                suggestion: "Encode the JSON payload as UTF-8."
            )
        }
        let object = try JSONSerialization.jsonObject(with: data)
        guard let dictionary = object as? [String: Any] else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "Payload must be a JSON object.",
                suggestion: "Pass an object with named fields."
            )
        }
        return dictionary
    }

    static func usageError(_ command: String) -> BridgeFailure {
        BridgeFailure(
            errorCode: "USAGE_ERROR",
            message: "Invalid arguments for '\(command)'.",
            suggestion: "Check the Python bridge command construction."
        )
    }

    static func entityName(_ entityType: EKEntityType) -> String {
        switch entityType {
        case .event:
            return "Calendar"
        case .reminder:
            return "Reminders"
        @unknown default:
            return "EventKit"
        }
    }

    static func isoString(_ date: Date) -> String {
        isoFormatter.string(from: date)
    }

    static func reminderIdentifier(_ rawValue: String) -> String {
        if rawValue.hasPrefix("x-apple-reminder://") {
            return rawValue
        }
        return "x-apple-reminder://\(rawValue)"
    }

    static func nativeReminderIdentifier(_ rawValue: String) -> String {
        rawValue.replacingOccurrences(of: "x-apple-reminder://", with: "")
    }

    static func emptyToNil(_ value: String?) -> String? {
        guard let value else {
            return nil
        }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    static func encode<T: Encodable>(_ value: T) throws -> Data {
        try outputEncoder.encode(value)
    }

    static func writeErrorAndExit(_ failure: BridgeFailure) -> Never {
        let payload = ErrorPayload(
            error_code: failure.errorCode,
            message: failure.message,
            suggestion: failure.suggestion
        )
        let data = (try? outputEncoder.encode(payload)) ?? Data()
        if !data.isEmpty {
            FileHandle.standardOutput.write(data)
        }
        Foundation.exit(1)
    }

    static func parseTags(from notes: String?) -> [String] {
        guard let notes, !notes.isEmpty else {
            return []
        }
        let pattern = #"(?<!\w)#([A-Za-z0-9_-]+)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return []
        }
        let range = NSRange(notes.startIndex..., in: notes)
        let matches = regex.matches(in: notes, range: range)
        var seen = Set<String>()
        var tags: [String] = []
        for match in matches {
            if let tagRange = Range(match.range(at: 1), in: notes) {
                let tag = String(notes[tagRange])
                if !seen.contains(tag) {
                    seen.insert(tag)
                    tags.append(tag)
                }
            }
        }
        return tags
    }

    static func createReminderList(store: EKEventStore, payload: [String: Any]) throws -> ReminderListMutationPayload {
        let title = try requiredString(payload, field: "title")
        let calendar = EKCalendar(for: .reminder, eventStore: store)
        calendar.title = title
        guard let source = store.defaultCalendarForNewReminders()?.source ?? store.sources.first(where: { $0.sourceType == .calDAV || $0.sourceType == .local }) else {
            throw BridgeFailure(
                errorCode: "NO_SOURCE",
                message: "No suitable calendar source found for creating a reminder list.",
                suggestion: "Ensure at least one calendar account is configured."
            )
        }
        calendar.source = source
        try store.saveCalendar(calendar, commit: true)
        return ReminderListMutationPayload(list_id: calendar.calendarIdentifier, title: calendar.title, created: true)
    }

    static func validateReminderListDeletion(entityTypes: EKEntityMask, allowsModifications: Bool) throws {
        // Event and reminder calendars share identifiers. A mixed calendar
        // must never be deleted through the Reminders list tool either.
        guard entityTypes.contains(.reminder), !entityTypes.contains(.event) else {
            throw BridgeFailure(errorCode: "LIST_NOT_FOUND", message: "The target is not an exclusive reminder list.", suggestion: "List reminder lists first to discover valid ids.")
        }
        guard allowsModifications else {
            throw BridgeFailure(errorCode: "LIST_READ_ONLY", message: "The reminder list does not allow modifications.", suggestion: "Choose a writable reminder list.")
        }
    }

    static func deleteReminderList(store: EKEventStore, listID: String) throws -> BooleanMutationPayload {
        guard let calendar = store.calendar(withIdentifier: listID) else {
            return BooleanMutationPayload(deleted: false, object_id: listID)
        }
        try validateReminderListDeletion(
            entityTypes: calendar.allowedEntityTypes,
            allowsModifications: calendar.allowsContentModifications
        )
        try store.removeCalendar(calendar, commit: true)
        return BooleanMutationPayload(deleted: true, object_id: listID)
    }
}

extension CGColor {
    var hexString: String? {
        guard let components, components.count >= 3 else {
            return nil
        }
        let red = Int((components[0] * 255.0).rounded())
        let green = Int((components[1] * 255.0).rounded())
        let blue = Int((components[2] * 255.0).rounded())
        return String(format: "#%02X%02X%02X", red, green, blue)
    }
}
