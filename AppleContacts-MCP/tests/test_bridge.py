import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apple_contacts_mcp import contacts_bridge
from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError


def contact_item(
    contact_id: str,
    *,
    name: str = "Directory Contact",
    phone: str = "",
    email: str = "",
) -> dict[str, object]:
    phones = [{"label": "mobile", "value": phone}] if phone else []
    emails = [{"label": "work", "value": email}] if email else []
    return {
        "contact_id": contact_id,
        "name": name,
        "first_name": name.split()[0],
        "last_name": name.split()[-1],
        "organization": "",
        "phone_count": len(phones),
        "email_count": len(emails),
        "phones": phones,
        "emails": emails,
    }


def test_search_contacts_matches_phone_number(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "search_contacts.applescript":
            return {"items": []}
        assert script_name == "list_contacts.applescript"
        return {
            "total": 1,
            "items": [
                {
                    "contact_id": "contact-1",
                    "name": "Alice Doe",
                    "first_name": "Alice",
                    "last_name": "Doe",
                    "organization": "Example",
                    "phone_count": 1,
                    "email_count": 1,
                    "phones": [{"label": "mobile", "value": "+1 (555) 123-4567"}],
                    "emails": [{"label": "work", "value": "alice@example.com"}],
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    contacts = bridge.search_contacts("5551234567")

    assert len(contacts) == 1
    assert contacts[0].contact_id == "contact-1"


@pytest.mark.parametrize(
    ("query", "field", "value"),
    [
        ("5550001001", "phone", "+1 (555) 000-1001"),
        ("late@example.com", "email", "late@example.com"),
    ],
)
def test_search_contacts_scans_past_first_thousand(monkeypatch, query, field, value) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    directory = [contact_item(f"contact-{index}") for index in range(1001)]
    directory.append(
        contact_item(
            "contact-late",
            name="Late Match",
            phone=value if field == "phone" else "",
            email=value if field == "email" else "",
        )
    )
    calls: list[int] = []

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "search_contacts.applescript":
            return {"items": []}
        assert script_name == "list_contacts.applescript"
        limit, offset = map(int, args)
        calls.append(offset)
        return {"items": directory[offset : offset + limit], "total": len(directory)}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    matches = bridge.search_contacts(query)

    assert [contact.contact_id for contact in matches] == ["contact-late"]
    assert calls == [0, 1000]


def test_search_contacts_keeps_exact_matches_before_earlier_partial_matches(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    directory = [contact_item("contact-partial", phone="+1 555 000 10010")]
    directory.extend(contact_item(f"contact-{index}") for index in range(1, 1000))
    directory.append(contact_item("contact-exact", phone="555 000 1001"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        limit, offset = map(int, args)
        return {"items": directory[offset : offset + limit], "total": len(directory)}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    matches = bridge.search_contacts("5550001001")

    assert [contact.contact_id for contact in matches] == ["contact-exact", "contact-partial"]


def test_resolve_recipient_finds_contact_after_first_thousand(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    directory = [contact_item(f"contact-{index}") for index in range(1001)]
    late_contact = contact_item("contact-late", name="Late Recipient", phone="+1 555 777 9999")
    directory.append(late_contact)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "list_contacts.applescript":
            limit, offset = map(int, args)
            return {"items": directory[offset : offset + limit], "total": len(directory)}
        if script_name == "get_contact.applescript":
            return {"found": True, "contact": {**late_contact, "note": ""}}
        raise AssertionError(f"Unexpected script {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    recipient = bridge.resolve_message_recipient("5557779999")

    assert recipient.contact.contact_id == "contact-late"
    assert recipient.recipient_value == "+1 555 777 9999"


def test_search_contacts_prefers_direct_name_search(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "search_contacts.applescript"
        assert args == ("Sona", "25")
        return {
            "items": [
                {
                    "contact_id": "contact-sona",
                    "name": "Sonali (Sona) Chellan",
                    "first_name": "",
                    "last_name": "",
                    "organization": "",
                    "phone_count": 1,
                    "email_count": 1,
                    "phones": [{"label": "Phone", "value": "(832) 361-5976"}],
                    "emails": [{"label": "Email", "value": "sonalichellan@gmail.com"}],
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    contacts = bridge.search_contacts("Sona")

    assert len(contacts) == 1
    assert contacts[0].name == "Sonali (Sona) Chellan"


def test_get_contact_raises_when_missing(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "get_contact.applescript"
        return {"found": False}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    try:
        bridge.get_contact("contact-1")
    except ContactsBridgeError as exc:
        assert exc.error_code == "CONTACT_NOT_FOUND"
    else:
        raise AssertionError("Expected ContactsBridgeError")


def test_run_script_times_out_and_terminates_child(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "permission_check.applescript"
    script_path.touch()
    bridge = AppleContactsBridge(tmp_path)
    real_popen = subprocess.Popen

    def sleeping_popen(command, **kwargs):
        return real_popen([sys.executable, "-c", "import time; time.sleep(10)"], **kwargs)

    monkeypatch.setattr(contacts_bridge, "SCRIPT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(contacts_bridge.subprocess, "Popen", sleeping_popen)

    with pytest.raises(ContactsBridgeError, match="timeout") as exc_info:
        bridge._run_script(script_path.name)

    assert exc_info.value.error_code == "APPLESCRIPT_TIMEOUT"


def test_stop_process_handles_exit_before_terminate() -> None:
    class ExitedProcess:
        def terminate(self) -> None:
            raise ProcessLookupError

        def wait(self, timeout=None) -> int:
            return 0

    AppleContactsBridge(Path("/tmp/scripts"))._stop_process(ExitedProcess())


def test_run_script_rejects_oversized_output(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "permission_check.applescript"
    script_path.touch()
    bridge = AppleContactsBridge(tmp_path)
    real_popen = subprocess.Popen

    def noisy_popen(command, **kwargs):
        return real_popen([sys.executable, "-c", "print('x' * 1024)"], **kwargs)

    monkeypatch.setattr(contacts_bridge, "MAX_SCRIPT_OUTPUT_BYTES", 32)
    monkeypatch.setattr(contacts_bridge.subprocess, "Popen", noisy_popen)

    with pytest.raises(ContactsBridgeError) as exc_info:
        bridge._run_script(script_path.name)

    assert exc_info.value.error_code == "APPLESCRIPT_OUTPUT_TOO_LARGE"


def test_search_contacts_matches_parenthetical_nickname(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "search_contacts.applescript"
        assert args == ("Sona", "25") or args == ("Sonali", "25")
        return {
            "items": [
                {
                    "contact_id": "contact-sona",
                    "name": "Sonali (Sona) Chellan",
                    "first_name": "",
                    "last_name": "",
                    "organization": "",
                    "phone_count": 0,
                    "email_count": 1,
                    "phones": [],
                    "emails": [{"label": "home", "value": "sona@example.com"}],
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    sona_matches = bridge.search_contacts("Sona")
    sonali_matches = bridge.search_contacts("Sonali")

    assert len(sona_matches) == 1
    assert sona_matches[0].contact_id == "contact-sona"
    assert len(sonali_matches) == 1
    assert sonali_matches[0].contact_id == "contact-sona"


def test_create_contact_serializes_methods(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    captured: dict[str, object] = {}

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        captured["script_name"] = script_name
        captured["args"] = args
        return {"contact_id": "contact-1", "name": "Alice Doe", "created": True}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    result = bridge.create_contact(
        first_name="Alice",
        last_name="Doe",
        phones=[bridge._normalize_methods([{"label": "mobile", "value": "+15551234567"}])[0]],
        emails=[bridge._normalize_methods([{"label": "work", "value": "alice@example.com"}])[0]],
    )

    assert result.contact_id == "contact-1"
    assert captured["script_name"] == "create_contact.applescript"
    assert "+15551234567" in captured["args"][3]
    assert "alice@example.com" in captured["args"][4]


def test_update_contact_supports_no_change_sentinel(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        calls.append((script_name, args))
        if script_name == "update_contact.applescript":
            return {"contact_id": "contact-1", "name": "Alice Doe", "updated": True}
        if script_name == "get_contact.applescript":
            return {
                "found": True,
                "contact": {
                    "contact_id": "contact-1",
                    "name": "Alice Doe",
                    "first_name": "Alice",
                    "last_name": "Doe",
                    "organization": "",
                    "phone_count": 1,
                    "email_count": 1,
                    "phones": [{"label": "mobile", "value": "+15551234567"}],
                    "emails": [{"label": "work", "value": "alice@example.com"}],
                    "note": "",
                },
            }
        raise AssertionError(f"Unexpected script {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    detail = bridge.update_contact("contact-1", first_name="Alicia")

    assert detail.first_name == "Alice"
    assert calls[0][0] == "update_contact.applescript"
    assert calls[0][1][4] == "__NOCHANGE__"
    assert calls[0][1][5] == "__NOCHANGE__"


@pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("osacompile") is None,
    reason="osacompile is only available on macOS",
)
def test_contacts_scripts_compile(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "src" / "apple_contacts_mcp" / "applescripts"
    scripts = (
        scripts_dir / "permission_check.applescript",
        scripts_dir / "list_contacts.applescript",
        scripts_dir / "search_contacts.applescript",
        scripts_dir / "get_contact.applescript",
        scripts_dir / "create_contact.applescript",
        scripts_dir / "update_contact.applescript",
        scripts_dir / "delete_contact.applescript",
    )

    for script_path in scripts:
        compiled_path = tmp_path / f"{script_path.stem}.scpt"
        completed = subprocess.run(
            ["osacompile", "-o", str(compiled_path), str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout


def test_find_duplicates_groups_by_shared_email_and_name(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "list_contacts.applescript":
            return {
                "total": 2,
                "items": [
                    {
                        "contact_id": "contact-1",
                        "name": "Example Person",
                        "first_name": "Example",
                        "last_name": "Person",
                        "organization": "",
                        "phone_count": 1,
                        "email_count": 1,
                        "phones": [{"label": "mobile", "value": "+1 (555) 123-4567"}],
                        "emails": [{"label": "home", "value": "person@example.com"}],
                    },
                    {
                        "contact_id": "contact-2",
                        "name": "Example Person",
                        "first_name": "Example",
                        "last_name": "Person",
                        "organization": "",
                        "phone_count": 0,
                        "email_count": 1,
                        "phones": [],
                        "emails": [{"label": "work", "value": "person@example.com"}],
                    },
                ]
            }
        raise AssertionError(f"Unexpected script {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    groups = bridge.find_duplicates()

    assert len(groups) == 1
    assert groups[0].merge_recommended is True
    assert {contact.contact_id for contact in groups[0].contacts} == {"contact-1", "contact-2"}
    assert {item.kind for item in groups[0].evidence} >= {"name", "email"}


def test_find_duplicates_scans_past_first_thousand(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    directory = [contact_item(f"contact-{index}", name=f"Unique{index}") for index in range(1000)]
    directory.extend(
        [
            contact_item("contact-late-1", name="Late One", email="shared@example.com"),
            contact_item("contact-late-2", name="Late Two", email="shared@example.com"),
        ]
    )

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        limit, offset = map(int, args)
        return {"items": directory[offset : offset + limit], "total": len(directory)}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    groups = bridge.find_duplicates()

    assert any(
        {contact.contact_id for contact in group.contacts} == {"contact-late-1", "contact-late-2"}
        for group in groups
    )


def test_directory_scan_rejects_total_above_bound(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda *args: {"items": [], "total": contacts_bridge.MAX_DIRECTORY_CONTACTS + 1},
    )

    with pytest.raises(ContactsBridgeError) as exc_info:
        list(bridge._iter_all_contacts())

    assert exc_info.value.error_code == "CONTACT_DIRECTORY_TOO_LARGE"


def test_directory_scan_rejects_short_page(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))
    monkeypatch.setattr(bridge, "_run_script", lambda *args: {"items": [], "total": 1})

    with pytest.raises(ContactsBridgeError) as exc_info:
        list(bridge._iter_all_contacts())

    assert exc_info.value.error_code == "INCOMPLETE_CONTACT_DIRECTORY"


def test_suggest_merge_candidates_filters_query(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "list_contacts.applescript":
            return {
                "total": 3,
                "items": [
                    {
                        "contact_id": "contact-1",
                        "name": "Example Person",
                        "first_name": "Example",
                        "last_name": "Person",
                        "organization": "",
                        "phone_count": 0,
                        "email_count": 1,
                        "phones": [],
                        "emails": [{"label": "home", "value": "person@example.com"}],
                    },
                    {
                        "contact_id": "contact-2",
                        "name": "Example Person",
                        "first_name": "Example",
                        "last_name": "Person",
                        "organization": "",
                        "phone_count": 0,
                        "email_count": 1,
                        "phones": [],
                        "emails": [{"label": "work", "value": "person@example.com"}],
                    },
                    {
                        "contact_id": "contact-3",
                        "name": "Alice Doe",
                        "first_name": "Alice",
                        "last_name": "Doe",
                        "organization": "",
                        "phone_count": 0,
                        "email_count": 1,
                        "phones": [],
                        "emails": [{"label": "work", "value": "alice@example.com"}],
                    },
                ]
            }
        raise AssertionError(f"Unexpected script {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    groups = bridge.suggest_merge_candidates("example")

    assert len(groups) == 1
    assert all(contact.name == "Example Person" for contact in groups[0].contacts)
