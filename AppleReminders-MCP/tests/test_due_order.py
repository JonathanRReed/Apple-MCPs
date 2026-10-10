import os
import time

import pytest

from apple_reminders_mcp import tools
from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.models import ReminderListInfo, ReminderSummary


@pytest.mark.parametrize(
    "zone,all_day,timed,expected",
    [
        ("America/New_York", "2026-03-08", "2026-03-08T04:30:00Z", "timed"),
        ("America/New_York", "2026-03-09", "2026-03-09T04:30:00Z", "all-day"),
        ("America/New_York", "2026-11-01", "2026-11-01T04:30:00Z", "all-day"),
        ("America/New_York", "2026-11-02", "2026-11-02T04:30:00Z", "timed"),
        ("Europe/Berlin", "2026-03-30", "2026-03-29T22:30:00Z", "all-day"),
    ],
)
def test_scoped_cross_list_limit_uses_local_midnight_and_due_date_dst(monkeypatch, zone, all_day, timed, expected):
    previous = os.environ.get("TZ")
    monkeypatch.setenv("TZ", zone)
    time.tzset()
    monkeypatch.setenv("APPLE_REMINDERS_MCP_ALLOWED_LISTS", "A,B")
    load_settings.cache_clear()

    class Bridge:
        def list_lists(self):
            return [ReminderListInfo(list_id=n, title=n, allows_content_modifications=True) for n in ("A", "B")]

        def list_reminders(self, list_id, limit, **kw):
            assert limit == 1
            return [
                ReminderSummary(
                    reminder_id="all-day" if list_id == "A" else "timed", title="Due", list_id=list_id, list_name=list_id, due_date=all_day if list_id == "A" else timed, due_all_day=list_id == "A"
                )
            ]

    monkeypatch.setattr(tools, "_bridge", lambda: Bridge())
    try:
        assert [r.reminder_id for r in tools._scoped_reminders(limit=1)] == [expected]
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()
        load_settings.cache_clear()
