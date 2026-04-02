# Phase 2 macOS Context Expansion Design

Date: 2026-04-02
Scope: Phase 2 macOS context expansion for the Apple MCP suite
Status: Proposed

## Goal

Expand the suite's macOS-native context so the assistant can reason about Focus state, Finder-style file workflows, and iCloud Drive without introducing fake support claims or new thin MCPs.

Success means:

- Focus status is available as truthful system context
- Finder-style file actions are available through `AppleFiles-MCP`
- iCloud Drive is treated as a first-class file root instead of an accidental shell path
- Apple-Tools exposes this context in the unified workflow layer
- notification support remains honest, with no claim that the suite can read Notification Center history if macOS does not expose that cleanly

## Non-Goals

- adding separate Finder, iCloud, or Focus MCPs
- claiming Notification Center history support through AppleScript when it does not exist
- broad computer-use or screenshot automation as a substitute for native system and file context
- Phase 3 domains such as Music, Podcasts, Photos, Health, or Screen Time

## Scope

This phase includes three workstreams:

1. Focus status in `AppleSystem-MCP`
2. Finder and iCloud Drive expansion in `AppleFiles-MCP`
3. Unified routing and briefing exposure in `Apple-Tools-MCP`

## Approach

Use the existing domain boundaries:

- `AppleSystem-MCP` owns macOS context
- `AppleFiles-MCP` owns file and Finder-adjacent workflows
- `Apple-Tools-MCP` owns orchestration and assistant-facing wrappers

This preserves install simplicity and keeps standalone MCPs as the source of truth.

## Workstream 1: Focus Status

### Problem

The assistant lacks a reliable sense of the user's active mode, which weakens daily briefing, interruption awareness, and contextual routing.

### Design

Add read-only Focus context to `AppleSystem-MCP`.

New tools:

- `system_get_focus_status`
- `system_get_context_snapshot`

New resource:

- `system://context`

Returned Focus data should only include what the suite can retrieve reliably on an unsigned local install path. Expected fields:

- whether a Focus mode is active
- best available Focus name, if discoverable
- timestamp of observation
- source and confidence metadata

If the system cannot reliably read the active Focus, return an honest partial result:

- `focus_supported: false`
- structured explanation of the limitation

### Notification Context

Do not claim Notification Center history support unless there is a real path. Instead:

- keep local notification sending
- add explicit non-support notes in health or docs if the user asks for missed notifications
- if a minimal truthful signal exists, expose it as partial system context only

## Workstream 2: Finder and iCloud Drive Through AppleFiles

### Problem

The current file layer is useful but still feels generic. It lacks several Finder-native workflows and does not present iCloud Drive as a clearly supported first-class root.

### Design

Extend `AppleFiles-MCP` with Finder-style operations that still fit a file-domain boundary.

New tools:

- `files_open_path`
- `files_reveal_in_finder`
- `files_get_tags`
- `files_set_tags`
- `files_add_tags`
- `files_remove_tags`
- `files_list_recent_locations`

New resources:

- `files://recent-locations`
- `files://icloud-status`

### iCloud Drive

Do not create a separate iCloud MCP.

Instead:

- include iCloud Drive in allowed-root detection when present
- add helper metadata to distinguish local roots from iCloud Drive roots
- expose whether a path is inside iCloud Drive
- keep path operations file-native, not cloud-API-shaped

### Finder Semantics

The Files server should provide Finder-adjacent behavior without pretending to replace Finder completely.

In-scope:

- reveal path in Finder
- open path in the default app
- manage Finder tags
- improve recent file and location visibility

Out of scope:

- Smart Folder creation
- Finder sidebar manipulation
- full Finder window automation

## Workstream 3: Apple-Tools Integration

### Problem

Even when the standalone servers grow, the unified assistant needs to surface this context in a way that feels useful instead of just exposing more raw tools.

### Design

Add unified wrappers:

- `apple_get_focus_status`
- `apple_get_system_context`
- `apple_open_file_path`
- `apple_reveal_in_finder`
- `apple_tag_file`

Briefing integration:

- include Focus context in daily and weekly briefings when available
- include iCloud-aware recent files in the overview or today resource
- distinguish local file context from iCloud Drive context

Routing:

- prefer Files for iCloud and Finder workflows, not shell fallbacks
- prefer System for Focus context
- continue to fail honestly where notification history is not supported

## Public Interface Changes

Planned `AppleSystem-MCP` additions:

- `system_get_focus_status`
- `system_get_context_snapshot`
- `system://context`

Planned `AppleFiles-MCP` additions:

- `files_open_path`
- `files_reveal_in_finder`
- `files_get_tags`
- `files_set_tags`
- `files_add_tags`
- `files_remove_tags`
- `files_list_recent_locations`
- `files://recent-locations`
- `files://icloud-status`

Planned `Apple-Tools-MCP` additions:

- `apple_get_focus_status`
- `apple_get_system_context`
- `apple_open_file_path`
- `apple_reveal_in_finder`
- `apple_tag_file`

## Error Handling

Focus:

- `FOCUS_STATUS_UNAVAILABLE`
- `FOCUS_UNSUPPORTED_ON_THIS_SETUP`

Files:

- `PATH_NOT_ALLOWED`
- `PATH_NOT_FOUND`
- `TAG_MUTATION_FAILED`
- `FINDER_REVEAL_FAILED`
- `ICLOUD_ROOT_UNAVAILABLE`

Notifications:

- explicit non-support or partial-support responses where appropriate

## Testing Strategy

### Unit tests

- Focus status parsing and partial-support behavior
- iCloud root detection
- Finder reveal and open-path dispatch
- tag read and write normalization
- Apple-Tools wrapper routing

### Integration tests

- system context resource includes Focus payload
- file resources expose iCloud-aware metadata
- briefings include Focus context when present

### Documentation verification

- docs describe Focus as best-effort but truthful
- docs do not claim Notification Center history read support
- Files docs clearly position Finder and iCloud support inside `AppleFiles-MCP`

## Risks

1. Focus status may not have a clean unsigned retrieval path.
Mitigation: ship a truthful partial-support response rather than a fake value.

2. Finder tags may behave differently across volumes and iCloud.
Mitigation: normalize tags carefully and surface precise path errors.

3. iCloud Drive paths may not exist on every machine.
Mitigation: treat iCloud roots as conditional and report availability explicitly.

4. The assistant may over-infer from partial Focus context.
Mitigation: include confidence or support metadata in the response shape.

## Rollout Order

1. Focus read support
2. Finder reveal and open-path support
3. File tags
4. iCloud-aware resources and helpers
5. Apple-Tools wrappers and briefing integration
6. Docs and E2E updates

## Out of Scope for Phase 3

- Music
- Podcasts
- Photos
- Health
- Screen Time

Each of those domains still needs an explicit feasibility and packaging review before implementation.
