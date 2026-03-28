from datetime import datetime
from typing import NamedTuple


class EventIdentity(NamedTuple):
    calendar_name: str
    uid: str


def _local_tzinfo():
    return datetime.now().astimezone().tzinfo


def parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_local_tzinfo())
    return parsed


def datetime_to_iso(value: datetime) -> str:
    return value.astimezone().isoformat(timespec="seconds")


def iso_to_epoch_seconds(value: str) -> int:
    return int(parse_iso_datetime(value).timestamp())


def epoch_seconds_to_iso(value: int | float) -> str:
    return datetime.fromtimestamp(float(value), tz=_local_tzinfo()).isoformat(timespec="seconds")


def build_event_id(calendar_name: str, uid: str) -> str:
    return f"uid:{calendar_name}:{uid}"


def parse_event_id(value: str) -> EventIdentity:
    if not value.startswith("uid:"):
        raise ValueError("event_id must start with 'uid:'")
    remainder = value[4:]
    parts = remainder.split(":")
    if len(parts) < 2:
        raise ValueError("event_id must include calendar name and uid")
    calendar_name = ":".join(parts[:-1]).strip()
    uid = parts[-1].strip()
    if not calendar_name or not uid:
        raise ValueError("event_id must include non-empty calendar name and uid")
    return EventIdentity(calendar_name=calendar_name, uid=uid)
