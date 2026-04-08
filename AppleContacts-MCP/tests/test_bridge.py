from pathlib import Path
import subprocess

from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError


def test_search_contacts_matches_phone_number(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "search_contacts.applescript":
            return {"items": []}
        assert script_name == "list_contacts.applescript"
        return {
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


def test_search_contacts_prefers_direct_name_search(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "search_contacts.applescript"
        assert args == ("Sona",)
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


def test_search_contacts_matches_parenthetical_nickname(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "search_contacts.applescript"
        assert args == ("Sona",) or args == ("Sonali",)
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


def test_contacts_scripts_compile(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts = (
        repo_root / "applescripts" / "permission_check.applescript",
        repo_root / "applescripts" / "list_contacts.applescript",
        repo_root / "applescripts" / "search_contacts.applescript",
        repo_root / "applescripts" / "get_contact.applescript",
        repo_root / "applescripts" / "create_contact.applescript",
        repo_root / "applescripts" / "update_contact.applescript",
        repo_root / "applescripts" / "delete_contact.applescript",
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


def test_suggest_merge_candidates_filters_query(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "list_contacts.applescript":
            return {
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
    assert all("Example Person" == contact.name for contact in groups[0].contacts)
