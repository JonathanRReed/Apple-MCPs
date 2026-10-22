"""Attach Contacts names to Messages handles in the unified server.

The Messages database stores raw handles (phone numbers, emails), so
participants and senders come back as ``+61402797945`` rather than a name.
The unified server has both Messages and Contacts access, so it resolves the
handles present in a Messages response through Contacts and fills
``display_name`` / ``contact_id`` on the participant and sender records. The
standalone Messages server is unchanged and keeps needing only Messages access.

Rules:
- Only the handles actually returned are looked up, in one Contacts helper call
  per response (at most ``MAX_HANDLES_PER_LOOKUP`` handles). The lookup is
  passive: it never builds the helper, never requests access and never runs
  the AppleScript backend, so a Messages read never raises a macOS prompt.
- Matching is exact-owner only (``AppleContactsBridge.lookup_handles`` with
  ``apple_contacts_mcp.phone_matching``): emails ignore case; a phone matches
  when it is the same number, allowing only a missing country calling code, so
  a different area code never borrows a contact's name; a handle owned by two
  different contacts is never guessed.
- Results are cached per handle for a few minutes; a Contacts failure is
  remembered briefly so a broken Contacts setup does not slow every read.
- Every response carries ``contact_names_status``: ``ok``,
  ``permission_denied`` (macOS denied Contacts access to this process) or
  ``unavailable`` (access not yet granted, helper not built yet, AppleScript
  backend selected, helper failure or timeout).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from typing import Any

from apple_contacts_mcp.models import ContactSummary
from apple_contacts_mcp.phone_matching import has_international_prefix, normalize_email, normalize_phone
from apple_messages_mcp.models import ContactNamesStatus

CACHE_TTL_SECONDS = 300.0
MAX_HANDLES_PER_LOOKUP = 500
FAILURE_BACKOFF_SECONDS = 60.0
STATUS_OK: ContactNamesStatus = "ok"
STATUS_PERMISSION_DENIED: ContactNamesStatus = "permission_denied"
STATUS_UNAVAILABLE: ContactNamesStatus = "unavailable"

NameMatch = tuple[str, str]  # (contact_id, display_name)


def contact_display_name(contact: ContactSummary) -> str | None:
    name = (contact.name or "").strip()
    if not name:
        name = " ".join(part for part in ((contact.first_name or "").strip(), (contact.last_name or "").strip()) if part)
    if not name:
        name = (contact.organization or "").strip()
    return name or None


def normalize_handle(address: str | None) -> str | None:
    """The cache key for a Messages handle, or None when it is neither an email nor a phone.

    Emails are lower-cased; phones are ``phone_matching.normalize_phone`` digits
    (with any extension), prefixed with ``+`` when written internationally. The
    prefix matters: ``+44 20 7946 0958`` and the national ``442079460958`` have
    the same digits but can belong to different people under ``same_phone``.
    Other handles (business chat ids) are never sent to Contacts.
    """
    value = (address or "").strip()
    if not value:
        return None
    if "@" in value:
        return normalize_email(value)
    digits = normalize_phone(value)
    if digits is None:
        return None
    return f"+{digits}" if has_international_prefix(value) else digits


class ContactNameResolver:
    """Per-handle, time-limited Contacts lookups shared by the Messages wrappers.

    ``lookup`` is called with the list of handles still unknown and returns
    either a response with ``ok`` and ``contacts`` (handle → ContactSummary) or
    an error response with ``error.error_code``; it is expected to check
    Contacts authorization itself without prompting.
    """

    def __init__(self, lookup: Callable[[list[str]], Any], *, clock: Callable[[], float] = time.monotonic) -> None:
        self._lookup = lookup
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[NameMatch | None, float]] = {}
        self._failure: tuple[ContactNamesStatus, float] | None = None

    def resolve(self, addresses: Iterable[str | None]) -> tuple[dict[str, NameMatch], ContactNamesStatus]:
        """Names for the given handles plus the status of the Contacts side.

        Returns ``(matches keyed by normalized handle, status)``. With no handles
        to resolve, Contacts is not consulted and the status is ``ok``.
        """
        keys: dict[str, str] = {}
        for address in addresses:
            key = normalize_handle(address)
            if address is not None and key is not None and key not in keys:
                keys[key] = address.strip()
        if not keys:
            return {}, STATUS_OK
        with self._lock:
            now = self._clock()
            found: dict[str, NameMatch] = {}
            pending: dict[str, str] = {}
            for key, raw in keys.items():
                cached = self._cache.get(key)
                if cached is not None and now < cached[1]:
                    if cached[0] is not None:
                        found[key] = cached[0]
                else:
                    pending[key] = raw
            if not pending:
                return found, STATUS_OK
            # One bounded helper call per response; handles past the cap stay
            # unnamed and uncached, so a later, smaller response can name them.
            pending = dict(list(pending.items())[:MAX_HANDLES_PER_LOOKUP])
            if self._failure is not None and now < self._failure[1]:
                return found, self._failure[0]
            status, resolved = self._fetch(list(pending.values()))
            if status != STATUS_OK:
                self._failure = (status, now + FAILURE_BACKOFF_SECONDS)
                return found, status
            self._failure = None
            for key in pending:
                match = resolved.get(key)
                self._cache[key] = (match, now + CACHE_TTL_SECONDS)
                if match is not None:
                    found[key] = match
            return found, STATUS_OK

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()
            self._failure = None

    def _fetch(self, handles: list[str]) -> tuple[ContactNamesStatus, dict[str, NameMatch]]:
        try:
            response = self._lookup(handles)
        except Exception:
            return STATUS_UNAVAILABLE, {}
        if not getattr(response, "ok", False):
            error = getattr(response, "error", None)
            code = getattr(error, "error_code", None) if error is not None else None
            return (STATUS_PERMISSION_DENIED if code == "PERMISSION_DENIED" else STATUS_UNAVAILABLE), {}
        contacts = getattr(response, "contacts", None) or {}
        resolved: dict[str, NameMatch] = {}
        for handle, contact in contacts.items():
            key = normalize_handle(handle)
            display = contact_display_name(contact)
            if key is not None and display is not None:
                resolved[key] = (contact.contact_id, display)
        return STATUS_OK, resolved


def _participants_needing_names(records: Iterable[Any]) -> list[str]:
    handles: list[str] = []
    for participant in records:
        if participant is None or getattr(participant, "display_name", None):
            continue
        address = getattr(participant, "address", None)
        if address:
            handles.append(address)
    return handles


def _annotate_participant(participant: Any, names: dict[str, NameMatch]) -> None:
    if participant is None or getattr(participant, "display_name", None):
        return
    key = normalize_handle(getattr(participant, "address", None))
    match = names.get(key) if key is not None else None
    if match is not None:
        participant.contact_id, participant.display_name = match


def _conversation_participants(conversation: Any) -> list[Any]:
    records = list(getattr(conversation, "participants", None) or [])
    records.extend(getattr(message, "sender", None) for message in getattr(conversation, "messages", None) or [])
    return records


def _finish_conversation(conversation: Any, names: dict[str, NameMatch]) -> None:
    participants = list(getattr(conversation, "participants", None) or [])
    for participant in _conversation_participants(conversation):
        _annotate_participant(participant, names)
    # Messages falls back to the raw handle as the title of an unnamed 1:1 chat.
    if len(participants) == 1 and participants[0].display_name:
        title = getattr(conversation, "display_name", None) or ""
        if not title or normalize_handle(title) == normalize_handle(participants[0].address):
            conversation.display_name = participants[0].display_name


def annotate_conversations(conversations: Iterable[Any], resolver: ContactNameResolver) -> ContactNamesStatus:
    """Fill names on every participant and sender in ``conversations``; returns the status."""
    items = list(conversations)
    handles: list[str] = []
    for conversation in items:
        handles.extend(_participants_needing_names(_conversation_participants(conversation)))
    names, status = resolver.resolve(handles)
    for conversation in items:
        _finish_conversation(conversation, names)
    return status


def annotate_messages(messages: Iterable[Any], resolver: ContactNameResolver) -> ContactNamesStatus:
    """Fill names on the senders of ``messages``; returns the status."""
    items = list(messages)
    names, status = resolver.resolve(_participants_needing_names(getattr(message, "sender", None) for message in items))
    for message in items:
        _annotate_participant(getattr(message, "sender", None), names)
    return status
