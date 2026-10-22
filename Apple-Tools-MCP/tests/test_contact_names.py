"""Contacts names on Messages responses: per-handle lookups, no prompt, honest status."""


import apple_agent_mcp.tools as tools
from apple_agent_mcp.contact_names import (
    ContactNameResolver,
    annotate_conversations,
    annotate_messages,
    contact_display_name,
    normalize_handle,
)
from apple_contacts_mcp.models import ContactMethod, ContactSummary, ErrorResponse, HandleLookupResponse, ToolError
from apple_messages_mcp.models import (
    ConversationListResponse,
    ConversationRecord,
    ConversationResponse,
    ConversationSummary,
    MessageRecord,
    MessageResponse,
    MessageSearchResponse,
    ParticipantRecord,
)


def _contact(contact_id: str, name: str = "", *, organization: str = "", phones=(), emails=()) -> ContactSummary:
    return ContactSummary(
        contact_id=contact_id,
        name=name,
        organization=organization,
        phones=[ContactMethod(label="mobile", value=value) for value in phones],
        emails=[ContactMethod(label="home", value=value) for value in emails],
    )


def _participant(address: str) -> ParticipantRecord:
    return ParticipantRecord(handle_id=address, address=address)


OWNERS = {
    "+61402797945": _contact("c-michael", "Michael", organization="Somewhere", phones=["0402 797 945"]),
    "ana@example.com": _contact("c-ana", "Ana Silva", phones=["+1 (425) 753-4663"], emails=["Ana@Example.com"]),
    "+12125551234": _contact("c-mom", "Mom", phones=["(212) 555-1234"]),
    "+61390001111": _contact("c-shop", organization="Corner Shop", phones=["+61 3 9000 1111"]),
}


class FakeContacts:
    """Stands in for contacts_lookup_handles: exact owners from OWNERS, counting calls."""

    def __init__(self, result=None):
        self.calls: list[list[str]] = []
        self.result = result

    def __call__(self, handles: list[str]):
        self.calls.append(list(handles))
        if self.result is not None:
            return self.result
        return HandleLookupResponse(contacts={h: OWNERS[h] for h in handles if h in OWNERS})


def _denied(code: str = "PERMISSION_DENIED") -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=code, message="no", suggestion=None))


def test_normalize_handle_lowercases_emails_and_keeps_phone_digits() -> None:
    assert normalize_handle(" Ana@Example.com ") == "ana@example.com"
    assert normalize_handle("+1 (212) 555-1234") == "+12125551234"
    assert normalize_handle("(212) 555-1234") == "2125551234"
    assert normalize_handle("") is None
    assert normalize_handle(None) is None
    assert normalize_handle("---") is None


def test_display_name_prefers_name_then_first_last_then_organization() -> None:
    assert contact_display_name(_contact("a", "Full Name", organization="Org")) == "Full Name"
    assert contact_display_name(ContactSummary(contact_id="b", name="", first_name="Jo", last_name="Lee")) == "Jo Lee"
    assert contact_display_name(_contact("c", organization="Org Only")) == "Org Only"
    assert contact_display_name(_contact("d")) is None


def test_resolver_asks_contacts_only_for_unknown_handles_and_caches_both_hits_and_misses() -> None:
    now = [0.0]
    contacts = FakeContacts()
    resolver = ContactNameResolver(contacts, clock=lambda: now[0])

    names, status = resolver.resolve(["+61402797945", "+61402797945", "+15550000000", None, ""])
    assert status == "ok"
    assert names == {"+61402797945": ("c-michael", "Michael")}
    assert contacts.calls == [["+61402797945", "+15550000000"]]

    names, status = resolver.resolve(["+61402797945", "+15550000000", "ana@example.com"])
    assert status == "ok"
    assert names == {"+61402797945": ("c-michael", "Michael"), "ana@example.com": ("c-ana", "Ana Silva")}
    assert contacts.calls[1] == ["ana@example.com"]  # the hit and the miss were both cached

    now[0] = 301.0
    resolver.resolve(["+61402797945"])
    assert contacts.calls[2] == ["+61402797945"]  # refreshed after the TTL


def test_resolver_never_calls_contacts_without_handles() -> None:
    contacts = FakeContacts()
    resolver = ContactNameResolver(contacts)

    assert resolver.resolve([]) == ({}, "ok")
    assert resolver.resolve([None, "", "  "]) == ({}, "ok")
    assert contacts.calls == []


def test_resolver_reports_permission_denied_and_backs_off() -> None:
    now = [0.0]
    contacts = FakeContacts(result=_denied())
    resolver = ContactNameResolver(contacts, clock=lambda: now[0])

    assert resolver.resolve(["+61402797945"]) == ({}, "permission_denied")
    assert resolver.resolve(["ana@example.com"]) == ({}, "permission_denied")
    assert len(contacts.calls) == 1  # backing off, not retried yet

    now[0] = 61.0
    contacts.result = None
    names, status = resolver.resolve(["ana@example.com"])
    assert status == "ok"
    assert names == {"ana@example.com": ("c-ana", "Ana Silva")}


def test_resolver_reports_other_failures_as_unavailable() -> None:
    assert ContactNameResolver(FakeContacts(result=_denied("AUTHORIZATION_UNKNOWN"))).resolve(["+61402797945"])[1] == "unavailable"
    assert ContactNameResolver(FakeContacts(result=_denied("SCRIPT_TIMEOUT"))).resolve(["+61402797945"])[1] == "unavailable"

    def explode(handles):
        raise RuntimeError("helper crashed")

    assert ContactNameResolver(explode).resolve(["+61402797945"])[1] == "unavailable"


def test_resolver_keeps_cached_names_while_contacts_is_down() -> None:
    contacts = FakeContacts()
    resolver = ContactNameResolver(contacts)
    resolver.resolve(["+61402797945"])

    contacts.result = _denied()
    names, status = resolver.resolve(["+61402797945", "+12125551234"])

    assert status == "permission_denied"
    assert names == {"+61402797945": ("c-michael", "Michael")}


def test_annotate_conversations_names_participants_senders_and_unnamed_one_to_one_title() -> None:
    contacts = FakeContacts()
    resolver = ContactNameResolver(contacts)
    conversation = ConversationRecord(
        chat_id="any;-;+61402797945",
        display_name="+61402797945",
        participants=[_participant("+61402797945")],
        unread_count=0,
        messages=[
            MessageRecord(message_id="m1", sender=_participant("+61402797945"), is_from_me=False, has_attachments=False),
            MessageRecord(message_id="m2", sender=_participant("ana@example.com"), is_from_me=False, has_attachments=False),
        ],
    )

    status = annotate_conversations([conversation], resolver)

    assert status == "ok"
    assert conversation.display_name == "Michael"
    assert conversation.participants[0].display_name == "Michael"
    assert conversation.participants[0].contact_id == "c-michael"
    assert conversation.messages[0].sender.display_name == "Michael"
    assert conversation.messages[1].sender.display_name == "Ana Silva"
    assert contacts.calls == [["+61402797945", "ana@example.com"]]  # one Contacts call per response


def test_annotate_conversations_keeps_group_titles_and_existing_names() -> None:
    resolver = ContactNameResolver(FakeContacts())
    named = ParticipantRecord(handle_id="+61402797945", address="+61402797945", display_name="Mike (from Messages)")
    group = ConversationSummary(
        chat_id="chat123", display_name="Guys Night", participants=[named, _participant("+12125551234")], unread_count=0
    )

    annotate_conversations([group], resolver)

    assert group.display_name == "Guys Night"
    assert [p.display_name for p in group.participants] == ["Mike (from Messages)", "Mom"]


def test_annotate_conversations_uses_organization_and_leaves_unknown_handles_alone() -> None:
    resolver = ContactNameResolver(FakeContacts())
    shop = ConversationSummary(chat_id="any;-;+61390001111", display_name=None, participants=[_participant("+61390001111")], unread_count=0)
    stranger = ConversationSummary(chat_id="any;-;+13125551234", display_name="+13125551234", participants=[_participant("+13125551234")], unread_count=0)

    annotate_conversations([shop, stranger], resolver)

    assert shop.display_name == "Corner Shop"
    # +1 312 555 1234 is not Mom (212 555 1234): Contacts returned no owner, so nothing is guessed.
    assert stranger.display_name == "+13125551234"
    assert stranger.participants[0].display_name is None


def test_annotate_messages_names_senders() -> None:
    resolver = ContactNameResolver(FakeContacts())
    messages = [MessageRecord(message_id="m1", sender=_participant("ana@example.com"), is_from_me=False, has_attachments=False)]

    assert annotate_messages(messages, resolver) == "ok"
    assert messages[0].sender.display_name == "Ana Silva"


def test_wrappers_attach_names_set_status_and_leave_errors_untouched(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_CONTACT_NAMES", ContactNameResolver(FakeContacts()))
    conversation = ConversationSummary(
        chat_id="any;-;+61402797945", display_name="+61402797945", participants=[_participant("+61402797945")], unread_count=1
    )
    message = MessageRecord(message_id="m1", sender=_participant("ana@example.com"), is_from_me=False, has_attachments=False)
    monkeypatch.setattr(tools, "_messages_list_conversations", lambda **_: ConversationListResponse(conversations=[conversation], count=1))
    monkeypatch.setattr(tools, "_messages_search_messages", lambda **_: MessageSearchResponse(messages=[message], count=1))
    monkeypatch.setattr(tools, "_messages_get_conversation", lambda **_: ConversationResponse(conversation=ConversationRecord(**conversation.model_dump(), messages=[])))
    monkeypatch.setattr(tools, "_messages_get_message", lambda **_: MessageResponse(message=message))

    listed = tools.messages_list_conversations(limit=5)
    searched = tools.messages_search_messages(query="hi")
    fetched = tools.messages_get_conversation("any;-;+61402797945", limit=5)
    single = tools.messages_get_message("m1")

    assert listed.conversations[0].display_name == "Michael"
    assert searched.messages[0].sender.display_name == "Ana Silva"
    assert fetched.conversation.display_name == "Michael"
    assert single.message.sender.display_name == "Ana Silva"
    assert {r.contact_names_status for r in (listed, searched, fetched, single)} == {"ok"}

    monkeypatch.setattr(tools, "_messages_list_conversations", lambda **_: {"ok": False, "error_code": "PERMISSION_DENIED"})
    assert tools.messages_list_conversations() == {"ok": False, "error_code": "PERMISSION_DENIED"}


def test_wrappers_report_missing_contacts_access_without_prompting(monkeypatch) -> None:
    contacts = FakeContacts(result=_denied())
    monkeypatch.setattr(tools, "_CONTACT_NAMES", ContactNameResolver(contacts))
    conversation = ConversationSummary(chat_id="any;-;+61402797945", display_name="+61402797945", participants=[_participant("+61402797945")], unread_count=0)
    monkeypatch.setattr(tools, "_messages_list_conversations", lambda **_: ConversationListResponse(conversations=[conversation], count=1))

    listed = tools.messages_list_conversations()

    assert listed.contact_names_status == "permission_denied"
    assert listed.conversations[0].display_name == "+61402797945"
    assert contacts.calls == [["+61402797945"]]


def test_wrappers_skip_contacts_entirely_when_nothing_needs_a_name(monkeypatch) -> None:
    contacts = FakeContacts(result=_denied())
    monkeypatch.setattr(tools, "_CONTACT_NAMES", ContactNameResolver(contacts))
    monkeypatch.setattr(tools, "_messages_list_conversations", lambda **_: ConversationListResponse(conversations=[], count=0))

    assert tools.messages_list_conversations().contact_names_status == "ok"
    assert contacts.calls == []


def test_normalize_handle_keeps_extensions_and_skips_non_phone_handles() -> None:
    assert normalize_handle("+1 415 555 0100 x12") == "+14155550100;ext=12"
    assert normalize_handle("urn:biz:1234567-abcd") is None


def test_resolver_caps_one_lookup_and_does_not_cache_the_overflow(monkeypatch) -> None:
    import apple_agent_mcp.contact_names as contact_names

    monkeypatch.setattr(contact_names, "MAX_HANDLES_PER_LOOKUP", 2)
    contacts = FakeContacts()
    resolver = ContactNameResolver(contacts)

    resolver.resolve(["+61402797945", "ana@example.com", "+12125551234"])
    names, _ = resolver.resolve(["+12125551234"])

    assert contacts.calls == [["+61402797945", "ana@example.com"], ["+12125551234"]]
    assert names == {"+12125551234": ("c-mom", "Mom")}


def test_end_to_end_a_stranger_never_gets_a_saved_contacts_name(monkeypatch) -> None:
    """+1 312 555 1234 is not "Mom" when Mom is (212) 555-1234, through the real bridge and matcher."""
    from pathlib import Path

    import apple_contacts_mcp.tools as contacts_tools
    from apple_contacts_mcp.contacts_bridge import AppleContactsBridge

    package = Path(contacts_tools.__file__).resolve().parent
    bridge = AppleContactsBridge(package / "applescripts", helper_source=package / "contacts_bridge.swift", helper_build_dir=Path("/nonexistent"))
    mom = {"contact_id": "c-mom", "name": "Mom", "phones": [{"label": "mobile", "value": "(212) 555-1234"}], "emails": []}
    helper_calls: list[str] = []

    def fake_run_script(script_name: str, *args: str, **kwargs: object) -> dict[str, object]:
        helper_calls.append(script_name)
        return {"items": [mom]}  # the helper's cheap last-7-digits candidate set includes Mom for both

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    monkeypatch.setattr(bridge, "helper_built", lambda: True)
    monkeypatch.setattr(contacts_tools, "_bridge", lambda: bridge)
    resolver = ContactNameResolver(contacts_tools.contacts_lookup_handles)
    stranger = ConversationSummary(chat_id="any;-;+13125551234", display_name="+13125551234", participants=[_participant("+13125551234")], unread_count=0)
    family = ConversationSummary(chat_id="any;-;+12125551234", display_name="+12125551234", participants=[_participant("+12125551234")], unread_count=0)

    assert annotate_conversations([stranger, family], resolver) == "ok"

    assert stranger.participants[0].display_name is None
    assert stranger.display_name == "+13125551234"
    assert family.participants[0].display_name == "Mom"
    assert helper_calls == ["lookup_handles.applescript"]


def test_international_and_national_handles_with_same_digits_keep_separate_names() -> None:
    # Release review round 2: "+44 20 7946 0958" (Alice, saved as 020 7946 0958)
    # and the national "442079460958" (Bob, saved as +49 442079460958) have the
    # same digits; a digits-only cache key showed Alice's name on Bob's messages.
    from apple_contacts_mcp.phone_matching import same_phone

    alice = _contact("c-alice", "Alice", phones=("020 7946 0958",))
    bob = _contact("c-bob", "Bob", phones=("+49 442079460958",))
    assert same_phone("+44 20 7946 0958", "020 7946 0958") and same_phone("442079460958", "+49 442079460958")

    def lookup(handles):
        owners = {}
        for handle in handles:
            matches = [c for c in (alice, bob) if any(same_phone(handle, m.value) for m in c.phones)]
            if len(matches) == 1:
                owners[handle] = matches[0]
        return HandleLookupResponse(contacts=owners)

    together, _ = ContactNameResolver(lookup).resolve(["+44 20 7946 0958", "442079460958"])
    assert together == {"+442079460958": ("c-alice", "Alice"), "442079460958": ("c-bob", "Bob")}

    resolver = ContactNameResolver(lookup)
    first, _ = resolver.resolve(["+44 20 7946 0958"])
    second, _ = resolver.resolve(["442079460958"])
    assert first == {"+442079460958": ("c-alice", "Alice")}
    assert second == {"442079460958": ("c-bob", "Bob")}
