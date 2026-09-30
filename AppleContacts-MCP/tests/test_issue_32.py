"""Coverage authored for issue #32; live deletion needs macOS validation."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "apple_contacts_mcp" / "applescripts"


@pytest.mark.parametrize("query", ["Nobody Here", "Studio54", "Person 123", "東京", "alice.example.com", "Studio54 ext5", "Person 123 ext5", "ext 5", "x5"])
def test_no_match_name_does_not_scan_contact_directory(monkeypatch, query) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "search_contacts.applescript"
        return {"items": []}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    assert bridge.search_contacts(query) == []


@pytest.mark.parametrize("query", ["+", "---", "()", "."])
def test_non_method_query_does_not_scan_contact_directory(monkeypatch, query) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        raise AssertionError(f"Unexpected directory scan: {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    assert bridge.search_contacts(query) == []


@pytest.mark.parametrize(
    ("query", "phone", "email"),
    [
        ("+1 (555) 123-4567", "+1 (555) 123-4567", ""),
        ("123-4567", "+1 (555) 123-4567", ""),
        ("alice@example.com", "", "alice@example.com"),
        ("@example.com", "", "alice@example.com"),
    ],
)
def test_method_queries_keep_directory_fallback(monkeypatch, query, phone, email) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "search_contacts.applescript":
            return {"items": []}
        assert script_name == "list_contacts.applescript"
        return {"total": 1, "items": [{
            "contact_id": "contact-1",
            "name": "Example Person",
            "phones": [{"label": "mobile", "value": phone}] if phone else [],
            "emails": [{"label": "work", "value": email}] if email else [],
        }]}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    assert [contact.contact_id for contact in bridge.search_contacts(query)] == ["contact-1"]


def install_finished_process(monkeypatch, output: str) -> None:
    class FinishedProcess:
        returncode = 0

        def poll(self) -> int:
            return 0

    def fake_popen(command, *, stdout, stderr):
        stdout.write(output.encode("utf-8"))
        return FinishedProcess()

    monkeypatch.setattr("apple_contacts_mcp.contacts_bridge.subprocess.Popen", fake_popen)


@pytest.mark.parametrize("control_code", range(32))
def test_run_script_preserves_literal_string_controls_and_complex_emoji(monkeypatch, control_code) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    value = "before" + chr(control_code) + "after 👩🏽‍💻 👨‍👩‍👧‍👦 🇺🇸 e\u0301"
    install_finished_process(monkeypatch, '{"text":"' + value + '"}')

    payload = bridge._run_script("get_contact.applescript", "contact-1")

    assert payload["text"] == value
    assert json.loads(json.dumps(payload))["text"] == value


def test_run_script_preserves_existing_json_escapes(monkeypatch) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    value = 'tab\tline\nquote"backslash\\literal\\n 👩🏽‍💻'
    install_finished_process(monkeypatch, json.dumps({"text": value}, ensure_ascii=False))

    assert bridge._run_script("get_contact.applescript", "contact-1")["text"] == value


@pytest.mark.parametrize("output", ['{"text":\x01}', '{"text":"unescaped " quote"}', "{}junk", "[]"])
def test_run_script_still_rejects_invalid_json_or_non_objects(monkeypatch, output) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    install_finished_process(monkeypatch, output)

    with pytest.raises(ContactsBridgeError) as exc_info:
        bridge._run_script("get_contact.applescript", "contact-1")

    assert exc_info.value.error_code == "INVALID_SCRIPT_OUTPUT"


def test_delete_contact_resolves_repeat_reference_before_delete() -> None:
    source = (SCRIPTS_DIR / "delete_contact.applescript").read_text()
    assert "set targetPerson to contents of thePerson" in source
    assert "set targetPerson to thePerson\n" not in source
    assert source.index("set targetPerson to contents of thePerson") < source.index("delete targetPerson")


@pytest.mark.parametrize("query", [
    "555-1234 ext 5", "555-1234 EXT. 5", "555-1234 extension 5",
    "555-1234 extn. 5", "555-1234 x5", "555-1234 #5",
    "555-1234;ext=5", "tel:555-1234;ext=5",
])
def test_phone_extensions_reach_method_scan_and_recipient_resolution(monkeypatch, query) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    contact = {
        "contact_id": "contact-extension",
        "name": "Example Person",
        "phones": [{"label": "work", "value": "555-1234 x5"}],
        "emails": [],
    }
    calls = []

    def fake_run_script(script_name, *args):
        calls.append(script_name)
        if script_name == "search_contacts.applescript":
            return {"items": []}
        if script_name == "list_contacts.applescript":
            return {"total": 1, "items": [contact]}
        assert script_name == "get_contact.applescript"
        return {"found": True, "contact": contact}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    assert [result.contact_id for result in bridge.search_contacts(query)] == ["contact-extension"]
    resolved = bridge.resolve_message_recipient(query, channel="phone")
    assert resolved.contact.contact_id == "contact-extension"
    assert resolved.recipient_value == "555-1234 x5"
    assert "list_contacts.applescript" in calls


@pytest.mark.parametrize("query", ["+ ext5", "ext5", "#5", "555-1234 ext", "555-1234 extno 5"])
def test_incomplete_or_non_numeric_extension_queries_do_not_scan_directory(monkeypatch, query) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)

    def fake_run_script(script_name, *args):
        assert script_name == "search_contacts.applescript"
        return {"items": []}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    assert bridge.search_contacts(query) == []


@pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("osacompile") is None,
    reason="osacompile is only available on macOS",
)
def test_contacts_delete_script_compiles(tmp_path) -> None:
    script_path = SCRIPTS_DIR / "delete_contact.applescript"
    completed = subprocess.run(
        ["osacompile", "-o", str(tmp_path / "delete_contact.scpt"), str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


@pytest.mark.parametrize("query", ["555-1234 x5", "555-1234 ext. 5", "555-1234;ext=5"])
def test_extension_query_does_not_match_concatenated_number_or_other_extension(monkeypatch, query) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)

    def fake_run_script(script_name, *args):
        assert script_name == "list_contacts.applescript"
        return {"total": 3, "items": [
            {"contact_id": "concatenated", "name": "Wrong", "phones": [{"label": "work", "value": "555-12345"}]},
            {"contact_id": "longer-base", "name": "Wrong", "phones": [{"label": "work", "value": "555-12345 x5"}]},
            {"contact_id": "other-extension", "name": "Wrong", "phones": [{"label": "work", "value": "555-1234 x50"}]},
        ]}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    assert bridge.search_contacts(query) == []
    with pytest.raises(ContactsBridgeError) as failure:
        bridge.resolve_message_recipient(query)
    assert failure.value.error_code == "CONTACT_NOT_FOUND"


def test_extension_query_selects_correct_contact_and_matching_secondary_phone(monkeypatch) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    target = {
        "contact_id": "target", "name": "Target",
        "phones": [
            {"label": "primary", "value": "888-0000"},
            {"label": "work", "value": "+1 555-1234 ext. 5"},
        ],
    }
    wrong = {"contact_id": "wrong", "name": "Wrong", "phones": [{"label": "work", "value": "555-12345"}]}

    def fake_run_script(script_name, *args):
        if script_name == "list_contacts.applescript":
            return {"total": 2, "items": [wrong, target]}
        assert script_name == "get_contact.applescript"
        assert args == ("target",)
        return {"found": True, "contact": target}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    matches = bridge.search_contacts("555-1234 x5")
    assert [contact.contact_id for contact in matches] == ["target"]
    result = bridge.resolve_message_recipient("555-1234 x5")
    assert result.contact.contact_id == "target"
    assert result.recipient_value == "+1 555-1234 ext. 5"


def test_extension_query_rejects_multiple_matching_phone_methods(monkeypatch) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    target = {
        "contact_id": "target", "name": "Target",
        "phones": [
            {"label": "one", "value": "555-1234 x5"},
            {"label": "two", "value": "777-1234 x5"},
        ],
    }

    def fake_run_script(script_name, *args):
        if script_name == "list_contacts.applescript":
            return {"total": 1, "items": [target]}
        assert script_name == "get_contact.applescript"
        return {"found": True, "contact": target}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    with pytest.raises(ContactsBridgeError) as failure:
        bridge.resolve_message_recipient("1234 x5")
    assert failure.value.error_code == "AMBIGUOUS_PHONE_NUMBER"


def test_phone_identity_preserves_extension_boundary_and_leading_zeroes() -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    assert bridge._normalize_lookup_value("555-1234 x5") == "5551234;ext=5"
    assert bridge._normalize_lookup_value("555-12345") == "55512345"
    assert bridge._normalize_lookup_value("555-1234 ext. 05") == "5551234;ext=05"
    assert bridge._normalize_lookup_value("tel:555-1234;ext=5") == "5551234;ext=5"
