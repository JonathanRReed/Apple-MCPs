import EventKit
import Foundation

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
}

struct BooleanMutationPayload: Encodable {
    let deleted: Bool
    let object_id: String
}

struct ListPayload<T: Encodable>: Encodable {
    let count: Int
    let items: [T]
}

struct AccessStatusPayload: Encodable {
    let ok = true
    let domain: String
    let status: String
    let can_read_events: Bool
    let can_write_events: Bool
    let message: String?
    let suggestion: String?
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
            return try encode(calendarAccessStatus())
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
            guard arguments.count == 1 else {
                throw usageError(command)
            }
            return try encode(try deleteEvent(store: store, eventID: arguments[0]))
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

    static func getEvent(store: EKEventStore, eventID: String) throws -> EventRecord {
        guard let event = store.event(withIdentifier: eventID) else {
            throw BridgeFailure(
                errorCode: "EVENT_NOT_FOUND",
                message: "No event matched '\(eventID)'.",
                suggestion: "List calendar events first to discover valid ids."
            )
        }
        return eventRecord(event)
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
        guard let event = store.event(withIdentifier: eventID) else {
            throw BridgeFailure(
                errorCode: "EVENT_NOT_FOUND",
                message: "No event matched '\(eventID)'.",
                suggestion: "List calendar events first to discover valid ids."
            )
        }
        try applyEventFields(store: store, event: event, payload: payload, isCreate: false)
        guard event.endDate > event.startDate else {
            throw BridgeFailure(
                errorCode: "INVALID_INPUT",
                message: "The end date must be later than the start date.",
                suggestion: "Provide a valid start and end."
            )
        }
        try store.save(event, span: .thisEvent, commit: true)
        return eventRecord(event)
    }

    static func deleteEvent(store: EKEventStore, eventID: String) throws -> BooleanMutationPayload {
        guard let event = store.event(withIdentifier: eventID) else {
            return BooleanMutationPayload(deleted: false, object_id: eventID)
        }
        try store.remove(event, span: .thisEvent, commit: true)
        return BooleanMutationPayload(deleted: true, object_id: eventID)
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
            modification_date: reminder.lastModifiedDate.map(isoString)
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
        EventRecord(
            event_id: event.calendarItemIdentifier,
            title: event.title,
            calendar_id: event.calendar.calendarIdentifier,
            calendar_name: event.calendar.title,
            start: isoString(event.startDate),
            end: isoString(event.endDate),
            all_day: event.isAllDay,
            location: emptyToNil(event.location),
            notes: emptyToNil(event.notes)
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

    static func ensureAccess(store: EKEventStore, entityType: EKEntityType) throws {
        let status = EKEventStore.authorizationStatus(for: entityType)
        switch status {
        case .authorized:
            return
        case .fullAccess:
            return
        case .writeOnly:
            return
        case .restricted, .denied:
            throw BridgeFailure(
                errorCode: "PERMISSION_DENIED",
                message: "macOS denied access to \(entityName(entityType)).",
                suggestion: "Allow access in System Settings and retry."
            )
        case .notDetermined:
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
                suggestion: "Retry and accept the macOS permission prompt."
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
            throw BridgeFailure(
                errorCode: "PERMISSION_DENIED",
                message: "macOS denied access to \(entityName(entityType)).",
                suggestion: "Allow access in System Settings and retry."
            )
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
