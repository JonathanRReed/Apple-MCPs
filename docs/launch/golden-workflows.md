# Golden Workflows

These workflows are the launch-standard paths that should feel Apple-native when an agent uses this suite.

## 1. Resolve a contact, then text them

Recommended server:
- `Apple-Tools-MCP`

Expected flow:
1. Resolve the person through Contacts first.
2. If multiple contacts match, ask once and do not send yet.
3. Choose Messages only after the contact resolves to a message-ready phone number or email.
4. Omit `service_name` on iMessage sends.

Core tools:
- `apple_prepare_communication`
- `apple_preview_communication`
- `apple_send_communication`

Standalone equivalent:
- `contacts_search_contacts`
- `contacts_resolve_message_recipient`
- `messages_send_message`

## 2. Turn an email into a reminder and note

Recommended server:
- `Apple-Tools-MCP`

Expected flow:
1. Find the target mail message or thread.
2. Extract the follow-up context.
3. Create a reminder in the default list or the selected list.
4. Create a note in the default folder or the selected folder.
5. Return both created object ids and the source message id.

Core tools:
- `mail_search_messages`
- `mail_get_message`
- `apple_capture_follow_up_from_mail`

Standalone equivalent:
- `mail_search_messages`
- `mail_get_message`
- `reminders_create_reminder`
- `notes_create_note`

## 3. Generate daily and weekly briefings

Recommended server:
- `Apple-Tools-MCP`

Expected flow:
1. Read calendar state, reminders, recent messages, recent notes, system context, and recent files.
2. Generate a concise daily or weekly summary.
3. Store the result in Notes when the user asks for a persistent digest.
4. If the client supports MCP tasks, task-capable tools may run asynchronously.
5. If the client does not support tasks, the same tools should still return a direct result.

Core tools:
- `apple_generate_daily_briefing`
- `apple_generate_weekly_briefing`
- `apple_create_note_with_defaults`

## 4. Create an event, then create follow-up reminders

Recommended server:
- `Apple-Tools-MCP`

Expected flow:
1. Confirm title, date, start time, end time, and calendar before writing.
2. Create the event in Calendar.
3. Create one or more reminders for preparation or follow-up.
4. Persist the reminder list selection so later flows feel native.

Core tools:
- `apple_create_event_interactive`
- `calendar_create_event`
- `apple_create_reminder_with_defaults`

Standalone equivalent:
- `calendar_create_event`
- `reminders_create_reminder`

## Launch expectations

- Contacts-first routing for person-based communication
- Health check before the first real action
- Permission-guide fallback when access is blocked
- Preview before destructive or externally visible actions when the client wants a confirm step
