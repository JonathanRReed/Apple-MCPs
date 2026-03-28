from apple_contacts_mcp.config import load_settings
from apple_contacts_mcp.models import ContactDetail, ContactMethod
from apple_contacts_mcp import tools


class FakeBridge:
    def permission_diagnostic(self):
        return True, None

    def list_contacts(self):
        return [
            ContactDetail(
                contact_id="contact-1",
                name="Alice Doe",
                first_name="Alice",
                last_name="Doe",
                organization="Example",
                phone_count=1,
                email_count=1,
                phones=[ContactMethod(label="mobile", value="+15551234567")],
                emails=[ContactMethod(label="work", value="alice@example.com")],
                note="Friend",
            )
        ]

    def get_contact(self, contact_id: str):
        return self.list_contacts()[0]

    def search_contacts(self, query: str, limit: int = 25):
        return self.list_contacts()

    def resolve_message_recipient(self, query: str, channel: str = "phone"):
        return tools.ResolvedRecipientResponse(
            contact=self.get_contact("contact-1"),
            recipient_kind="phone",
            recipient_label="mobile",
            recipient_value="+15551234567",
        )


def test_contacts_health_reports_access(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.contacts_health()

    assert result.ok is True
    assert result.contacts_accessible is True


def test_contacts_resolve_message_recipient_returns_value(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.contacts_resolve_message_recipient("Alice")

    assert result.ok is True
    assert result.recipient_value == "+15551234567"


def teardown_function() -> None:
    load_settings.cache_clear()
