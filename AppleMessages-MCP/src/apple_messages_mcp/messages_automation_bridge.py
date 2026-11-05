from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Required, TypedDict


class SendResult(TypedDict, total=False):
    """Fields a send reports back; validated into models.SendResponse."""

    sent: Required[bool]
    recipient: str
    chat_id: str
    file_path: str
    text: str | None
    service_name: str | None


class MessagesAutomationBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


# Messages' AppleScript "service type" enumerators on macOS 15+ (sdef: SMS, iMessage, RCS).
SERVICE_NAMES = {"imessage": "iMessage", "sms": "SMS", "rcs": "RCS"}
DEFAULT_SERVICE = "iMessage"
_NO_ACCOUNT_ERROR_NUMBER = 9001
# `send` returns before a file is transferred, so a send waits this long for
# Messages to report how the transfer ended.
_TRANSFER_WAIT_SECONDS = 20
_TRANSFER_POLL_SECONDS = 1
# Messages' scripting dictionary gained the RCS service type in macOS 15.
_RCS_MIN_MACOS = 15
_ENABLE_FORWARDING = (
    "turn on Text Message Forwarding for this Mac on the iPhone (Settings > Apps > Messages > Text Message Forwarding)"
)


def normalize_service_name(service_name: str | None) -> str | None:
    """Return the canonical service name, None when unset, or raise for unknown values."""
    if service_name is None or not service_name.strip():
        return None
    canonical = SERVICE_NAMES.get(service_name.strip().lower())
    if canonical is None:
        raise MessagesAutomationBridgeError(
            "INVALID_INPUT",
            f"Unsupported service_name '{service_name}'.",
            "Use iMessage, SMS or RCS, or omit service_name to send as iMessage.",
        )
    return canonical


def _macos_major_version() -> int | None:
    """Major macOS version, or None when unknown (non-macOS, or the 10.16 compatibility shim)."""
    release = platform.mac_ver()[0]
    try:
        parts = [int(part) for part in release.split(".")[:2]]
    except ValueError:
        return None
    if not parts or parts[:2] == [10, 16]:
        return None
    return parts[0]


def _rcs_scriptable() -> bool:
    """False only when this Mac is known to predate RCS in Messages' scripting dictionary."""
    major = _macos_major_version()
    return major is None or major >= _RCS_MIN_MACOS


class MessagesAutomationBridge:
    def __init__(self, allowed_roots: tuple[Path, ...] = ()) -> None:
        self.allowed_roots = allowed_roots

    def automation_accessible(self) -> bool:
        accessible, _ = self.automation_access_diagnostic()
        return accessible

    def automation_access_diagnostic(self) -> tuple[bool, MessagesAutomationBridgeError | None]:
        try:
            # NSRunningApplication queries Launch Services without Apple Events.
            running = self._run_command([
                "osascript", "-l", "JavaScript", "-e",
                'ObjC.import("AppKit"); $.NSRunningApplication.runningApplicationsWithBundleIdentifier("com.apple.MobileSMS").count > 0',
            ], timeout=5)
            if running == "false":
                return False, MessagesAutomationBridgeError(
                    "NOT_PROBED", "Messages is not running; automation access was not probed.",
                    "Use an explicit Messages operation when needed.",
                )
            if running != "true":
                raise MessagesAutomationBridgeError("AUTOMATION_FAILED", "Could not determine whether Messages is running.")
            return False, MessagesAutomationBridgeError(
                "AUTHORIZATION_UNKNOWN", "Messages is running; automation authorization has not been checked.",
                "An explicit send or reply checks authorization and may show the macOS Automation prompt.",
            )
        except MessagesAutomationBridgeError as exc:
            return False, exc

    def send_message(
        self, recipient: str, text: str, service_name: str | None = None, *, services: list[str] | None = None
    ) -> SendResult:
        """Send to one recipient over the first available of ``services``.

        ``service_name`` picks one service explicitly (iMessage, SMS or RCS);
        ``services`` is an ordered preference list for callers that infer the
        service (e.g. replying in an SMS/RCS thread). Neither keeps the
        previous behaviour: iMessage.
        """
        if not recipient.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "recipient must not be empty", "Provide an explicit iMessage address or phone number.")
        if not text.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "text must not be empty", "Provide a non-empty message body.")
        wanted, thread_service = self._service_preference(service_name, services)
        script = f'''
        tell application "Messages"
{self._account_selection(wanted)}
            set targetParticipant to participant "{self._escape(recipient)}" of targetAccount
            send "{self._escape(text)}" to targetParticipant
            return usedService
        end tell
        '''
        used = self._run_send_script(script, wanted, thread_service)
        return {
            "sent": True,
            "recipient": recipient,
            "text": text,
            "service_name": used,
        }

    def send_to_group(self, chat_id: str, text: str) -> SendResult:
        if not chat_id.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "chat_id must not be empty", "Provide a valid chat_id from conversation history.")
        if not text.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "text must not be empty", "Provide a non-empty message body.")

        script = f'''
        tell application "Messages"
            set targetChat to chat id "{self._escape(chat_id)}"
            send "{self._escape(text)}" to targetChat
        end tell
        '''
        self._run_script(script)
        return {
            "sent": True,
            "chat_id": chat_id,
            "text": text,
        }

    def send_attachment(
        self, recipient: str, file_path: str, text: str | None = None, service_name: str | None = None
    ) -> SendResult:
        if not recipient.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "recipient must not be empty", "Provide an explicit iMessage address or phone number.")
        if not file_path.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "file_path must not be empty", "Provide a valid file path.")

        attachment = self._ensure_attachment_allowed(file_path)
        wanted, _ = self._service_preference(service_name, None)
        staged = self._stage_attachment(attachment)
        script = f'''
        tell application "Messages"
{self._account_selection(wanted)}
            set targetParticipant to participant "{self._escape(recipient)}" of targetAccount
            send POSIX file "{self._escape(str(staged))}" to targetParticipant
            return usedService
        end tell
        '''
        known_transfers = set(self._outgoing_transfers())
        try:
            used = self._run_send_script(script, wanted, None)
            self._confirm_transfer(staged, attachment, known_transfers)
        except MessagesAutomationBridgeError as exc:
            # A transfer still in progress may need its file, so that one stays.
            if staged != attachment and exc.error_code != "SEND_STATUS_UNKNOWN":
                shutil.rmtree(staged.parent, ignore_errors=True)
            raise
        # The text follows only a confirmed file, so a failed send leaves no
        # caption for a file that never arrived.
        if text and text.strip():
            try:
                self.send_message(recipient, text, service_name=used)
            except MessagesAutomationBridgeError as exc:
                raise MessagesAutomationBridgeError(
                    exc.error_code,
                    f"The file was sent, but the text was not: {exc.message}",
                    "Send only the text. Do not send the file again.",
                ) from exc
        return {
            "sent": True,
            "recipient": recipient,
            "file_path": str(attachment),
            "text": text,
            "service_name": used,
        }

    def _stage_attachment(self, attachment: Path) -> Path:
        # Messages is sandboxed and can fail to read a file in a user folder
        # such as Downloads, so it gets a private copy inside its own
        # attachments folder. Each copy has its own folder to keep its file name.
        # Without access to that folder, the transfer check reports the outcome.
        try:
            staging = Path.home() / "Library" / "Messages" / "Attachments" / "apple-mcp"
            staging.mkdir(exist_ok=True)
            staged = Path(tempfile.mkdtemp(dir=staging)) / attachment.name
            shutil.copyfile(attachment, staged)
        except OSError:
            return attachment
        return staged

    def _outgoing_transfers(self) -> dict[str, tuple[str, str]]:
        """Return each outgoing file transfer's name and status by id."""
        output = self._run_script('''
        tell application "Messages"
            set transferIds to id of every file transfer
            set transferNames to name of every file transfer
            set transferStates to transfer status of every file transfer
            set transferDirections to direction of every file transfer
        end tell
        set output to ""
        repeat with i from 1 to count of transferIds
            if ((item i of transferDirections) as text) is "outgoing" then
                set output to output & (item i of transferIds) & tab & (item i of transferNames) & tab & ((item i of transferStates) as text) & linefeed
            end if
        end repeat
        return output
        ''')
        transfers = {}
        for line in output.splitlines():
            transfer_id, _, rest = line.partition("\t")
            name, _, status = rest.rpartition("\t")
            transfers[transfer_id] = (name, status)
        return transfers

    def _confirm_transfer(self, staged: Path, attachment: Path, known_transfers: set[str]) -> None:
        deadline = time.monotonic() + _TRANSFER_WAIT_SECONDS
        while True:
            try:
                transfers = self._outgoing_transfers()
            except MessagesAutomationBridgeError:
                transfers = {}
            statuses = {status for transfer_id, (name, status) in transfers.items() if transfer_id not in known_transfers and name == staged.name}
            if "failed" in statuses:
                raise MessagesAutomationBridgeError(
                    "ATTACHMENT_NOT_DELIVERED",
                    f"Messages could not send the file: {attachment}. No text was sent.",
                    "Give the app running this server Full Disk Access, so the file can be copied where Messages can read it, then retry."
                    if staged == attachment
                    else "Check that the file opens and that Messages is signed in, then retry.",
                )
            if "finished" in statuses:
                return
            if time.monotonic() >= deadline:
                raise MessagesAutomationBridgeError(
                    "SEND_STATUS_UNKNOWN",
                    f"Messages has not confirmed the file was sent: {attachment}. It may still go out. No text was sent.",
                    "Check the conversation in Messages before sending again.",
                )
            time.sleep(_TRANSFER_POLL_SECONDS)

    def _ensure_attachment_allowed(self, path: str) -> Path:
        # An attachment leaves this Mac, so like every other file tool it stays
        # inside the allowed folders. The resolved path is what gets sent, so
        # `..` and symbolic links cannot leave them.
        resolved = Path(path).expanduser().resolve(strict=False)
        roots = tuple(root.resolve(strict=False) for root in self.allowed_roots)
        if not any(resolved != root and resolved.is_relative_to(root) for root in roots):
            folders = ", ".join(str(root) for root in roots)
            raise MessagesAutomationBridgeError(
                "PATH_NOT_ALLOWED",
                f"Attachment is outside the allowed folders: {resolved}",
                f"Send a file inside one of these folders: {folders}. Set APPLE_MESSAGES_MCP_ALLOWED_ROOTS (in Claude Desktop: \"Folders Messages may send files from\") to change them.",
            )
        if not resolved.is_file():
            raise MessagesAutomationBridgeError("FILE_NOT_FOUND", f"No file at: {resolved}", "Check the path; only a single file can be sent.")
        return resolved

    @staticmethod
    def _service_preference(service_name: str | None, services: list[str] | None) -> tuple[list[str], str | None]:
        """Return the ordered services to try and, when inferred from ``services``, the thread's service.

        RCS is dropped on Macs known to predate it in Messages' scripting
        dictionary (macOS < 15); if nothing is left the send is refused with
        SERVICE_UNAVAILABLE instead of failing inside AppleScript.
        """
        explicit = normalize_service_name(service_name)
        if explicit is not None:
            wanted, thread_service = [explicit], None
        else:
            preferred = [name for name in (normalize_service_name(item) for item in services or []) if name]
            wanted, thread_service = (preferred, preferred[0]) if preferred else ([DEFAULT_SERVICE], None)
        if "RCS" in wanted and not _rcs_scriptable():
            wanted = [name for name in wanted if name != "RCS"]
            if not wanted:
                requested = "This thread's last message used RCS" if thread_service else "service_name='RCS' was requested"
                raise MessagesAutomationBridgeError(
                    "SERVICE_UNAVAILABLE",
                    f"{requested}, but RCS sending needs macOS {_RCS_MIN_MACOS} or later "
                    f"and this Mac runs macOS {platform.mac_ver()[0]}. Nothing was sent.",
                    "Retry with service_name='SMS' (needs Text Message Forwarding) or service_name='iMessage'.",
                )
        return wanted, thread_service

    @staticmethod
    def _account_selection(services: list[str]) -> str:
        """AppleScript that sets targetAccount/usedService to the first enabled account of ``services``."""
        lines = ["            set targetAccount to missing value", '            set usedService to ""']
        for name in services:
            lines += [
                "            if targetAccount is missing value then",
                f"                set candidateAccounts to (every account whose service type = {name} and enabled is true)",
                "                if (count of candidateAccounts) > 0 then",
                "                    set targetAccount to item 1 of candidateAccounts",
                f'                    set usedService to "{name}"',
                "                end if",
                "            end if",
            ]
        lines.append(
            f'            if targetAccount is missing value then error "No enabled Messages account for this service" number {_NO_ACCOUNT_ERROR_NUMBER}'
        )
        return "\n".join(lines)

    def _run_send_script(self, script: str, services: list[str], thread_service: str | None) -> str:
        try:
            output = self._run_script(script)
        except MessagesAutomationBridgeError as exc:
            if exc.error_code != "AUTOMATION_FAILED":
                raise
            if f"({_NO_ACCOUNT_ERROR_NUMBER})" in exc.message:
                raise self._no_account_error(services, thread_service) from exc
            if "-2753" in exc.message and "RCS" in exc.message:
                # Older Messages dictionaries have no RCS service type, so the script
                # stops at account selection, before anything is sent.
                raise MessagesAutomationBridgeError(
                    "SERVICE_UNAVAILABLE",
                    "This Mac's Messages app has no RCS service (RCS sending needs macOS "
                    f"{_RCS_MIN_MACOS} or later). Nothing was sent.",
                    "Retry with service_name='SMS' (needs Text Message Forwarding) or service_name='iMessage'.",
                ) from exc
            raise
        return output.strip() or services[0]

    @staticmethod
    def _no_account_error(services: list[str], thread_service: str | None) -> MessagesAutomationBridgeError:
        wanted = " or ".join(services)
        carrier = any(name in {"SMS", "RCS"} for name in services)
        reason = " (Text Message Forwarding is off or this Mac is not paired with an iPhone)" if carrier else ""
        if thread_service is not None:
            message = (
                f"This thread's last message used {thread_service}, but this Mac has no enabled {wanted} "
                f"account in Messages{reason}. Nothing was sent."
            )
        elif services == [DEFAULT_SERVICE]:
            message = f"This Mac has no enabled {DEFAULT_SERVICE} account in Messages. Nothing was sent."
        else:
            message = (
                f"service_name='{services[0]}' was requested, but this Mac has no enabled {wanted} "
                f"account in Messages{reason}. Nothing was sent."
            )
        suggestion = (
            f"Retry with service_name='iMessage' to send over iMessage instead, or {_ENABLE_FORWARDING} and retry."
            if carrier
            else "Sign in to iMessage in Messages settings on this Mac, then retry."
        )
        return MessagesAutomationBridgeError("SERVICE_UNAVAILABLE", message, suggestion)

    def _run_script(self, script: str) -> str:
        return self._run_command(["osascript", "-e", script], timeout=30)

    def _run_command(self, command: list[str], *, timeout: int) -> str:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise MessagesAutomationBridgeError(
                "AUTOMATION_TIMEOUT", "Messages automation timed out.",
                "Check Messages history before retrying a send; its delivery status may be unknown.",
            ) from exc
        except OSError as exc:
            raise MessagesAutomationBridgeError(
                "OSASCRIPT_UNAVAILABLE",
                f"Could not run 'osascript': {exc}.",
                "This server requires macOS with osascript available.",
            ) from exc
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Messages automation failed."
            lowered = message.lower()
            if "not authorized" in lowered or "-1743" in lowered:
                raise MessagesAutomationBridgeError(
                    "PERMISSION_DENIED",
                    "macOS denied automation access to Messages.",
                    "Allow automation access for the host app or terminal and retry.",
                )
            raise MessagesAutomationBridgeError("AUTOMATION_FAILED", message, "Inspect Messages.app state and retry.")
        return completed.stdout.strip()

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
