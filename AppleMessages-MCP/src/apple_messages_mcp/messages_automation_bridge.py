from __future__ import annotations

import subprocess


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


class MessagesAutomationBridge:
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
    ) -> dict[str, str | bool | None]:
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
        wanted = self._service_preference(service_name, services)
        script = f'''
        tell application "Messages"
{self._account_selection(wanted)}
            set targetParticipant to participant "{self._escape(recipient)}" of targetAccount
            send "{self._escape(text)}" to targetParticipant
            return usedService
        end tell
        '''
        used = self._run_send_script(script, wanted)
        return {
            "sent": True,
            "recipient": recipient,
            "text": text,
            "service_name": used,
        }

    def send_to_group(self, chat_id: str, text: str) -> dict[str, str | bool | None]:
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
    ) -> dict[str, str | bool | None]:
        if not recipient.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "recipient must not be empty", "Provide an explicit iMessage address or phone number.")
        if not file_path.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "file_path must not be empty", "Provide a valid file path.")

        wanted = self._service_preference(service_name, None)
        send_parts = [f'send POSIX file "{self._escape(file_path)}" to targetParticipant']
        if text and text.strip():
            send_parts.append(f'send "{self._escape(text)}" to targetParticipant')

        script = f'''
        tell application "Messages"
{self._account_selection(wanted)}
            set targetParticipant to participant "{self._escape(recipient)}" of targetAccount
            {chr(10).join(send_parts)}
            return usedService
        end tell
        '''
        used = self._run_send_script(script, wanted)
        return {
            "sent": True,
            "recipient": recipient,
            "file_path": file_path,
            "text": text,
            "service_name": used,
        }

    @staticmethod
    def _service_preference(service_name: str | None, services: list[str] | None) -> list[str]:
        explicit = normalize_service_name(service_name)
        if explicit is not None:
            return [explicit]
        preferred = [name for name in (normalize_service_name(item) for item in services or []) if name]
        return preferred or [DEFAULT_SERVICE]

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

    def _run_send_script(self, script: str, services: list[str]) -> str:
        try:
            output = self._run_script(script)
        except MessagesAutomationBridgeError as exc:
            if exc.error_code == "AUTOMATION_FAILED" and f"({_NO_ACCOUNT_ERROR_NUMBER})" in exc.message:
                wanted = " or ".join(services)
                suggestion = (
                    "Turn on Text Message Forwarding for this Mac on the iPhone (Settings > Apps > Messages), "
                    "or send as iMessage."
                    if any(name in {"SMS", "RCS"} for name in services)
                    else "Sign in to iMessage in Messages settings on this Mac."
                )
                raise MessagesAutomationBridgeError(
                    "SERVICE_UNAVAILABLE", f"This Mac has no enabled {wanted} account in Messages.", suggestion
                ) from exc
            raise
        return output.strip() or services[0]

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
