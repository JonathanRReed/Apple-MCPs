# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

## [1.1.0] - 2026-10-10

### Added
- A Contacts-framework backend for list, get, search, create, update, delete and permission checks. The previous backend remains available with `APPLE_CONTACTS_MCP_BACKEND=applescript`. Native writes preserve omitted phone/email collections and clear explicit empty collections. Nonempty notes require a macOS entitlement and are rejected before a native write. Adapted from Jaume Puig's work in [JaumeAP/Apple-MCPs](https://github.com/JaumeAP/Apple-MCPs/commit/cb60c29fc11a56c72d8817f3e5aa1126900bff13). (#44)
- Calendar relative and absolute alarms, with native EventKit create/read/list/preserve/replace/clear support. Responses retain location-alarm metadata. Relative inputs accept whole minutes from 0 through 525600; absolute inputs require a timezone. Thanks to LightSpeedSpirit for the original alarm contribution in #26. (#44)
- Calendar batch ID lookup that preserves request order and distinguishes confirmed absence from unknown outcomes, adapted from LightSpeedSpirit's proposal in #27. (#36)

### Security
- Reject unknown safety-mode settings as read-only, require safe Files moves to remain within their allowed roots, and restrict writable System preference domains. (#45)
- Reject embedded NULs before resolving file move paths or calling native rename code; refuse destination replacement through an atomic exclusive rename. (#46)
- Require PyJWT 2.15.1 or newer within the 2.x series and refresh the locked version, addressing advisory records affecting the previous 2.13.0 dependency. (#39)

### Fixed
- Compile Contacts, Calendar and Reminders from immutable source snapshots into separate source-hash executables or bundles. A concurrent build cannot overwrite an installed winner, and a source change during compilation is rejected. Helper caches can use atomic exclusive rename when hard links are unsupported; unsupported cache locations return actionable errors. (#44, #45, #46)
- Read Notes body/plaintext in the application's context, reuse folder lookups, and preserve control characters and complex Unicode in Notes/Contacts script output. (#34)
- Resolve Contacts deletion without stale positional references, avoid unnecessary full scans for name-only misses, and preserve phone-extension matching and matching-method reporting. (#34, #37)
- Scope fallback Calendar identities and verify native-ID aliases before accepting them. Ambiguous, unavailable and conflicting identities remain unknown and cannot authorize writes. (#38, #45)
- Keep Calendar/Reminders date conversion consistent with UTC and preserve deadline and entity/writability checks. Mail subjectless lookup stays isolated to the requested mailbox. Native helper timeouts remain explicit errors with unknown mutation outcomes. (#43, #45)

### Changed
- Require suite packages at version 1.1.0 or newer within the 1.x series so standalone installs receive the new shared native and atomic helpers. (#39)
- Refresh Ruff to 0.16.10 and retain the locked Pydantic 2.13.5 update. (#40, #33)

### Compatibility and verification limits
- Full alarm replacement and clearing require native EventKit access. Calendar automation supports initial display alerts and unchanged existing alerts. It rejects edits requiring removal of existing alerts, or unreadable alert collections, before changing other event fields. Creation refusal cleans up only the new event; failed cleanup reports an unknown outcome. Health, standalone/unified tool discovery and READMEs expose the native requirement. Issue #41 remains open and partially addressed. (#44)
- Strict legacy fallback identifier collision checks can exceed the 30-second deadline on large calendar stores. Timeouts do not establish absence or permit mutation. Grant full native Calendar access and list events again to obtain native identifiers. No negative lookup shortcut or typed-reference API is introduced. (#44, #45)
- A controlled Notes creation timed out on the maintainer's Mac and returned `NOTE_CREATE_STATUS_UNKNOWN`; scoped fixture cleanup was verified. One explicit Contacts AppleScript get also timed out; native Contacts CRUD passed. No complete Notes CRUD or Contacts fallback parity is claimed.
- Controlled native tests use owned disposable fixtures on the maintainer's Mac. They do not establish behavior on every provider or the reporters' macOS 26 setups. Issues #32, #41 and #42 remain open for post-release retesting. Physical exFAT/SMB helper-cache testing has not been run.

## [1.0.5] - 2026-09-25

### Security
- Calendar read tools and resources now consistently enforce the `APPLE_CALENDAR_MCP_ALLOWED_CALENDARS` read scope, and writes fail closed when an allowlisted target cannot be resolved. Single-event reads keep their preflight policy checks. (#25, #29)

### Added
- `APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS`: an optional write-only allowlist that restricts event create, update, and delete to named calendars without hiding other readable calendars. When both allowlists are set, writes must pass both; `safe_readonly` still blocks all writes. (#25, #29)

### Fixed
- Mail `mail_get_message`, `mail_move_message`, and `mail_delete_message` (including archive-anchor reads) now resolve targets through evaluated account/mailbox matches and numeric-ID-filtered message lookups instead of positional references, verify the resolved ID, and reject ambiguous targets. This addresses the AppleScript `-1728` deletion and archiving failures reported in #23 on a Gmail account with ~190 mailboxes. The fix passed CI, native AppleScript compilation, and handler tests, but has not been confirmed on the reporter's live Mail/Gmail setup — #23 stays open pending confirmation. (#30)
- The Calendar helper now runs with a real application-bundle identity (`apple-calendar-pim-bridge.app`) so macOS attributes Automation and EventKit permission prompts to the helper instead of a transient process; previously compiled bare-binary helpers are migrated to the bundle layout automatically. (#24, #28)

### Changed
- Updated the MCP Python SDK from 2.1.1 to 2.2.0 across every server and `apple-mcp-common`. (#22)
- Tightened setup, permissions, and usage documentation.

## [1.0.4] - 2026-09-04

### Security
- Pass notification text through AppleScript arguments instead of interpolating it into code. (#18)
- Require an explicit Mail attachment directory. Reject paths outside it, escaping symlinks, non-files, and transport separators. Return structured validation errors for rejected attachments. (#16)
- Bound Contacts subprocess time and output size. Scan larger directories in pages, and report incomplete scans instead of silently omitting contacts. (#17)
- Restrict unauthenticated Streamable HTTP servers to loopback addresses. Network and wildcard binds now fail at startup.

### Fixed
- Calendar `update_event` no longer fails with `-10025` ("start date must be before end date") when an event is moved so that its new start lies after its old end: the AppleScript fallback now assigns the two boundaries in whichever order keeps the intermediate state valid. (#15)
- Send resource notifications through the current MCP subscription API while preserving legacy client support.
- Report the suite version in MCP server metadata and align the Mail settings default.
- Delete Notes folders by stable ID and map the Swift Reminders list deletion response to the public tool schema. Both fixes were verified in the native apps.
- Require matching shared and domain package versions so upgrades cannot retain incompatible or vulnerable older components.

### Changed
- Test the frozen MCP 2026-07-28 requirements with a pinned conformance runner. Keep legacy conformance and its optional-feature baseline separate.
- Check discovery, schemas, structured tool calls, errors, and current/legacy negotiation across every server. Validate isolated bundle launches through their manifest commands.
- Validate source versions and artifact counts before publishing. Publish PyPI packages in dependency order, create the GitHub release after all uploads succeed, and publish registry records through GitHub OIDC. Attach distributions plus exact registry metadata alongside bundles and checksums.
- Pin MCPB and Inspector tooling, declare generated bundle capabilities, and document Codex setup and attachment restrictions.

## [1.0.3] - 2026-09-01

### Added
- CI now enforces the vendored Swift bridge sync (`scripts/check_bridge_sync.sh`) and type-checks every Swift source with `swiftc -typecheck` on macOS.
- Dependabot keeps the uv lockfile and GitHub Actions current with weekly grouped update PRs.
- `scripts/bump_version.py` bumps the suite version across every package's `pyproject.toml`, `config.py`, `manifest.json`, and `server.json` in one step.
- `docs/troubleshooting.md` covers macOS Automation prompts, Calendar "Add Only" access, Notes timeouts, and common error codes.

### Changed
- CI runs on every pull request, including docs-only changes, so required status checks can never leave a merge waiting on a skipped workflow.
- Minimum dependency floors raised to `mcp>=2.1.1` and `pydantic>=2.13.5`; refreshed compatible transitive dependencies in the workspace lockfile.

### Fixed
- Calendar `create_event`, `get_event`, `update_event`, and `delete_event` now retry through the AppleScript fallback under write-only ("Add Only") Calendar access, matching the existing read-path fallback; the native bridge's `deleteEvent` now reports a missing event as `EVENT_NOT_FOUND` instead of a silent `deleted: false`. (#7)
- Notes AppleScript calls are now bounded by a configurable timeout (`APPLE_NOTES_MCP_SCRIPT_TIMEOUT_SECONDS`, default 60s) instead of hanging indefinitely, and `notes_create_note` resolves the ambiguous case where Notes commits the note but stalls afterwards: the created note is recovered by a deterministic folder/title lookup, or a structured `NOTE_CREATE_STATUS_UNKNOWN` error warns the client not to retry blindly. Post-create readbacks inside the AppleScript are also capped so the note id still comes back when Notes stalls on body/plaintext. (#6)
- Archive mailbox auto-detection now inspects Mail only instead of probing unrelated Calendar, Reminders, and Notes defaults.
- Unified-server tests no longer call live Contacts or filesystem resource bridges when their test data is mocked.

## [1.0.2] - 2026-08-05

### Fixed
- MCP Registry ownership markers in package READMEs now use the exact GitHub username casing (`io.github.JonathanRReed/...`) that the registry validates against.

## [1.0.1] - 2026-08-05

### Changed
- **Three packages renamed on PyPI** because their names were already taken by unrelated projects: the Mail server publishes as `apple-mcp-mail`, Notes as `apple-mcp-notes`, and Reminders as `apple-mcp-reminders` (matching the `apple-mcp-common` naming pattern). Module names, tool names, folders, and the original console scripts are unchanged; each package also installs a console script matching its new dist name, so `uvx apple-mcp-mail` works directly.
- Health tools now report the real package version (previously hardcoded to 0.1.0).

## [1.0.0] - 2026-08-05

Modernization release: the whole suite moves to the current MCP specification (2026-07-28, the first Linux Foundation-era spec release) and Python SDK 2.x, with a modern packaging and distribution story.

### Changed
- **MCP SDK v2 / spec 2026-07-28** across every server and `apple-mcp-common`. Servers now require `mcp>=2.0.0,<3`. SDK v2 servers still interoperate with clients speaking older protocol revisions.
- **Full tool surface by default.** `tools/list` now returns every tool (modern clients defer-load large tool surfaces themselves). `search_tools` and `get_tool_info` remain available as ordinary tools for context-constrained clients. The previous minimized-list behavior and its private-SDK-API implementation are gone.
- The repository is now a **uv workspace**: `uv sync --all-packages` builds one environment with every server's console script; `uv.lock` is committed. `start.sh` prefers `uv run` and falls back to a plain venv bootstrap with a Python 3.11+ guard.
- Task-capable briefing tools (`apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, `apple_triage_communications_task`) are now standard tools with the same names and results. The experimental tasks API they used was removed from the MCP spec (SEP-1686) and SDK.
- Per-resource subscribe/unsubscribe handlers were removed (spec 2026-07-28 replaced them with `subscriptions/listen`, which the SDK handles).
- Conformance-mode fixtures were trimmed to features that still exist in spec 2026-07-28 (sampling, logging/setLevel, and legacy elicitation fixtures removed).
- Generated code-mode wrapper index keys are now namespaced (`"mail/mail_send_message"` instead of colliding bare tool names).
- All packages are version 1.0.0, declare `license = "MIT"` metadata, and ship a LICENSE file.

### Fixed
- **Standalone Mail server tool names.** 17 of 20 tools were registered under wrong wire names (`health`, `mail_send_message_registered`, `mail_get_prompt_prompt`, ...). They now match the documented `mail_*` names used by the unified server, and Mail's health tool is visible again.
- **Transport env vars were silently ignored** by AppleFiles, AppleMaps, AppleShortcuts, and AppleSystem: `server.py` hardcoded stdio and bypassed `main()`. All launchers now go through `main()`, so `APPLE_<DOMAIN>_MCP_TRANSPORT=streamable-http` works everywhere (Calendar, Contacts, Notes, Messages, and Reminders gained the same env-driven transport support).
- **`start.sh` bootstrap was cwd-dependent**: it ran `pip install -r requirements.txt` without changing into the server directory, so the `-e ../AppleMCPCommon` line resolved against the MCP client's working directory and every documented install was broken. It also created venvs with whatever `python3` resolved to, with no version check.
- Drifted duplicate AppleScript directories removed (Mail's root-level copy had drifted from the packaged scripts the code actually loads); Contacts/Notes script-compilation tests now validate the packaged copies.
- Dead code removed: unused `cache.py` and `logging_utils.py` in Calendar, a no-op permissions stub in Apple-Tools, a stale `apple-aio-mcp` egg-info, and the orphaned `SharedAppleBridge/` copy of the Swift bridges.

### Migration notes
- If you pinned tool results by shape: tool wire names for the standalone Mail server changed (see above) — the unified server's names are unchanged.
- If your client relied on the minimized `tools/list`: all tools are listed now; use client-side deferred loading (Claude clients do this automatically) or the `search_tools`/`get_tool_info` pattern.
- If you launched servers through per-server `.venv`s: delete them and use `uv sync --all-packages` (or the new `start.sh`, which self-repairs).

## [0.1.0] - 2026-04-03

### Added
- Unified `Apple-Tools-MCP` server covering Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps.
- Standalone MCP servers for each supported Apple domain.
- Assistant defaults, contact-aware communication routing, preview helpers, undo helpers, and audit history in `Apple-Tools-MCP`.
- MCP prompt fallback tools for thinner clients.
- MCP completion, elicitation, resource subscription handling, and task-capable briefing tools in the unified server.
- Streamable HTTP support and protocol validation support where applicable.
- Inspector smoke checks and MCP conformance coverage for the unified server.

### Changed
- Renamed the unified server brand from `Apple-AIO-MCP` to `Apple-Tools-MCP`.
- Renamed the calendar server brand from `ICal-MCP` to `Apple-Calendar-MCP`.
- Standardized README routing guidance, permissions guidance, and launch instructions across the suite.

### Fixed
- Notes create and update AppleScript failures that dropped or failed to write body content.
- Contacts lookup and method extraction issues affecting recipient resolution.
- Messages and Calendar health reporting so blocked permissions are surfaced clearly.
- Unified routing behavior for communication, preview flows, and contact resolution.
