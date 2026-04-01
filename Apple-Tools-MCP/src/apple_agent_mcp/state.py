from __future__ import annotations

from pathlib import Path
import json

from apple_agent_mcp.models import AssistantActionRecord, AssistantPreferences


class StateStoreError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


def load_preferences(path: Path) -> AssistantPreferences:
    if not path.exists():
        return AssistantPreferences()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateStoreError(
            "STATE_READ_FAILED",
            f"Failed to read assistant preferences from '{path}'.",
            "Check filesystem permissions and retry.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise StateStoreError(
            "STATE_INVALID_JSON",
            f"Assistant preferences file at '{path}' is invalid JSON: {exc.msg}.",
            "Fix or delete the preferences file, then retry.",
        ) from exc
    if not isinstance(payload, dict):
        raise StateStoreError(
            "STATE_INVALID_SHAPE",
            f"Assistant preferences file at '{path}' must contain a JSON object.",
            "Fix or delete the preferences file, then retry.",
        )
    try:
        return AssistantPreferences.model_validate(payload)
    except Exception as exc:
        raise StateStoreError(
            "STATE_INVALID_SHAPE",
            f"Assistant preferences file at '{path}' does not match the expected schema.",
            "Fix or delete the preferences file, then retry.",
        ) from exc


def save_preferences(path: Path, preferences: AssistantPreferences) -> AssistantPreferences:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(preferences.model_dump(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise StateStoreError(
            "STATE_WRITE_FAILED",
            f"Failed to write assistant preferences to '{path}'.",
            "Check filesystem permissions and retry.",
        ) from exc
    return preferences


def load_action_history(path: Path) -> list[AssistantActionRecord]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateStoreError(
            "STATE_READ_FAILED",
            f"Failed to read assistant action history from '{path}'.",
            "Check filesystem permissions and retry.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise StateStoreError(
            "STATE_INVALID_JSON",
            f"Assistant action history file at '{path}' is invalid JSON: {exc.msg}.",
            "Fix or delete the action history file, then retry.",
        ) from exc
    if not isinstance(payload, list):
        raise StateStoreError(
            "STATE_INVALID_SHAPE",
            f"Assistant action history file at '{path}' must contain a JSON array.",
            "Fix or delete the action history file, then retry.",
        )
    try:
        return [AssistantActionRecord.model_validate(item) for item in payload]
    except Exception as exc:
        raise StateStoreError(
            "STATE_INVALID_SHAPE",
            f"Assistant action history file at '{path}' does not match the expected schema.",
            "Fix or delete the action history file, then retry.",
        ) from exc


def save_action_history(path: Path, actions: list[AssistantActionRecord]) -> list[AssistantActionRecord]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([action.model_dump() for action in actions], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise StateStoreError(
            "STATE_WRITE_FAILED",
            f"Failed to write assistant action history to '{path}'.",
            "Check filesystem permissions and retry.",
        ) from exc
    return actions
