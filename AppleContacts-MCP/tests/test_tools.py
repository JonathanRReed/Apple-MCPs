from apple_contacts_mcp.config import load_settings
from apple_contacts_mcp.models import ContactDetail, ContactMethod, DuplicateCandidateGroup, DuplicateEvidence
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

    def create_contact(self, **kwargs):
        return tools.CreateContactResponse(contact_id="contact-2", name="Test User", created=True)

    def update_contact(self, contact_id: str, **kwargs):
        contact = self.get_contact(contact_id)
        contact.first_name = kwargs.get("first_name") or contact.first_name
        contact.note = kwargs.get("note") or contact.note
        return contact

    def delete_contact(self, contact_id: str):
        return tools.DeleteContactResponse(contact_id=contact_id, deleted=True)


def test_contacts_health_reports_access(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.contacts_health()

    assert result.ok is True
    assert result.contacts_accessible is True
    assert "create_contact" not in result.capabilities
    assert "delete_contact" not in result.capabilities
    assert "find_duplicates" in result.capabilities


def test_contacts_health_respects_safety_mode(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    manage = tools.contacts_health()

    assert "create_contact" in manage.capabilities
    assert "update_contact" in manage.capabilities
    assert "delete_contact" not in manage.capabilities

    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()

    full = tools.contacts_health()

    assert "delete_contact" in full.capabilities


def test_contacts_resolve_message_recipient_returns_value(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.contacts_resolve_message_recipient("Alice")

    assert result.ok is True
    assert result.recipient_value == "+15551234567"


def test_contacts_create_update_and_delete(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    created = tools.contacts_create_contact(first_name="Test", last_name="User", note="Created by test")
    updated = tools.contacts_update_contact("contact-1", first_name="Alicia", note="Updated by test")
    deleted = tools.contacts_delete_contact("contact-1")

    assert created.ok is True
    assert created.contact_id == "contact-2"
    assert updated.ok is True
    assert updated.contact.first_name == "Alicia"
    assert deleted.ok is True
    assert deleted.deleted is True


def test_contacts_create_and_update_accept_methods(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class RecordingBridge(FakeBridge):
        def create_contact(self, **kwargs):
            captured["create"] = kwargs
            return super().create_contact(**kwargs)

        def update_contact(self, contact_id: str, **kwargs):
            captured["update"] = {"contact_id": contact_id, **kwargs}
            return super().update_contact(contact_id, **kwargs)

    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: RecordingBridge())

    phone = ContactMethod(label="mobile", value="+15551234567")
    email = ContactMethod(label="work", value="alice@example.com")
    tools.contacts_create_contact(first_name="Alice", phones=[phone], emails=[email])
    tools.contacts_update_contact("contact-1", phones=[phone], emails=[email])

    assert captured["create"]["phones"][0].value == "+15551234567"
    assert captured["create"]["emails"][0].value == "alice@example.com"
    assert captured["update"]["phones"][0].label == "mobile"
    assert captured["update"]["emails"][0].label == "work"


def test_contacts_find_duplicates_tool(monkeypatch) -> None:
    class DuplicateBridge(FakeBridge):
        def find_duplicates(self):
            return [
                DuplicateCandidateGroup(
                    duplicate_group_id="dup-1",
                    confidence=0.96,
                    evidence=[DuplicateEvidence(kind="email", value="jonathan@example.com")],
                    contacts=self.list_contacts(),
                    merge_recommended=True,
                )
            ]

        def suggest_merge_candidates(self, query: str | None = None):
            return self.find_duplicates()

    monkeypatch.setenv("APPLE_CONTACTS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: DuplicateBridge())

    result = tools.contacts_find_duplicates()
    filtered = tools.contacts_suggest_merge_candidates("alice")

    assert result.ok is True
    assert result.count == 1
    assert result.groups[0].merge_recommended is True
    assert filtered.ok is True


def teardown_function() -> None:
    load_settings.cache_clear()
