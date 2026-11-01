# MCP compatibility for 1.1.5

Reviewed October 26, 2026 against the [MCP 2026-07-28 specification](https://modelcontextprotocol.io/specification/2026-07-28), still the latest stable revision, and [Python SDK 2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0), still the latest SDK release.

The suite uses the official Python SDK and requires `mcp>=2.3.0,<3`.
Resource notifications use the SDK's subscription methods for modern protocols and its session notification methods for legacy protocols. A wire test verifies both legacy resource-update and list-change messages. All servers
report version 1.1.5 and expose JSON Schema inputs and structured outputs.
Streamable HTTP preserves sessions for legacy clients so their GET notification
streams remain available. MCP 2026-07-28 requests still use the SDK's
self-contained stateless request path. HTTP remains restricted to loopback addresses.
Remote access would require a separate authentication and deployment design.

Calendar asks the user which occurrences of a repeating event to change through
form elicitation. It uses the SDK's `Resolve`/`Elicit` resolvers, which send the
question as an `input_required` round trip on 2026-07-28 and as a mid-call
`elicitation/create` request on earlier revisions. Clients that do not declare
form elicitation are never asked; they get `RECURRING_EVENT_SCOPE_REQUIRED` instead.

## Protocol checks

The official [conformance runner](https://github.com/modelcontextprotocol/conformance)
is pinned to `0.2.0-alpha.12` with the frozen `2026-07-28` requirements. All
scored scenarios passed locally. The runner also executes 13 unscored extension
or pending scenarios. Eleven of those fail, accounting for all 31 failed
assertions in its aggregate output of 153 passed and 31 failed. They cover the
optional Tasks extension and pending schema/header behavior. This release does
not claim support for those unscored features.

The unified server enables synthetic fixtures only in conformance mode. These
exercise SDK behavior without reading local Apple data. Current conformance
mode uses SSE responses to test progress; production uses JSON responses.
Legacy checks use runner `0.1.16` and a separate documented baseline; every
failure in that run was an expected optional-feature failure.

`python scripts/protocol_smoke.py` checks all 11 real server entry points in
current and legacy modes. It validates tool discovery, input/output schemas,
structured results, missing-tool errors, and reported versions. The same checks
run against unpacked bundles through each manifest's launch command with
`python scripts/bundle_smoke.py` after building the bundles. All 22 runs of each
passed for 1.1.4. For 1.1.5 the 22 protocol runs passed; the bundle runs were
not repeated, because 1.1.5 changes no launch command; its only manifest change
is the Mail safety mode description.

CI runs current and legacy conformance separately, plus protocol and Inspector
checks. MCPB packaging uses `@anthropic-ai/mcpb@2.1.2` and Inspector uses
`@modelcontextprotocol/inspector@2.12.0`. Bundle manifests follow the
[MCPB manifest specification](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)
(manifest 0.4) and declare their generated tools and prompts. Registry records
use the `2025-12-11` `server.json` schema, still the latest, and all 11 generated
records validate with `mcp-publisher` 1.8.5.

## Upgrade check

1.1.5 changes only Files, Shortcuts and Mail safety checks and the development
lockfile. The 12 published 1.1.4 packages were installed from PyPI into a clean
virtual environment, then upgraded in place to the 1.1.5 wheels. Across all 11
servers (369 tools), tools, input and output schemas, annotations, prompts and
resources were compared over stdio before and after. The only differences were
the reported version; the `output_path` description on `shortcuts_run_shortcut`,
which now says the path must be inside the allowed folders; and on
`mail_reply_message` and `mail_reply_latest_in_thread`, a description sentence
on `safe_manage` drafts and two new output fields, `draft` and `note`, as
`mail_forward_message` already has. Each change appears in both the domain
server and Apple-Tools-MCP. No tool or parameter was added, removed, renamed or
retyped. Through the installed 1.1.5 servers, `files_move_path` with an allowed
root as its source returned `PATH_NOT_ALLOWED` and left the folder in place, and
`shortcuts_run_shortcut` returned `PATH_NOT_ALLOWED` for an `output_path`
outside the allowed folders, including one that used `..` to leave them, in both
the Shortcuts and unified servers.

For 1.1.4, the 12 published 1.1.3 packages were installed from PyPI into a clean virtual
environment, then upgraded in place to the 1.1.4 wheels. Every server's tools,
input and output schemas, annotations, prompts, resources and health output were
compared over stdio before and after. The only differences were the version
numbers and the intended Calendar changes: the new optional `scope` and
`occurrence_start_iso` inputs on `calendar_update_event` and
`calendar_delete_event`, their descriptions, and the new optional `recurring`,
`scope` and `occurrence_start` output fields. No tool, parameter or output field
was removed, renamed or retyped.

## Client and native-app checks

These checks were run for 1.1.4 and not repeated for 1.1.5, which changes no
Apple app integration. On macOS 27, dedicated test data exercised Notes folder and note operations,
Reminders list and reminder operations, and Calendar event creation, reads,
updates and deletion. All test records and containers were removed and the
removal was verified. Repeating Calendar events were exercised in a throwaway
local calendar: refused unscoped writes, single-occurrence, following and
whole-series deletes, occurrences edited on their own (including one moved onto
another occurrence's start), series time shifts, and the elicitation flow through
an in-process MCP client in both protocol modes.

Not checked live for this release: iCloud, CalDAV and Exchange calendars, macOS
15 and earlier, and how Claude Desktop, Claude Code or other hosts render the
Calendar elicitation form. Mail sending and Messages sending were not used for
release testing.

## Upgrade behavior

Mail attachments require `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT`. Paths must
resolve to regular files inside that directory; traversal, escaping symlinks,
and attachment transport separators are rejected. See the Mail README for setup.

Every domain package requires `apple-mcp-common>=1.1.5,<2`. The unified package
also requires each domain package at `>=1.1.5,<2`, so an upgrade brings in the
fixes together. Publishing checks validate these floors, all version fields, and
the complete distribution and bundle set. Release metadata records the exact
bundle hashes uploaded to GitHub.

The native Calendar and Reminders helpers are rebuilt when their source changes,
and macOS ties a helper's privacy grant to that build. Where the helper itself
holds Calendar or Reminders access, macOS asks once more after an upgrade that
changes the helper, as 1.1.4 did. 1.1.5 does not change the helpers.
