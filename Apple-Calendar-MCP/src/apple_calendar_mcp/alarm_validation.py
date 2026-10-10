import math
from datetime import datetime

from apple_calendar_mcp.utils import parse_iso_datetime

# Keep these limits identical to the native eventAlarms validator.
MAX_ALARM_MINUTES = 525600
MAX_EVENT_ALARMS = 100


def coerce_alarm_minutes(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError("minutes_before must be a number")
    try:
        minutes = float(value.strip()) if isinstance(value, str) else float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("minutes_before must be a number") from exc
    if not math.isfinite(minutes):
        raise ValueError("minutes_before must be a number")
    if minutes < 0:
        raise ValueError("minutes_before must be zero or greater")
    if minutes > MAX_ALARM_MINUTES:
        raise ValueError(f"minutes_before must be at most {MAX_ALARM_MINUTES}")
    if not minutes.is_integer():
        raise ValueError("minutes_before must be a whole number of minutes")
    return minutes


def validate_alarms(alarms: object) -> list[dict[str, object]] | None:
    if alarms is None:
        return None
    if not isinstance(alarms, list):
        raise ValueError("alarms must be a list")
    if len(alarms) > MAX_EVENT_ALARMS:
        raise ValueError(f"alarms must contain at most {MAX_EVENT_ALARMS} entries")
    normalized: list[dict[str, object]] = []
    for entry in alarms:
        if not isinstance(entry, dict):
            raise ValueError("each alarm must be an object with minutes_before or absolute_iso")
        if set(entry) not in ({"minutes_before"}, {"absolute_iso"}):
            raise ValueError("each alarm must have exactly one of minutes_before or absolute_iso")
        if "minutes_before" in entry:
            normalized.append({"minutes_before": coerce_alarm_minutes(entry["minutes_before"])})
        else:
            value = entry["absolute_iso"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("absolute_iso must be a non-empty ISO datetime string")
            explicit = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if explicit.tzinfo is None or explicit.utcoffset() is None:
                raise ValueError("absolute_iso requires an explicit UTC Z or timezone offset")
            absolute = parse_iso_datetime(value)
            normalized.append({"absolute_iso": absolute.isoformat(timespec="seconds")})
    return normalized
