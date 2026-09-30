"""Coverage authored for issue #32; live deletion needs macOS validation."""

import json
from pathlib import Path

import pytest

from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "apple_contacts_mcp" / "applescripts"


@pytest.mark.parametrize("query", ["Nobody Here", "Studio54", "Person 123", "東京", "alice.example.com"])
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
