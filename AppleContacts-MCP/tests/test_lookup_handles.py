"""lookup_handles: exact owners only, passive (no prompt, no build), one helper call per lookup."""

import json
from pathlib import Path

import pytest

from apple_contacts_mcp import tools
from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError
from apple_contacts_mcp.models import ErrorResponse, HandleLookupResponse

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "apple_contacts_mcp" / "applescripts"
HELPER_SOURCE = Path(__file__).resolve().parents[1] / "src" / "apple_contacts_mcp" / "contacts_bridge.swift"


def contact_item(contact_id: str, name: str = "", *, phones: tuple[str, ...] = (), emails: tuple[str, ...] = (), organization: str = "") -> dict[str, object]:
    return {
        "contact_id": contact_id,
        "name": name,
        "organization": organization,
        "phones": [{"label": "mobile", "value": value} for value in phones],
        "emails": [{"label": "home", "value": value} for value in emails],
    }


DIRECTORY = [
    contact_item("c-michael", "Michael", phones=("0402 797 945",)),
    contact_item("c-ana", "Ana Silva", phones=("+1 (425) 753-4663",), emails=("Ana@Example.com",)),
    contact_item("c-mom", "Mom", phones=("(212) 555-1234",)),
    contact_item("c-uk", "UK Office", phones=("+44 20 7946 0958",)),
    contact_item("c-bank", "Bank", phones=("88911",)),
    # Two different contacts hold the same complete number: never guess between them.
    contact_item("c-dup1", "Dup One", phones=("+33 7911 123456",)),
    contact_item("c-dup2", "Dup Two", phones=("+33 7911 123456",)),
]


def native_bridge(monkeypatch, directory: list[dict[str, object]], calls: list[tuple[str, tuple[str, ...]]] | None = None) -> AppleContactsBridge:
    bridge = AppleContactsBridge(SCRIPTS_DIR, helper_source=HELPER_SOURCE, helper_build_dir=Path("/nonexistent"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if calls is not None:
            calls.append((script_name, args))
        assert script_name == "lookup_handles.applescript"
        wanted = json.loads(args[0])
        assert isinstance(wanted, list)
        # The helper returns a superset: the same last 7 digits, or an exact email (same rule as the Swift helper).
        return {"items": [item for item in directory if _helper_candidate(item, wanted)]}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    return bridge


def _helper_candidate(item: dict[str, object], wanted: list[str]) -> bool:
    for handle in wanted:
        if "@" in handle:
            if any(method["value"].strip().lower() == handle.strip().lower() for method in item["emails"]):  # type: ignore[index]
                return True
            continue
        digits = "".join(ch for ch in handle if ch.isdigit())
        for method in item["phones"]:  # type: ignore[index]
            stored = "".join(ch for ch in method["value"] if ch.isdigit())  # type: ignore[index]
            if stored == digits or (len(stored) >= 7 and len(digits) >= 7 and stored[-7:] == digits[-7:]):
                return True
    return False


def test_exact_owners_resolve_in_international_and_national_forms(monkeypatch) -> None:
    bridge = native_bridge(monkeypatch, DIRECTORY)

    resolved = bridge.lookup_handles(["+61402797945", "+14257534663", "ana@example.com", "+442079460958"])

    assert {handle: contact.contact_id for handle, contact in resolved.items()} == {
        "+61402797945": "c-michael",
        "+14257534663": "c-ana",
        "ana@example.com": "c-ana",
        "+442079460958": "c-uk",
    }


def test_different_area_code_never_borrows_a_name(monkeypatch) -> None:
    """+1 312 555 1234 must not show as "Mom" when Mom is (212) 555-1234."""
    bridge = native_bridge(monkeypatch, DIRECTORY)

    assert bridge.lookup_handles(["+13125551234"]) == {}
    assert bridge.lookup_handles(["+12125551234"])["+12125551234"].contact_id == "c-mom"


def test_short_codes_match_digit_for_digit_only(monkeypatch) -> None:
    bridge = native_bridge(monkeypatch, DIRECTORY)

    assert bridge.lookup_handles(["88911"])["88911"].contact_id == "c-bank"
    assert bridge.lookup_handles(["988911"]) == {}


def test_two_owners_and_unknown_handles_are_left_out(monkeypatch) -> None:
    bridge = native_bridge(monkeypatch, DIRECTORY)

    assert bridge.lookup_handles(["+337911123456", "+15550000000", "nobody@example.com", "  ", ""]) == {}


def test_native_lookup_is_one_helper_call_with_deduplicated_handles(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    bridge = native_bridge(monkeypatch, DIRECTORY, calls)

    bridge.lookup_handles(["+61402797945", "+61402797945 ", "ana@example.com"])

    assert len(calls) == 1
    assert json.loads(calls[0][1][0]) == ["+61402797945", "ana@example.com"]


def test_empty_handle_list_never_touches_contacts(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    bridge = native_bridge(monkeypatch, DIRECTORY, calls)

    assert bridge.lookup_handles([]) == {}
    assert bridge.lookup_handles(["", "   "]) == {}
    assert calls == []


def test_applescript_backend_scans_the_directory_pages(monkeypatch) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    scripts: list[str] = []

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        scripts.append(script_name)
        assert script_name == "list_contacts.applescript"
        return {"total": len(DIRECTORY), "items": DIRECTORY}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    resolved = bridge.lookup_handles(["0402797945", "+13125551234"])

    assert [contact.contact_id for contact in resolved.values()] == ["c-michael"]
    assert scripts == ["list_contacts.applescript"]


def test_national_handle_matching_two_contacts_numbers_is_left_out(monkeypatch) -> None:
    # same_phone is not transitive: a national handle matches both a +1 and a +44
    # number. Owned by two contacts, it is ambiguous and gets no name.
    directory = [
        contact_item("c-us", "US Person", phones=("+1 6123456789",)),
        contact_item("c-uk", "UK Person", phones=("+44 6123456789",)),
    ]
    bridge = native_bridge(monkeypatch, directory)

    assert bridge.lookup_handles(["6123456789"]) == {}
    assert bridge.lookup_handles(["+16123456789"])["+16123456789"].contact_id == "c-us"


def test_shared_phone_matching_rules_apply(monkeypatch) -> None:
    directory = [
        contact_item("c-mom", "Mom", phones=("(212) 555-1234",)),
        contact_item("c-ana", "Ana", emails=("  Ana@Example.com ",)),
        contact_item("c-ext", "Desk", phones=("+1 415 555 0100 x12",)),
    ]
    bridge = native_bridge(monkeypatch, directory)

    resolved = bridge.lookup_handles(["1 (212) 555-1234", "ANA@example.com", "+14155550100", "+14155550100 x12"])

    assert {handle: contact.contact_id for handle, contact in resolved.items()} == {
        "1 (212) 555-1234": "c-mom",
        "ANA@example.com": "c-ana",
        "+14155550100 x12": "c-ext",
    }


def _no_helper_run(*_args, **_kwargs):
    pytest.fail("a passive lookup must not run or build the Contacts helper")


def test_tool_never_runs_the_applescript_backend(monkeypatch) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR)
    monkeypatch.setattr(bridge, "_run_script", _no_helper_run)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.contacts_lookup_handles(["+61402797945"])

    assert isinstance(result, ErrorResponse)
    assert result.error.error_code == "AUTHORIZATION_UNKNOWN"


def test_tool_never_builds_the_helper(monkeypatch, tmp_path) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR, helper_source=HELPER_SOURCE, helper_build_dir=tmp_path)
    monkeypatch.setattr(bridge, "_run_script", _no_helper_run)
    monkeypatch.setattr(bridge, "_ensure_native_helper", _no_helper_run)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.contacts_lookup_handles(["+61402797945"])

    assert isinstance(result, ErrorResponse)
    assert result.error.error_code == "HELPER_NOT_BUILT"


def test_tool_resolves_with_one_helper_call_and_no_separate_permission_check(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    bridge = native_bridge(monkeypatch, DIRECTORY, calls)
    monkeypatch.setattr(bridge, "helper_built", lambda: True)
    monkeypatch.setattr(bridge, "permission_diagnostic", _no_helper_run)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.contacts_lookup_handles(["+61402797945"])

    assert isinstance(result, HandleLookupResponse)
    assert result.contacts["+61402797945"].name == "Michael"
    assert [name for name, _ in calls] == ["lookup_handles.applescript"]


@pytest.mark.parametrize("error_code", ["PERMISSION_DENIED", "AUTHORIZATION_UNKNOWN"])
def test_tool_passes_the_helpers_permission_state_through(monkeypatch, error_code) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR, helper_source=HELPER_SOURCE, helper_build_dir=Path("/nonexistent"))
    monkeypatch.setattr(bridge, "helper_built", lambda: True)
    helper_stderr = json.dumps({"ok": False, "error_code": error_code, "message": "no access", "suggestion": "Allow it."})

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        raise bridge._map_script_error(helper_stderr)

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.contacts_lookup_handles(["+61402797945"])

    assert isinstance(result, ErrorResponse)
    assert result.error.error_code == error_code


def test_helper_lookup_command_never_requests_access() -> None:
    source = HELPER_SOURCE.read_text()
    passive = source[source.index("func requireAccessWithoutPrompt()"):]
    passive = passive[: passive.index("\n}\n")]
    assert "requestAccess" not in passive
    assert 'if command == "lookup_handles" {\n' in source
    dispatch = source[source.index('if command == "lookup_handles" {'):]
    assert dispatch.index("requireAccessWithoutPrompt()") < dispatch.index("requireAccess()")


def test_tool_reports_bridge_failures_as_errors(monkeypatch) -> None:
    bridge = AppleContactsBridge(SCRIPTS_DIR, helper_source=HELPER_SOURCE, helper_build_dir=Path("/nonexistent"))
    monkeypatch.setattr(bridge, "helper_built", lambda: True)

    def boom(handles: list[str]) -> dict[str, object]:
        raise ContactsBridgeError("HELPER_TIMEOUT", "Contacts helper timed out.", "Retry.")

    monkeypatch.setattr(bridge, "lookup_handles", boom)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.contacts_lookup_handles(["+61402797945"])

    assert isinstance(result, ErrorResponse)
    assert result.error.error_code == "HELPER_TIMEOUT"
