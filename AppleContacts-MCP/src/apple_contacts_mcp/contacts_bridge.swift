// Native Contacts helper for apple-contacts-mcp. It replaces the AppleScript files the
// server used to run through osascript and talks to the Contacts framework
// (CNContactStore) instead, so it never launches or waits on Contacts.app and needs
// only the Privacy > Contacts permission. AppleContactsBridge compiles it on first use.
//
// Usage: apple-contacts-bridge <command> [args...]
// Each command takes the same positional arguments as the AppleScript of the same
// name and prints the same JSON object on stdout; errors go to stderr with exit 1.
//
//   permission_check
//   list_contacts LIMIT OFFSET
//   search_contacts QUERY LIMIT
//   get_contact ID
//   create_contact FIRST LAST ORG PHONES EMAILS NOTE
//   update_contact ID FIRST LAST ORG PHONES EMAILS NOTE
//   delete_contact ID
//
// PHONES and EMAILS are "label\u{1F}value" records joined by "\u{1E}"; for
// update_contact "__NOCHANGE__" leaves them untouched and anything else replaces
// the whole set. Empty FIRST/LAST/ORG/NOTE on update leave the field unchanged.
//
// Adapted from JaumeAP/Apple-MCPs by Jaume Puig (MIT).
import Contacts
import Darwin
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

let fieldSeparator: Character = "\u{1F}"
let recordSeparator: Character = "\u{1E}"
let noChangeSentinel = "__NOCHANGE__"

func fail(_ message: String) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(1)
}

func emit(_ object: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) else {
        fail("Could not encode the result as JSON.")
    }
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}

let store = CNContactStore()

/// Writes a structured error to stderr and exits; the server reads its code and suggestion.
func failPermission(_ code: String, _ message: String, _ suggestion: String) -> Never {
    let object: [String: Any] = ["ok": false, "error_code": code, "message": message, "suggestion": suggestion]
    if let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) {
        FileHandle.standardError.write(data)
        FileHandle.standardError.write("\n".data(using: .utf8)!)
    }
    exit(1)
}

func contactsAccessGranted(_ status: CNAuthorizationStatus) -> Bool {
    // Limited access is raw value 4; older macOS SDKs do not name this case.
    // Honor the selected-contact grant without requiring a newer SDK symbol.
    status == .authorized || status.rawValue == 4
}

/// Hands the command to a self-responsible copy of the helper when the
/// launching app has no grant. Never returns when the relaunch happens.
func relaunchIfContactsAccessMissing() {
    let status = CNContactStore.authorizationStatus(for: .contacts)
    if status == .notDetermined || status == .denied {
        relaunchAsSelfResponsible()
    }
}

func requireAccess() {
    let status = CNContactStore.authorizationStatus(for: .contacts)
    if contactsAccessGranted(status) { return }
    switch status {
    case .restricted:
        failPermission("PERMISSION_DENIED", "macOS restricts Contacts access on this Mac.",
                       "A configuration profile or Screen Time setting blocks Contacts access. Ask the Mac's administrator to allow it.")
    case .denied:
        relaunchIfContactsAccessMissing()
        failPermission("PERMISSION_DENIED", "macOS denied Contacts access to '\(responsibleAppName())'.",
                       privacyGuidance(pane: "Contacts", tccService: "AddressBook"))
    default:
        relaunchIfContactsAccessMissing()
    }
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    store.requestAccess(for: .contacts) { ok, _ in
        granted = ok
        semaphore.signal()
    }
    guard semaphore.wait(timeout: .now() + 25) == .success else {
        failPermission("PERMISSION_TIMEOUT", "Timed out waiting for an answer to the macOS Contacts prompt.",
                       "Retry and choose Allow in the macOS prompt for '\(responsibleAppName())'.")
    }
    if !granted {
        // Still undetermined after a refused request means macOS never showed a prompt.
        let prompted = CNContactStore.authorizationStatus(for: .contacts) != .notDetermined
        failPermission("PERMISSION_DENIED",
                       prompted ? "macOS denied Contacts access to '\(responsibleAppName())'."
                                : "macOS refused to show a Contacts permission prompt for '\(responsibleAppName())'.",
                       privacyGuidance(pane: "Contacts", tccService: "AddressBook"))
    }
}

// The note field is deliberately absent: reading it needs an entitlement that an
// unsigned command-line tool cannot have, and the AppleScript version never
// returned it either.
let summaryKeys: [CNKeyDescriptor] = [
    CNContactIdentifierKey as CNKeyDescriptor,
    CNContactGivenNameKey as CNKeyDescriptor,
    CNContactFamilyNameKey as CNKeyDescriptor,
    CNContactOrganizationNameKey as CNKeyDescriptor,
    CNContactPhoneNumbersKey as CNKeyDescriptor,
    CNContactEmailAddressesKey as CNKeyDescriptor,
    CNContactFormatter.descriptorForRequiredKeys(for: .fullName),
]

// Contacts.app shows built-in labels as plain words; the framework stores them as
// "_$!<Word>!$_" constants. Map both ways so labels round-trip like before.
let labelNames: [(String, String)] = [
    (CNLabelHome, "home"), (CNLabelWork, "work"), (CNLabelOther, "other"), (CNLabelSchool, "school"),
    (CNLabelPhoneNumberMobile, "mobile"), (CNLabelPhoneNumberiPhone, "iPhone"),
    (CNLabelPhoneNumberMain, "main"), (CNLabelPhoneNumberHomeFax, "home fax"),
    (CNLabelPhoneNumberWorkFax, "work fax"), (CNLabelPhoneNumberOtherFax, "other fax"),
    (CNLabelPhoneNumberPager, "pager"), (CNLabelEmailiCloud, "iCloud"),
]

func displayLabel(_ raw: String?) -> String {
    guard let raw, !raw.isEmpty else { return "" }
    if let match = labelNames.first(where: { $0.0 == raw }) { return match.1 }
    if raw.hasPrefix("_$!<") && raw.hasSuffix(">!$_") {
        return String(raw.dropFirst(4).dropLast(4)).lowercased()
    }
    return raw
}

func storedLabel(_ display: String) -> String {
    labelNames.first(where: { $0.1.lowercased() == display.lowercased() })?.0 ?? display
}

func methods(_ raw: String) -> [(label: String, value: String)] {
    raw.split(separator: recordSeparator, omittingEmptySubsequences: true).compactMap { record in
        let parts = record.split(separator: fieldSeparator, maxSplits: 1, omittingEmptySubsequences: false)
        guard parts.count == 2 else { return nil }
        return (String(parts[0]), String(parts[1]))
    }
}

func displayName(_ contact: CNContact) -> String {
    let formatted = CNContactFormatter.string(from: contact, style: .fullName) ?? ""
    return formatted.isEmpty ? contact.organizationName : formatted
}

func personJSON(_ contact: CNContact) -> [String: Any] {
    let phones = contact.phoneNumbers.map { ["label": displayLabel($0.label), "value": $0.value.stringValue] }
    let emails = contact.emailAddresses.map { ["label": displayLabel($0.label), "value": $0.value as String] }
    return [
        "contact_id": contact.identifier,
        "name": displayName(contact),
        "first_name": contact.givenName,
        "last_name": contact.familyName,
        "organization": contact.organizationName,
        "phone_count": phones.count,
        "email_count": emails.count,
        "phones": phones,
        "emails": emails,
        "note": "",
    ]
}

func allContacts(keys: [CNKeyDescriptor] = summaryKeys) -> [CNContact] {
    let request = CNContactFetchRequest(keysToFetch: keys)
    request.sortOrder = .userDefault
    var result: [CNContact] = []
    do {
        try store.enumerateContacts(with: request) { contact, _ in result.append(contact) }
    } catch {
        fail("Could not read Contacts: \(error.localizedDescription)")
    }
    return result
}

func findContact(_ id: String, keys: [CNKeyDescriptor] = summaryKeys) -> CNContact? {
    let predicate = CNContact.predicateForContacts(withIdentifiers: [id])
    do {
        return try store.unifiedContacts(matching: predicate, keysToFetch: keys).first
    } catch {
        fail("Could not read Contacts: \(error.localizedDescription)")
    }
}

let noteUnavailableMessage = "Notes cannot be written: macOS reserves the note field for apps with a special entitlement. Leave note empty or use the AppleScript backend."

func execute(_ request: CNSaveRequest) {
    do {
        try store.execute(request)
    } catch {
        fail("Contacts refused the change: \(error.localizedDescription)")
    }
}

func intArgument(_ args: [String], _ index: Int, _ name: String) -> Int {
    guard index < args.count, let value = Int(args[index]) else { fail("\(name) must be an integer.") }
    return value
}

func argument(_ args: [String], _ index: Int) -> String {
    index < args.count ? args[index] : ""
}

@main
struct NativeContactsBridge {
    static func main() {
        let arguments = Array(CommandLine.arguments.dropFirst())
        guard let command = arguments.first else { fail("Missing command.") }
        let args = Array(arguments.dropFirst())
        if command == "permission_check" {
            relaunchIfContactsAccessMissing()
            let status = CNContactStore.authorizationStatus(for: .contacts)
            let accessible = contactsAccessGranted(status)
            let label = accessible ? "authorized" : (status == .denied || status == .restricted ? "denied" : "unknown")
            var result: [String: Any] = [
                "ok": true, "accessible": accessible, "status": label,
                "tcc_client": responsibleAppName(), "helper_is_responsible": helperIsSelfResponsible(),
            ]
            if !accessible {
                result["suggestion"] = status == .notDetermined
                    ? "Run a Contacts tool and choose Allow in the macOS prompt for '\(responsibleAppName())'."
                    : privacyGuidance(pane: "Contacts", tccService: "AddressBook")
            }
            emit(result)
            return
        }
        requireAccess()

        switch command {
        case "list_contacts":
            let limit = max(0, intArgument(args, 0, "LIMIT"))
            let offset = max(0, intArgument(args, 1, "OFFSET"))
            let contacts = allContacts()
            let page = contacts.dropFirst(offset).prefix(limit)
            emit(["items": page.map(personJSON), "total": contacts.count])

        case "search_contacts":
            let query = argument(args, 0)
            let limit = max(0, intArgument(args, 1, "LIMIT"))
            // Same rule as the AppleScript: name or organization contains the query, ignoring case.
            let matches = allContacts().filter {
                displayName($0).range(of: query, options: .caseInsensitive) != nil
                    || $0.organizationName.range(of: query, options: .caseInsensitive) != nil
            }
            emit(["items": matches.prefix(limit).map(personJSON)])

        case "get_contact":
            if let contact = findContact(argument(args, 0)) {
                emit(["found": true, "contact": personJSON(contact)])
            } else {
                emit(["found": false])
            }

        case "create_contact":
            let contact = CNMutableContact()
            contact.givenName = argument(args, 0)
            contact.familyName = argument(args, 1)
            contact.organizationName = argument(args, 2)
            contact.phoneNumbers = methods(argument(args, 3)).map {
                CNLabeledValue(label: storedLabel($0.label), value: CNPhoneNumber(stringValue: $0.value))
            }
            contact.emailAddresses = methods(argument(args, 4)).map {
                CNLabeledValue(label: storedLabel($0.label), value: $0.value as NSString)
            }
            // A fresh CNMutableContact reports the note key as available, so setNote's guard
            // would pass and the save would fail on the missing entitlement. Refuse up front.
            if !argument(args, 5).isEmpty { fail(noteUnavailableMessage) }
            let request = CNSaveRequest()
            request.add(contact, toContainerWithIdentifier: nil)
            execute(request)
            emit(["contact_id": contact.identifier, "name": displayName(contact), "created": true])

        case "update_contact":
            let id = argument(args, 0)
            let note = argument(args, 6)
            if !note.isEmpty { fail(noteUnavailableMessage) }
            guard let original = findContact(id) else { fail("Can’t get person id \"\(id)\".") }
            let contact = original.mutableCopy() as! CNMutableContact
            if !argument(args, 1).isEmpty { contact.givenName = argument(args, 1) }
            if !argument(args, 2).isEmpty { contact.familyName = argument(args, 2) }
            if !argument(args, 3).isEmpty { contact.organizationName = argument(args, 3) }
            if argument(args, 4) != noChangeSentinel {
                contact.phoneNumbers = methods(argument(args, 4)).map {
                    CNLabeledValue(label: storedLabel($0.label), value: CNPhoneNumber(stringValue: $0.value))
                }
            }
            if argument(args, 5) != noChangeSentinel {
                contact.emailAddresses = methods(argument(args, 5)).map {
                    CNLabeledValue(label: storedLabel($0.label), value: $0.value as NSString)
                }
            }
            let request = CNSaveRequest()
            request.update(contact)
            execute(request)
            emit(["contact_id": id, "name": displayName(contact), "updated": true])

        case "delete_contact":
            let id = argument(args, 0)
            guard let original = findContact(id) else {
                emit(["contact_id": id, "deleted": false])
                exit(0)
            }
            let request = CNSaveRequest()
            request.delete(original.mutableCopy() as! CNMutableContact)
            execute(request)
            // Deleting a unified contact can leave some of its linked cards behind, so report
            // what the store holds now rather than assuming the save removed everything.
            emit(["contact_id": id, "deleted": findContact(id) == nil])

        default:
            fail("Unknown command '\(command)'.")
        }
    }
}
