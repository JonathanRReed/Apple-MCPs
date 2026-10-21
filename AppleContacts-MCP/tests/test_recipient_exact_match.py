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


def ann(**overrides: object) -> dict[str, object]:
    return {
        **contact_item("ann"),
        "name": "Ann Example",
        "phones": [{"label": "home", "value": "+1 (212) 555-0100"}, {"label": "mobile", "value": "+1 (917) 555-0199"}],
        "emails": [{"label": "home", "value": "ann@home.com"}, {"label": "work", "value": "ann@work.com"}],
        **overrides,
    }


@pytest.mark.parametrize("channel", ["phone", "any"])
def test_resolving_a_phone_returns_that_phone_not_the_first(monkeypatch, channel) -> None:
    bridge = bridge_with(monkeypatch, [ann()])

    recipient = bridge.resolve_message_recipient("917-555-0199", channel=channel)

    assert recipient.contact.contact_id == "ann"
    assert recipient.recipient_kind == "phone"
    assert (recipient.recipient_label, recipient.recipient_value) == ("mobile", "+1 (917) 555-0199")


@pytest.mark.parametrize("channel", ["email", "any"])
def test_resolving_an_email_returns_that_email_ignoring_case(monkeypatch, channel) -> None:
    bridge = bridge_with(monkeypatch, [ann()])

    recipient = bridge.resolve_message_recipient("ANN@work.com", channel=channel)

    assert recipient.recipient_kind == "email"
    assert (recipient.recipient_label, recipient.recipient_value) == ("work", "ann@work.com")


def test_one_number_stored_twice_in_different_forms_is_not_ambiguous(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [ann(phones=[
        {"label": "home", "value": "+1 (212) 555-0100"},
        {"label": "iPhone", "value": "(917) 555-0199"},
        {"label": "mobile", "value": "+1 917 555 0199"},
    ])])

    recipient = bridge.resolve_message_recipient("+19175550199")

    assert recipient.recipient_value == "+1 917 555 0199"


def test_two_different_numbers_of_one_contact_matching_a_query_are_ambiguous(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [ann(phones=[
        {"label": "US", "value": "+1 612 345 6789"},
        {"label": "UK", "value": "+44 612 345 6789"},
    ])])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient("612 345 6789")

    assert error.value.error_code == "AMBIGUOUS_PHONE_NUMBER"


@pytest.mark.parametrize(
    ("stored", "query"),
    [
        # A national number has no country code to leave out, so an area code
        # in front of a 7-digit local number is never skipped.
        ("(212) 555-1234", "555-1234"),
        ("(310) 555-1234", "555-1234"),
        ("555-1234", "(212) 555-1234"),
        ("212 555 1234", "555 1234"),
        # "0" + area code is not a trunk prefix after a country code either.
        ("0212 555 1234", "+212 555 1234"),
        ("0310 555 1234", "555 1234"),
    ],
)
def test_local_number_needs_an_international_number_to_skip_a_country_code(monkeypatch, stored, query) -> None:
    bridge = bridge_with(monkeypatch, [contact_item("other", phone=stored)])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient(query)

    assert error.value.error_code == "CONTACT_NOT_FOUND"


def test_local_number_resolves_to_the_contact_storing_it_locally(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [
        contact_item("new-york", phone="(212) 555-1234"),
        contact_item("los-angeles", phone="(310) 555-1234"),
        contact_item("local", phone="555 1234"),
    ])

    assert bridge.resolve_message_recipient("555-1234").contact.contact_id == "local"


def test_short_code_resolves_only_to_an_exact_owner(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [
        contact_item("contains", phone="+1 555 123 4567"),
        contact_item("owner", phone="12345"),
    ])

    recipient = bridge.resolve_message_recipient("12345")

    assert (recipient.contact.contact_id, recipient.recipient_value) == ("owner", "12345")


def test_short_code_matching_only_part_of_a_number_is_ambiguous(monkeypatch) -> None:
    bridge = bridge_with(monkeypatch, [contact_item("contains", phone="+1 555 123 4567")])

    with pytest.raises(ContactsBridgeError) as error:
        bridge.resolve_message_recipient("1234")

    assert error.value.error_code == "AMBIGUOUS_PHONE_NUMBER"
