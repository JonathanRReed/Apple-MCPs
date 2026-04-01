from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess

from apple_contacts_mcp.config import load_settings
from apple_contacts_mcp.models import ContactDetail, ContactMethod, ContactSummary, CreateContactResponse, DeleteContactResponse, ResolvedRecipientResponse

METHOD_FIELD_SEPARATOR = "\x1f"
METHOD_RECORD_SEPARATOR = "\x1e"
NO_CHANGE_SENTINEL = "__NOCHANGE__"


class ContactsBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class AppleContactsBridge:
    def __init__(self, scripts_dir: Path) -> None:
        self.scripts_dir = scripts_dir

    def permission_diagnostic(self) -> tuple[bool, ContactsBridgeError | None]:
        try:
            self._run_script("permission_check.applescript")
            return True, None
        except ContactsBridgeError as exc:
            return False, exc

    def list_contacts(self) -> list[ContactSummary]:
        payload = self._run_script("list_contacts.applescript")
        return [self._normalize_summary(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def get_contact(self, contact_id: str) -> ContactDetail:
        payload = self._run_script("get_contact.applescript", contact_id)
        if not payload.get("found", True):
            raise ContactsBridgeError(
                "CONTACT_NOT_FOUND",
                f"No contact matched '{contact_id}'.",
                "Search contacts first to discover a valid contact id.",
            )
        raw_contact = payload.get("contact")
        if not isinstance(raw_contact, dict):
            raise ContactsBridgeError(
                "INVALID_SCRIPT_OUTPUT",
                "The get_contact AppleScript did not return a contact object.",
                "Inspect the AppleScript output and try again.",
            )
        return self._normalize_detail(raw_contact)

    def search_contacts(self, query: str, limit: int = 25) -> list[ContactSummary]:
        query_text = query.strip().lower()
        if not query_text:
            raise ContactsBridgeError("INVALID_INPUT", "query must not be empty", "Provide a non-empty name, phone number, or email address.")
        direct_matches = self._search_contacts_by_name(query)
        if direct_matches:
            return direct_matches[: max(1, min(limit, 100))]
        normalized_query = self._normalize_lookup_value(query)
        exact_matches: list[ContactSummary] = []
        partial_matches: list[ContactSummary] = []
        for contact in self.list_contacts():
            if self._is_exact_match(contact, query_text, normalized_query):
                exact_matches.append(contact)
                continue
            if self._is_partial_match(contact, query_text, normalized_query):
                partial_matches.append(contact)
        ordered = self._dedupe_contacts([*exact_matches, *partial_matches])
        return ordered[: max(1, min(limit, 100))]

    def resolve_message_recipient(self, query: str, channel: str = "phone") -> ResolvedRecipientResponse:
        if channel not in {"phone", "email", "any"}:
            raise ContactsBridgeError("INVALID_INPUT", f"Unsupported channel '{channel}'.", "Use 'phone', 'email', or 'any'.")
        matches = self.search_contacts(query, limit=10)
        if not matches:
            raise ContactsBridgeError("CONTACT_NOT_FOUND", f"No contact matched '{query}'.", "Search contacts first to discover a valid contact.")

        query_text = query.strip().lower()
        normalized_query = self._normalize_lookup_value(query)
        exact_matches = [contact for contact in matches if self._is_exact_match(contact, query_text, normalized_query)]
        if len(exact_matches) > 1:
            raise ContactsBridgeError(
                "AMBIGUOUS_CONTACT",
                f"Multiple contacts matched '{query}'.",
                "Use contacts_search_contacts first, then choose a specific contact_id.",
            )
        if len(exact_matches) == 1:
            selected = exact_matches[0]
        elif len(matches) == 1:
            selected = matches[0]
        else:
            raise ContactsBridgeError(
                "AMBIGUOUS_CONTACT",
                f"Multiple contacts matched '{query}'.",
                "Use contacts_search_contacts first, then choose a specific contact_id.",
            )

        detail = self.get_contact(selected.contact_id)
        recipient_kind, recipient = self._choose_recipient(detail, channel)
        return ResolvedRecipientResponse(
            contact=detail,
            recipient_kind=recipient_kind,
            recipient_label=recipient.label,
            recipient_value=recipient.value,
        )

    def create_contact(
        self,
        *,
        first_name: str,
        last_name: str = "",
        organization: str = "",
        phones: list[ContactMethod] | None = None,
        emails: list[ContactMethod] | None = None,
        note: str = "",
    ) -> CreateContactResponse:
        payload = self._run_script(
            "create_contact.applescript",
            first_name,
            last_name,
            organization,
            self._serialize_methods(phones),
            self._serialize_methods(emails),
            note,
        )
        return CreateContactResponse(
            contact_id=str(payload.get("contact_id", "")),
            name=str(payload.get("name", "")),
            created=bool(payload.get("created", True)),
        )

    def update_contact(
        self,
        contact_id: str,
        *,
        first_name: str = "",
        last_name: str = "",
        organization: str = "",
        phones: list[ContactMethod] | None = None,
        emails: list[ContactMethod] | None = None,
        note: str = "",
    ) -> ContactDetail:
        payload = self._run_script(
            "update_contact.applescript",
            contact_id,
            first_name,
            last_name,
            organization,
            self._serialize_methods(phones) if phones is not None else NO_CHANGE_SENTINEL,
            self._serialize_methods(emails) if emails is not None else NO_CHANGE_SENTINEL,
            note,
        )
        if not payload.get("updated", False):
            raise ContactsBridgeError(
                "UPDATE_FAILED",
                f"Failed to update contact '{contact_id}'.",
                "Ensure the contact exists and try again.",
            )
        return self.get_contact(contact_id)

    def delete_contact(self, contact_id: str) -> DeleteContactResponse:
        payload = self._run_script("delete_contact.applescript", contact_id)
        return DeleteContactResponse(
            contact_id=contact_id,
            deleted=bool(payload.get("deleted", False)),
        )

    def _choose_recipient(self, contact: ContactDetail, channel: str) -> tuple[str, ContactMethod]:
        if channel == "phone":
            if contact.phones:
                return "phone", contact.phones[0]
            raise ContactsBridgeError(
                "NO_PHONE_NUMBER",
                f"Contact '{contact.name}' does not have a phone number.",
                "Use a different contact or resolve by email instead.",
            )
        if channel == "email":
            if contact.emails:
                return "email", contact.emails[0]
            raise ContactsBridgeError(
                "NO_EMAIL_ADDRESS",
                f"Contact '{contact.name}' does not have an email address.",
                "Use a different contact or resolve by phone instead.",
            )
        if contact.phones:
            return "phone", contact.phones[0]
        if contact.emails:
            return "email", contact.emails[0]
        raise ContactsBridgeError(
            "NO_CONTACT_METHOD",
            f"Contact '{contact.name}' does not have a phone number or email address.",
            "Use a different contact.",
        )

    def _run_script(self, script_name: str, *args: str) -> dict[str, object]:
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise ContactsBridgeError(
                "SCRIPT_NOT_FOUND",
                f"Missing AppleScript file '{script_name}'.",
                "Restore the AppleScript file and try again.",
            )

        completed = subprocess.run(["osascript", str(script_path), *args], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise self._map_script_error(completed.stderr.strip() or completed.stdout.strip())

        output = completed.stdout.strip()
        if not output:
            return {}
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise ContactsBridgeError(
                "INVALID_SCRIPT_OUTPUT",
                f"AppleScript returned invalid JSON: {exc.msg}.",
                "Inspect the AppleScript output and ensure it returns valid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise ContactsBridgeError(
                "INVALID_SCRIPT_OUTPUT",
                "AppleScript output must decode to a JSON object.",
                "Inspect the AppleScript output and ensure it returns an object.",
            )
        return payload

    def _search_contacts_by_name(self, query: str) -> list[ContactSummary]:
        if not any(character.isalpha() for character in query):
            return []
        payload = self._run_script("search_contacts.applescript", query.strip())
        return [self._normalize_summary(item) for item in payload.get("items", []) if isinstance(item, dict)]

    def _map_script_error(self, error_text: str) -> ContactsBridgeError:
        lowered = error_text.lower()
        if "not authorized" in lowered or "contacts" in lowered and "not allowed" in lowered:
            return ContactsBridgeError(
                "PERMISSION_DENIED",
                "macOS denied access to Contacts.",
                "Allow Contacts access for the host app or terminal and retry.",
            )
        if "can't get person" in lowered or "can’t get person" in lowered:
            return ContactsBridgeError("CONTACT_NOT_FOUND", error_text, "Search contacts first to discover a valid contact id.")
        return ContactsBridgeError(
            "APPLESCRIPT_EXECUTION_FAILED",
            error_text or "AppleScript execution failed.",
            "Inspect Contacts.app state and the AppleScript file, then retry.",
        )

    def _normalize_summary(self, raw_contact: dict[str, object]) -> ContactSummary:
        phones = self._normalize_methods(raw_contact.get("phones"))
        emails = self._normalize_methods(raw_contact.get("emails"))
        return ContactSummary(
            contact_id=str(raw_contact.get("contact_id", "")),
            name=self._optional_text(raw_contact.get("name")) or "",
            first_name=self._optional_text(raw_contact.get("first_name")) or "",
            last_name=self._optional_text(raw_contact.get("last_name")) or "",
            organization=self._optional_text(raw_contact.get("organization")) or "",
            phone_count=int(raw_contact.get("phone_count", len(phones)) or len(phones)),
            email_count=int(raw_contact.get("email_count", len(emails)) or len(emails)),
            phones=phones,
            emails=emails,
        )

    def _normalize_detail(self, raw_contact: dict[str, object]) -> ContactDetail:
        summary = self._normalize_summary(raw_contact)
        return ContactDetail(**summary.model_dump(), note=self._optional_text(raw_contact.get("note")) or "")

    def _normalize_methods(self, raw_methods: object) -> list[ContactMethod]:
        if not isinstance(raw_methods, list):
            return []
        return [ContactMethod.model_validate(item) for item in raw_methods if isinstance(item, dict)]

    def _is_exact_match(self, contact: ContactSummary, query_text: str, normalized_query: str) -> bool:
        if query_text in {contact.name.lower(), contact.first_name.lower(), contact.last_name.lower()}:
            return True
        if contact.organization and query_text == contact.organization.lower():
            return True
        return any(self._normalize_lookup_value(method.value) == normalized_query for method in [*contact.phones, *contact.emails])

    def _is_partial_match(self, contact: ContactSummary, query_text: str, normalized_query: str) -> bool:
        haystacks = [contact.name, contact.first_name, contact.last_name, contact.organization]
        if any(query_text in value.lower() for value in haystacks if value):
            return True
        if normalized_query and any(normalized_query in self._normalize_lookup_value(method.value) for method in [*contact.phones, *contact.emails]):
            return True
        return False

    def _dedupe_contacts(self, contacts: list[ContactSummary]) -> list[ContactSummary]:
        seen: set[str] = set()
        result: list[ContactSummary] = []
        for contact in contacts:
            if contact.contact_id in seen:
                continue
            seen.add(contact.contact_id)
            result.append(contact)
        return result

    def _normalize_lookup_value(self, value: str) -> str:
        lowered = value.strip().lower()
        if "@" in lowered:
            return lowered
        return re.sub(r"\D+", "", lowered)

    def _serialize_methods(self, methods: list[ContactMethod] | None) -> str:
        if not methods:
            return ""
        rows: list[str] = []
        for method in methods:
            label = method.label.replace(METHOD_FIELD_SEPARATOR, " ").replace(METHOD_RECORD_SEPARATOR, " ")
            value = method.value.replace(METHOD_FIELD_SEPARATOR, " ").replace(METHOD_RECORD_SEPARATOR, " ")
            rows.append(f"{label}{METHOD_FIELD_SEPARATOR}{value}")
        return METHOD_RECORD_SEPARATOR.join(rows)

    def _optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if text.lower() == "missing value":
            return None
        return text or None


def build_bridge() -> AppleContactsBridge:
    return AppleContactsBridge(load_settings().scripts_dir)
