# Failure Modes

Use this guide when an agent or operator hits a known failure path during setup or execution.

## Full Disk Access is missing for Messages history

Symptoms:
- `messages_health` reports send access but not history access
- search or history tools return blocked or empty history results

What to do:
1. Call `messages_permission_guide`
2. Grant Full Disk Access to the host app or terminal running the MCP
3. Call `messages_recheck_permissions`
4. Retry the history operation

Notes:
- send and reply can still work even when history is blocked
- treat history failure separately from Messages automation failure

## Calendar access is not granted

Symptoms:
- `calendar_health` reports `access_status` of `not_determined`, `denied`, or no read access
- event queries look empty even though the user expects data

What to do:
1. Call `calendar_permission_guide`
2. Grant Calendar access in macOS privacy settings
3. Call `calendar_recheck_permissions`
4. Retry the event query before assuming the calendar is empty

## Mail search returns no results

Symptoms:
- `mail_search_messages` returns an empty list

What to check:
1. Confirm the query is not blank
2. Retry with a sender fragment, subject fragment, or `*`
3. If the user meant a thread, use `mail_get_thread` or search by a stronger hint
4. If the user meant recent mail, explain that there is no list-all recent-mail endpoint and ask for a query

## Contacts resolve multiple matches

Symptoms:
- Contacts search returns more than one plausible person

What to do:
1. Do not send yet
2. Present the candidate contacts clearly
3. Ask once for the intended person
4. Resolve again, then continue with Mail or Messages

Notes:
- this is especially important for person-based message routing
- `Apple-Tools-MCP` should always resolve through Contacts before it sends

## MCP task mode is unsupported by the client

Symptoms:
- the client ignores task execution metadata
- task handles are not surfaced to the user

What to do:
1. Call the task-capable Apple-Tools tool normally
2. Accept the direct synchronous result
3. Do not block the workflow on task support

Notes:
- task support in `Apple-Tools-MCP` is optional and experimental
- daily briefing, weekly briefing, and communications triage should still work without task-aware clients

## Accessibility is missing for System GUI fallback

Symptoms:
- `system_gui_*` tools return `ACCESSIBILITY_PERMISSION_REQUIRED`
- menu clicks, key presses, or button clicks fail even though read-only System tools work

What to do:
1. Call `system_permission_guide`
2. Grant Accessibility access to the host app or terminal in System Settings -> Privacy & Security -> Accessibility
3. Retry the GUI fallback tool
4. Prefer native domain MCP tools where possible instead of repeating GUI automation

Notes:
- this affects bounded GUI fallback tools, not the whole suite
- explicit System settings writes should still be preferred over GUI fallback for macOS preference changes

## Focus status or notification history is unavailable

Symptoms:
- `system_get_focus_status` reports `focus_supported: false`
- `system_get_context_snapshot` reports `notification_history_supported: false`

What to do:
1. Treat the result as a truthful platform limit on this setup
2. Continue the workflow without inventing active Focus state or missed notifications
3. Use the frontmost app, battery state, calendar, reminders, and recent communications as alternate context

Notes:
- this is not a failure if the MCP reports the limitation clearly
- do not patch around it with fake shell parsing or unsupported UI scraping and still call the run a pass
