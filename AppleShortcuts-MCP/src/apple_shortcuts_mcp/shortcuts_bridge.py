from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess

from apple_shortcuts_mcp.config import load_settings
from apple_shortcuts_mcp.models import ShortcutArtifact, ShortcutFolderInfo, ShortcutInfo, ShortcutRunResponse

UUID_PATTERN = re.compile(r"^(?P<name>.+?)\s+\((?P<identifier>[0-9A-Fa-f-]{36})\)$")


class ShortcutsBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


@dataclass(frozen=True)
class ShortcutCLIResult:
    returncode: int
    stdout: str
    stderr: str


class ShortcutsBridge:
    def __init__(self, shortcuts_command: str | None = None, timeout_seconds: int | None = None) -> None:
        settings = load_settings()
        self.shortcuts_command = shortcuts_command or settings.shortcuts_command
        self.timeout_seconds = timeout_seconds or settings.command_timeout_seconds

    def cli_available(self) -> bool:
        return shutil.which(self.shortcuts_command) is not None

    def list_folders(self) -> list[ShortcutFolderInfo]:
        output = self._run_cli(["list", "--folders"])
        folders = [line.strip() for line in self._split_lines(output.stdout)]
        items = [ShortcutFolderInfo(folder_name=folder, shortcut_count=len(self.list_shortcuts(folder_name=folder))) for folder in folders]
        return items

    def list_shortcuts(self, folder_name: str | None = None) -> list[ShortcutInfo]:
        args = ["list", "--show-identifiers"]
        if folder_name is not None:
            args.extend(["--folder-name", folder_name])
        output = self._run_cli(args)
        items: list[ShortcutInfo] = []
        for line in self._split_lines(output.stdout):
            parsed = self._parse_shortcut_line(line)
            if parsed is not None:
                items.append(parsed)
        return items

    def view_shortcut(self, shortcut_name_or_identifier: str) -> ShortcutInfo:
        shortcut = self.resolve_shortcut(shortcut_name_or_identifier)
        output = self._run_cli(["view", shortcut.name])
        if output.returncode != 0:
            raise self._map_error("view", output)
        return shortcut

    def run_shortcut(
        self,
        shortcut_name_or_identifier: str,
        input_paths: list[str] | None = None,
        output_path: str | None = None,
        output_type: str | None = None,
        input_text: str | None = None,
    ) -> ShortcutRunResponse:
        shortcut = self.resolve_shortcut(shortcut_name_or_identifier)
        args = ["run", shortcut.identifier or shortcut.name]
        for path in input_paths or []:
            args.extend(["--input-path", path])
        if output_path is not None:
            args.extend(["--output-path", output_path])
        if output_type is not None:
            args.extend(["--output-type", output_type])

        output = self._run_cli(args, input_data=input_text)
        if output.returncode != 0:
            raise self._map_error("run", output)

        artifacts: list[ShortcutArtifact] = []
        if output_path is not None:
            artifact_path = Path(output_path)
            artifacts.append(
                ShortcutArtifact(
                    path=str(artifact_path),
                    exists=artifact_path.exists(),
                    kind="file",
                    size_bytes=artifact_path.stat().st_size if artifact_path.exists() else None,
                )
            )
        return ShortcutRunResponse(
            shortcut_name=shortcut.name,
            shortcut_identifier=shortcut.identifier,
            exit_code=output.returncode,
            stdout=output.stdout.rstrip(),
            stderr=output.stderr.rstrip(),
            artifacts=artifacts,
        )

    def resolve_shortcut(self, shortcut_name_or_identifier: str) -> ShortcutInfo:
        if self._looks_like_identifier(shortcut_name_or_identifier):
            matching = [item for item in self.list_shortcuts() if item.identifier == shortcut_name_or_identifier]
            if not matching:
                raise ShortcutsBridgeError(
                    "SHORTCUT_NOT_FOUND",
                    f"Shortcut '{shortcut_name_or_identifier}' was not found.",
                    "Run shortcuts_list_shortcuts to discover valid shortcut identifiers.",
                )
            return matching[0]

        matching = [item for item in self.list_shortcuts() if item.name == shortcut_name_or_identifier]
        if len(matching) == 1:
            return matching[0]
        if len(matching) > 1:
            raise ShortcutsBridgeError(
                "SHORTCUT_AMBIGUOUS",
                f"Shortcut name '{shortcut_name_or_identifier}' matched multiple shortcuts.",
                "Pass a shortcut identifier instead of a duplicated name.",
            )

        case_insensitive = [item for item in self.list_shortcuts() if item.name.lower() == shortcut_name_or_identifier.lower()]
        if len(case_insensitive) == 1:
            return case_insensitive[0]
        if len(case_insensitive) > 1:
            raise ShortcutsBridgeError(
                "SHORTCUT_AMBIGUOUS",
                f"Shortcut name '{shortcut_name_or_identifier}' matched multiple shortcuts.",
                "Pass a shortcut identifier instead of a duplicated name.",
            )

        raise ShortcutsBridgeError(
            "SHORTCUT_NOT_FOUND",
            f"Shortcut '{shortcut_name_or_identifier}' was not found.",
            "Run shortcuts_list_shortcuts to discover valid shortcut names and identifiers.",
        )

    def shortcuts_snapshot(self) -> dict[str, object]:
        folders = self.list_folders()
        shortcuts = self.list_shortcuts()
        return {
            "folders": [folder.model_dump() for folder in folders],
            "shortcuts": [shortcut.model_dump() for shortcut in shortcuts],
            "count": len(shortcuts),
        }

    def shortcuts_folder_snapshot(self, folder_name: str) -> dict[str, object]:
        shortcuts = self.list_shortcuts(folder_name=folder_name)
        return {
            "folder_name": folder_name,
            "shortcuts": [shortcut.model_dump() for shortcut in shortcuts],
            "count": len(shortcuts),
        }

    def _run_cli(self, args: list[str], input_data: str | None = None) -> ShortcutCLIResult:
        if not self.cli_available():
            raise ShortcutsBridgeError(
                "SHORTCUTS_CLI_NOT_FOUND",
                f"Command '{self.shortcuts_command}' was not found.",
                "Install or expose the official shortcuts CLI in PATH.",
            )

        try:
            completed = subprocess.run(
                [self.shortcuts_command, *args],
                input=input_data,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ShortcutsBridgeError(
                "CLI_TIMEOUT",
                f"Command '{self.shortcuts_command} {' '.join(args)}' timed out.",
                "Increase the timeout or simplify the shortcut.",
            ) from exc

        result = ShortcutCLIResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
        if result.returncode != 0:
            raise self._map_error(args[0], result)
        return result

    def _map_error(self, command: str, output: ShortcutCLIResult) -> ShortcutsBridgeError:
        text = (output.stderr or output.stdout or f"shortcuts {command} failed.").strip()
        lowered = text.lower()

        if "could not be processed" in lowered or "input" in lowered:
            return ShortcutsBridgeError(
                "SHORTCUT_INPUT_FAILED",
                text,
                "Check the shortcut's input types or provide a compatible input path.",
            )
        if "could not be found" in lowered or "not found" in lowered:
            return ShortcutsBridgeError(
                "SHORTCUT_NOT_FOUND",
                text,
                "Run shortcuts_list_shortcuts to discover valid names and identifiers.",
            )
        if "automation" in lowered or "permission" in lowered:
            return ShortcutsBridgeError(
                "PERMISSION_DENIED",
                text,
                "Allow automation access for the process that runs this MCP server.",
            )
        return ShortcutsBridgeError(
            "SHORTCUT_RUN_FAILED",
            text,
            "Inspect the shortcut in the Shortcuts app and retry.",
        )

    def _parse_shortcut_line(self, line: str) -> ShortcutInfo | None:
        text = line.strip()
        if not text:
            return None
        match = UUID_PATTERN.match(text)
        if match is not None:
            return ShortcutInfo(name=match.group("name"), identifier=match.group("identifier"))
        return ShortcutInfo(name=text)

    def _split_lines(self, raw: str) -> list[str]:
        return [line for line in raw.splitlines() if line.strip()]

    def _looks_like_identifier(self, value: str) -> bool:
        return bool(UUID_PATTERN.match(f"Shortcut ({value})"))
