from pathlib import Path

import pytest

from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError
from apple_contacts_mcp.models import ContactMethod


def contact_item(contact_id: str, *, phone: str = "", email: str = "") -> dict[str, object]:
    phones = [{"label": "mobile", "value": phone}] if phone else []
    emails = [{"label": "work", "value": email}] if email else []
    return {
        "contact_id": contact_id,
        "name": f"Person {contact_id}",
        "first_name": "Person",
        "last_name": contact_id,
        "organization": "",
        "phone_count": len(phones),
        "email_count": len(emails),
        "phones": phones,
        "emails": emails,
    }


def bridge_with(monkeypatch, directory: list[dict[str, object]]) -> AppleContactsBridge:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "search_contacts.applescript":
            return {"items": []}
        if script_name == "get_contact.applescript":
            return {"found": True, "contact": next({**item, "note": ""} for item in directory if item["contact_id"] == args[0])}
        limit, offset = map(int, args)
        return {"items": directory[offset : offset + limit], "total": len(directory)}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    return bridge


def test_exact_email_owner_wins_over_containing_address(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [
        contact_item("longer", email="xann@example.com"),
        contact_item("owner", email="ann@example.com"),
    ])

    recipient = bridge.resolve_message_recipient("ann@example.com", channel="email")

    assert recipient.contact.contact_id == "owner"
    assert recipient.recipient_value == "ann@example.com"


def test_email_without_exact_owner_is_not_found(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [contact_item("longer", email="xann@example.com")])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient("ann@example.com", channel="email")

    assert error.value.error_code == "CONTACT_NOT_FOUND"


def test_phone_exact_owner_wins_over_longer_number(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [
        contact_item("longer", phone="+1 555 123 45678"),
        contact_item("owner", phone="+1 555 123 4567"),
    ])

    assert bridge.resolve_message_recipient("5551234567").contact.contact_id == "owner"


def test_phone_without_exact_owner_is_not_found(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [contact_item("longer", phone="+1 555 123 45678")])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient("5551234567")

    assert error.value.error_code == "CONTACT_NOT_FOUND"


@pytest.mark.parametrize(
    ("stored", "query"),
    [
        # Spanish
        ("+34 612 345 678", "612345678"),
        ("612 345 678", "+34 612 345 678"),
        ("612 345 678", "0034612345678"),
        ("+34 612 345 678", "0034 612 345 678"),
        # UK, including the trunk zero in both directions
        ("+44 20 7946 0958", "020 7946 0958"),
        ("+44 (0)20 7946 0958", "20 7946 0958"),
        ("020 7946 0958", "+44 20 7946 0958"),
        ("+44 20 7946 0958", "0044 20 7946 0958"),
        ("20 7946 0958", "+44 (0)20 7946 0958"),
        # US
        ("+1 (555) 123-4567", "5551234567"),
        ("(555) 123-4567", "+1 555 123 4567"),
        ("(555) 123-4567", "001 555 123 4567"),
        ("+1 (555) 123-4567", "555-1234567"),
    ],
)
def test_phone_forms_match_in_both_directions(monkeypatch, stored, query) -> None:
    bridge = bridge_with(monkeypatch, [contact_item("owner", phone=stored)])

    assert bridge.resolve_message_recipient(query).contact.contact_id == "owner"


@pytest.mark.parametrize(
    ("stored", "query"),
    [
        # Different area code: the leading digits are not a country calling code.
        ("+1 (555) 123-4567", "9991234567"),
        ("+1 (555) 123-4567", "1234567"),
        ("+44 20 7946 0958", "161 7946 0958"),
        ("+34 612 345 678", "1612345678"),
        # Unassigned prefix.
        ("+999 612 345 678", "612345678"),
        ("0999 612 345 678", "612345678"),
        # A trunk zero is only accepted directly after a country code.
        ("+44 0 0 20 7946 0958", "20 7946 0958"),
    ],
)
def test_phone_with_other_prefix_does_not_match(monkeypatch, stored, query) -> None:
    bridge = bridge_with(monkeypatch, [contact_item("other", phone=stored)])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient(query)

    assert error.value.error_code == "CONTACT_NOT_FOUND"


def test_phone_in_different_area_code_resolves_to_its_own_owner(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [
        contact_item("other", phone="+1 (999) 123-4567"),
        contact_item("owner", phone="+1 (555) 123-4567"),
    ])

    assert bridge.resolve_message_recipient("+1 555 123 4567").contact.contact_id == "owner"


def test_two_exact_owners_are_ambiguous(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [
        contact_item("a", phone="+34 612 345 678"),
        contact_item("b", phone="612345678"),
    ])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient("612345678")

    assert error.value.error_code == "AMBIGUOUS_CONTACT"


@pytest.mark.parametrize("field", ["phones", "emails"])
@pytest.mark.parametrize("value", ["", "   "])
def test_update_contact_refuses_blank_method_value(monkeypatch, field, value) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    monkeypatch.setattr(bridge, "_run_script", lambda *args: pytest.fail("script must not run"))

    with pytest.raises(ContactsBridgeError) as error:
        bridge.update_contact("contact-1", **{field: [ContactMethod(label="mobile", value=value)]})

    assert error.value.error_code == "INVALID_INPUT"
