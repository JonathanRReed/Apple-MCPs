from __future__ import annotations

from .client import MCPToolCaller

from .health import health
from .mail_permission_guide_registered import mail_permission_guide_registered
from .mail_recheck_permissions_registered import mail_recheck_permissions_registered
from .mail_list_mailboxes_registered import mail_list_mailboxes_registered
from .mail_search_messages_registered import mail_search_messages_registered
from .mail_get_message_registered import mail_get_message_registered
from .mail_get_thread_registered import mail_get_thread_registered
from .mail_compose_draft_registered import mail_compose_draft_registered
from .mail_send_message_registered import mail_send_message_registered
from .mail_reply_message_registered import mail_reply_message_registered
from .mail_forward_message_registered import mail_forward_message_registered
from .mail_mark_message_registered import mail_mark_message_registered
from .mail_move_message_registered import mail_move_message_registered
from .mail_delete_message_registered import mail_delete_message_registered
from .mail_reply_latest_in_thread_registered import mail_reply_latest_in_thread_registered
from .mail_archive_thread_registered import mail_archive_thread_registered
from .mail_list_prompts import mail_list_prompts
from .mail_get_prompt_prompt import mail_get_prompt_prompt

__all__ = [
    "health",
    "mail_permission_guide_registered",
    "mail_recheck_permissions_registered",
    "mail_list_mailboxes_registered",
    "mail_search_messages_registered",
    "mail_get_message_registered",
    "mail_get_thread_registered",
    "mail_compose_draft_registered",
    "mail_send_message_registered",
    "mail_reply_message_registered",
    "mail_forward_message_registered",
    "mail_mark_message_registered",
    "mail_move_message_registered",
    "mail_delete_message_registered",
    "mail_reply_latest_in_thread_registered",
    "mail_archive_thread_registered",
    "mail_list_prompts",
    "mail_get_prompt_prompt",
]
