from pathlib import Path
import subprocess

from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError


def test_search_contacts_matches_phone_number(monkeypatch) -> None:
    bridge = AppleContactsBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
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


def test_contacts_scripts_compile(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts = (
        repo_root / "applescripts" / "permission_check.applescript",
        repo_root / "applescripts" / "list_contacts.applescript",
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
