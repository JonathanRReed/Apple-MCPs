# MCP compatibility for 1.0.4

Reviewed September 4, 2026 against the [MCP 2026-07-28 specification](https://modelcontextprotocol.io/specification/2026-07-28) and [Python SDK 2.1.1](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.1.1).

The suite uses the official Python SDK and requires `mcp>=2.1.1,<3`.
Resource notifications use the SDK's subscription methods for modern protocols and its session notification methods for legacy protocols. A wire test verifies both legacy resource-update and list-change messages. All servers
report version 1.0.4 and expose JSON Schema inputs and structured outputs.
Streamable HTTP preserves sessions for legacy clients so their GET notification
streams remain available. MCP 2026-07-28 requests still use the SDK's
self-contained stateless request path. HTTP remains restricted to loopback addresses.
Remote access would require a separate authentication and deployment design.

## Protocol checks

The official [conformance runner](https://github.com/modelcontextprotocol/conformance)
is pinned to `0.2.0-alpha.11`, the release used for the frozen `2026-07-28`
requirements. All 37 scored scenarios passed locally. The runner also executes
13 unscored extension or pending scenarios. Eleven of those fail, accounting
for all 31 failed assertions in its aggregate output of 152 passed and 31 failed.
They cover the optional Tasks extension and pending schema/header behavior.
This release does not claim support for those unscored features.

The unified server enables synthetic fixtures only in conformance mode. These
exercise SDK behavior without reading local Apple data. Current conformance
mode uses SSE responses to test progress; production uses JSON responses.
Legacy checks use runner `0.1.16` and a separate documented baseline. That run
passed 24 scenarios with eight expected optional-feature failures.

`python scripts/protocol_smoke.py` checks all 11 real server entry points in
current and legacy modes. It validates tool discovery, input/output schemas,
structured results, missing-tool errors, and reported versions. The same checks
run against unpacked bundles through each manifest's launch command with
`python scripts/bundle_smoke.py` after building the bundles.

CI runs current and legacy conformance separately, plus protocol and Inspector
checks. MCPB packaging uses `@anthropic-ai/mcpb@2.1.2` and Inspector uses
`@modelcontextprotocol/inspector@2.5.0`. Bundle manifests follow the
[MCPB manifest specification](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)
and declare their generated tools and prompts.

## Client and native-app checks

Codex and Claude Code connected to the release candidate and completed tool
search and schema discovery. Claude Desktop accepted the unified 1.0.4 bundle
in its installer preview and reported all requirements met. Preview validation
alone does not establish an installed Desktop server connection.

On macOS 27.0, dedicated test data exercised Notes folder/note operations,
Reminders list/reminder operations, and Calendar event creation, reads, updates,
and deletion. The checks found and verified fixes for Notes folder deletion
and the Reminders list deletion response. All dedicated test records and
containers were removed. Contacts also passed a bounded read check.

The package suites passed 252 tests before publication. These checks do not
assert that every operation in every Apple app was exercised live. Mail sending
and Messages sending were not used for release testing.

## Upgrade behavior

Mail attachments require `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT`. Paths must
resolve to regular files inside that directory; traversal, escaping symlinks,
and attachment transport separators are rejected. See the Mail README for setup.

Every domain package requires `apple-mcp-common>=1.0.4,<2`. The unified package
also requires each domain package at `>=1.0.4,<2`, so an upgrade brings in the
security and runtime fixes together. Publishing checks validate these floors,
all version fields, and the complete distribution and bundle set. Release
metadata records the exact bundle hashes uploaded to GitHub.
