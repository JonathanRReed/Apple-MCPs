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


def test_contacts_scripts_compile(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts = (
        repo_root / "applescripts" / "permission_check.applescript",
        repo_root / "applescripts" / "list_contacts.applescript",
        repo_root / "applescripts" / "search_contacts.applescript",
        repo_root / "applescripts" / "get_contact.applescript",
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
