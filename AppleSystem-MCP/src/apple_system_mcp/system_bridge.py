from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess

from apple_system_mcp.models import AppRecord, BatteryStatus


@dataclass(frozen=True)
class SystemBridgeError(Exception):
    error_code: str
    message: str
    suggestion: str | None = None


class SystemBridge:
    def _run(self, *command: str, input_text: str | None = None) -> str:
        try:
            result = subprocess.run(
                list(command),
                input=input_text,
                capture_output=True,
                check=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError as exc:
            raise SystemBridgeError("COMMAND_NOT_FOUND", f"Missing command: {command[0]}", "Run this server on macOS.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip()
            raise SystemBridgeError("COMMAND_FAILED", stderr or "System command failed.", "Check macOS privacy permissions and retry.") from exc
        except subprocess.TimeoutExpired as exc:
            raise SystemBridgeError("COMMAND_TIMEOUT", f"System command timed out: {command[0]}", "Retry the request.") from exc
        return result.stdout.strip()

    def battery(self) -> BatteryStatus:
        raw = self._run("pmset", "-g", "batt")
        percentage_match = re.search(r"(\d+)%", raw)
        percentage = int(percentage_match.group(1)) if percentage_match else None
        charging = None
        if "charging" in raw.lower():
            charging = True
        elif "discharging" in raw.lower():
            charging = False
        power_source = "AC Power" if "AC Power" in raw else ("Battery Power" if "Battery Power" in raw else None)
        return BatteryStatus(percentage=percentage, power_source=power_source, charging=charging, raw=raw)

    def frontmost_app(self) -> str:
        return self._run(
            "osascript",
            "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        )

    def running_apps(self) -> list[AppRecord]:
        raw = self._run(
            "osascript",
            "-e",
            'tell application "System Events" to get name of every application process whose background only is false',
        )
        names = [name.strip() for name in raw.split(",") if name.strip()]
        return [AppRecord(name=name) for name in names]

    def get_clipboard(self) -> str:
        return self._run("pbpaste")

    def set_clipboard(self, text: str) -> None:
        self._run("pbcopy", input_text=text)

    def show_notification(self, title: str, body: str, subtitle: str | None = None) -> None:
        escaped_body = body.replace('"', '\\"')
        escaped_title = title.replace('"', '\\"')
        command = [f'display notification "{escaped_body}" with title "{escaped_title}"']
        if subtitle:
            escaped_subtitle = subtitle.replace('"', '\\"')
            command[0] += f' subtitle "{escaped_subtitle}"'
        self._run("osascript", "-e", command[0])

    def open_application(self, application: str) -> None:
        self._run("open", "-a", application)


def build_bridge() -> SystemBridge:
    return SystemBridge()
