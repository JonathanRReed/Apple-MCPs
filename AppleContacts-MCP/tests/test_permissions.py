from apple_contacts_mcp.permissions import SafetyError, ensure_action_allowed


def test_contacts_read_actions_are_allowed() -> None:
    ensure_action_allowed("contacts_list_contacts")
    ensure_action_allowed("contacts_search_contacts")
    ensure_action_allowed("contacts_get_contact")
    ensure_action_allowed("contacts_resolve_message_recipient")


def test_unknown_action_is_rejected() -> None:
    try:
        ensure_action_allowed("contacts_delete_contact")
    except SafetyError as exc:
        assert exc.error_code == "UNKNOWN_ACTION"
    else:
        raise AssertionError("Expected SafetyError")
