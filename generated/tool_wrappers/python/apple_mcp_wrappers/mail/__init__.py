from __future__ import annotations

from .client import MCPToolCaller

from .mail_health import mail_health
from .mail_permission_guide import mail_permission_guide
from .mail_recheck_permissions import mail_recheck_permissions
from .mail_list_mailboxes import mail_list_mailboxes
from .mail_search_messages import mail_search_messages
from .mail_get_message import mail_get_message
from .mail_get_thread import mail_get_thread
from .mail_compose_draft import mail_compose_draft
from .mail_send_message import mail_send_message
from .mail_reply_message import mail_reply_message
from .mail_forward_message import mail_forward_message
from .mail_mark_message import mail_mark_message
from .mail_move_message import mail_move_message
from .mail_delete_message import mail_delete_message
from .mail_reply_latest_in_thread import mail_reply_latest_in_thread
from .mail_archive_thread import mail_archive_thread
from .mail_list_prompts import mail_list_prompts
from .mail_get_prompt import mail_get_prompt

__all__ = [
    "mail_health",
    "mail_permission_guide",
    "mail_recheck_permissions",
    "mail_list_mailboxes",
    "mail_search_messages",
    "mail_get_message",
    "mail_get_thread",
    "mail_compose_draft",
    "mail_send_message",
    "mail_reply_message",
    "mail_forward_message",
    "mail_mark_message",
    "mail_move_message",
    "mail_delete_message",
    "mail_reply_latest_in_thread",
    "mail_archive_thread",
    "mail_list_prompts",
    "mail_get_prompt",
]
