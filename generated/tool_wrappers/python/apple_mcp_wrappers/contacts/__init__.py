from __future__ import annotations

from .client import MCPToolCaller

from .contacts_health import contacts_health
from .contacts_permission_guide import contacts_permission_guide
from .contacts_recheck_permissions import contacts_recheck_permissions
from .contacts_list_contacts import contacts_list_contacts
from .contacts_search_contacts import contacts_search_contacts
from .contacts_get_contact import contacts_get_contact
from .contacts_resolve_message_recipient import contacts_resolve_message_recipient
from .contacts_find_duplicates import contacts_find_duplicates
from .contacts_suggest_merge_candidates import contacts_suggest_merge_candidates
from .contacts_create_contact import contacts_create_contact
from .contacts_update_contact import contacts_update_contact
from .contacts_delete_contact import contacts_delete_contact
from .contacts_list_prompts import contacts_list_prompts
from .contacts_get_prompt_prompt import contacts_get_prompt_prompt

__all__ = [
    "contacts_health",
    "contacts_permission_guide",
    "contacts_recheck_permissions",
    "contacts_list_contacts",
    "contacts_search_contacts",
    "contacts_get_contact",
    "contacts_resolve_message_recipient",
    "contacts_find_duplicates",
    "contacts_suggest_merge_candidates",
    "contacts_create_contact",
    "contacts_update_contact",
    "contacts_delete_contact",
    "contacts_list_prompts",
    "contacts_get_prompt_prompt",
]
