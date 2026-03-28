from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.models import ReminderDetail, ReminderListInfo
from apple_reminders_mcp import tools


class FakeBridge:
    def list_lists(self):
        return [
            ReminderListInfo(
                list_id="list-1",
                title="Chores",
                source_title="iCloud",
                allows_content_modifications=True,
                color_hex="#D9A69F",
            )
        ]

    def list_reminders(self, **kwargs):
        return []

    def get_reminder(self, reminder_id: str) -> ReminderDetail:
        return ReminderDetail(
            reminder_id=reminder_id,
            title="Trash day",
            list_id="list-1",
            list_name="Chores",
            due_date="2026-03-28T22:30:00Z",
            due_all_day=False,
            remind_at="2026-03-28T22:30:00Z",
            priority=1,
            completed=False,
            completion_date=None,
            notes="Bring bins in",
            creation_date="2026-03-20T10:00:00Z",
            modification_date="2026-03-27T10:00:00Z",
        )

    def create_reminder(self, **kwargs) -> ReminderDetail:
        return self.get_reminder("x-apple-reminder://new")

    def update_reminder(self, reminder_id: str, **kwargs) -> ReminderDetail:
        return self.get_reminder(reminder_id)

    def set_completed(self, reminder_id: str, completed: bool) -> ReminderDetail:
        detail = self.get_reminder(reminder_id)
        detail.completed = completed
        return detail

    def delete_reminder(self, reminder_id: str) -> bool:
        return True


def test_create_reminder_returns_structured_payload(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_REMINDERS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.reminders_create_reminder(title="Trash day", list_id="list-1")

    assert result.ok is True
    assert result.reminder.list_name == "Chores"


def test_list_reminders_rejects_bad_limit(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_REMINDERS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.reminders_list_reminders(limit=0)

    assert result.ok is False
    assert result.error.error_code == "INVALID_INPUT"


def test_reminders_main_exists() -> None:
    assert callable(tools.main)


def test_list_reminders_accepts_string_limit(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_REMINDERS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.reminders_list_reminders(limit="5")

    assert result.ok is True


def test_create_reminder_accepts_string_priority(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_REMINDERS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.reminders_create_reminder(title="Trash day", list_id="list-1", priority="2")

    assert result.ok is True


def teardown_function() -> None:
    load_settings.cache_clear()
