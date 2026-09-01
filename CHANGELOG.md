# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Changed
- Refreshed compatible transitive dependencies in the workspace lockfile.

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
