from __future__ import annotations

import subprocess


class MessagesAutomationBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class MessagesAutomationBridge:
    def automation_accessible(self) -> bool:
        accessible, _ = self.automation_access_diagnostic()
        return accessible

    def automation_access_diagnostic(self) -> tuple[bool, MessagesAutomationBridgeError | None]:
        try:
            self._run_script('tell application "Messages" to count of every service')
            return True, None
        except MessagesAutomationBridgeError as exc:
            return False, exc

    def send_message(self, recipient: str, text: str, service_name: str | None = None) -> dict[str, str | bool | None]:
        if not recipient.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "recipient must not be empty", "Provide an explicit iMessage address or phone number.")
        if not text.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "text must not be empty", "Provide a non-empty message body.")

        if service_name:
            script = f'''
            tell application "Messages"
                set targetService to first service whose name is "{self._escape(service_name)}"
                set targetBuddy to buddy "{self._escape(recipient)}" of targetService
                send "{self._escape(text)}" to targetBuddy
            end tell
            '''
        else:
            script = f'''
            tell application "Messages"
                set targetService to first service whose service type = iMessage
                set targetBuddy to buddy "{self._escape(recipient)}" of targetService
                send "{self._escape(text)}" to targetBuddy
            end tell
            '''
        self._run_script(script)
        return {
            "sent": True,
            "recipient": recipient,
            "text": text,
            "service_name": service_name or "iMessage",
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

    def send_attachment(self, recipient: str, file_path: str, text: str | None = None) -> dict[str, str | bool | None]:
        if not recipient.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "recipient must not be empty", "Provide an explicit iMessage address or phone number.")
        if not file_path.strip():
            raise MessagesAutomationBridgeError("INVALID_INPUT", "file_path must not be empty", "Provide a valid file path.")

        send_parts = [f'send POSIX file "{self._escape(file_path)}" to targetBuddy']
        if text and text.strip():
            send_parts.append(f'send "{self._escape(text)}" to targetBuddy')

        script = f'''
        tell application "Messages"
            set targetService to first service whose service type = iMessage
            set targetBuddy to buddy "{self._escape(recipient)}" of targetService
            {chr(10).join(send_parts)}
        end tell
        '''
        self._run_script(script)
        return {
            "sent": True,
            "recipient": recipient,
            "file_path": file_path,
            "text": text,
        }

    def _run_script(self, script: str) -> str:
        completed = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Messages automation failed."
            lowered = message.lower()
            if "not authorized" in lowered or "automation" in lowered:
                raise MessagesAutomationBridgeError(
                    "PERMISSION_DENIED",
                    "macOS denied automation access to Messages.",
                    "Allow automation access for the host app or terminal and retry.",
                )
            raise MessagesAutomationBridgeError("AUTOMATION_FAILED", message, "Inspect Messages.app state and retry.")
        return completed.stdout.strip()

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
