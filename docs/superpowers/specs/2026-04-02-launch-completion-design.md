# Launch Completion Design

Date: 2026-04-02
Scope: Phase 1 launch-completion work for the Apple MCP suite
Status: Proposed

## Goal

Close the remaining launch-quality gaps that prevent the suite from behaving like a reliable Apple personal assistant toolkit after a fresh install.

Success means:

- the public E2E checklist can run without non-Apple fallbacks for capabilities that claim native MCP support
- Apple-Tools enforces the right acceptance rules instead of silently degrading
- person-targeted workflows fail less often because duplicate contacts are surfaced before action
- digest generation has a stable Notes destination instead of polluting generic folders
- Shortcuts is used intentionally as an escalation path when native app coverage is insufficient

This phase does not add new app MCPs. It hardens the launch contract of the existing suite.

## Non-Goals

- adding new domains such as Music, Podcasts, Photos, Health, or Screen Time
- entitlement-gated features that require a paid Apple developer path
- broad GUI automation expansion beyond the bounded System fallback already shipped
- replacing the standalone MCPs as the source of truth for app-domain behavior

## Scope

This phase includes five workstreams:

1. Maps fail-closed behavior
2. Duplicate-contact detection
3. Persistent digest folder preference
4. Stronger Shortcuts routing
5. Stricter E2E acceptance rules and docs

## Approach

The unified server, `Apple-Tools-MCP`, will be the enforcement layer for assistant-quality behavior.

Standalone MCPs remain the domain implementations:

- `Apple Maps MCP` owns place search and route calculation
- `Apple Contacts MCP` owns contact search and duplicate detection
- `Apple Notes MCP` owns folder and note operations
- `Apple Shortcuts MCP` owns shortcut listing and execution

`Apple-Tools-MCP` adds policy:

- when a workflow may proceed
- when a workflow must fail
- when a workflow should route to Shortcuts instead of improvising
- where digests should be stored by default

This preserves clean domain ownership while making the unified server feel assistant-native.

## Workstream 1: Maps Fail-Closed Behavior

### Problem

Current E2E behavior can drift into non-Apple fallbacks such as URL opening, UI inspection, or external map APIs when the Maps helper is unavailable or not actually used. That makes acceptance misleading.

### Design

Add a Maps acceptance contract to `Apple-Tools-MCP`:

- workflows that claim place search or route estimation support must call `maps_health` first
- if `maps_health` reports the helper unavailable or unhealthy, Apple-Tools returns a structured error and stops
- Apple-Tools must not substitute shell, curl, OSM, web, or GUI-only fallbacks for supported Maps capabilities
- Apple-Tools should surface a clear remediation message when the helper is unavailable:
  - helper source missing
  - helper compile failed
  - helper timed out

Add assistant-facing wrappers:

- `apple_maps_search_places_strict`
- `apple_maps_get_directions_strict`

These wrappers:

- call the real Maps MCP
- record that a native Maps tool was used
- fail closed if the Maps helper is unavailable

### Acceptance

Maps steps pass only if:

- `maps_health.ok` is true
- `maps_health.helper_available` is true
- the workflow used `maps_search_places` or `maps_get_directions`, directly or through the strict Apple-Tools wrappers

Opening an Apple Maps URL is not sufficient for acceptance.

## Workstream 2: Duplicate Contact Detection

### Problem

Duplicate people records increase ambiguity and weaken every person-targeted workflow in Messages, Mail, and Calendar.

### Design

Add duplicate-detection support to `Apple Contacts MCP`.

New contact analysis tools:

- `contacts_find_duplicates`
- `contacts_suggest_merge_candidates`

Matching signals:

- normalized full name
- nickname and parenthetical nickname
- normalized phone numbers
- normalized email addresses

Result model:

- duplicate group identifier
- confidence score
- evidence list
- contact summaries per candidate
- merge recommendation, if confident

Apple-Tools behavior:

- before person-targeted sends, check for likely duplicate ambiguity when multiple candidate contacts are returned
- if a duplicate group is involved, return a structured ambiguity response instead of guessing
- expose unified wrappers:
  - `apple_find_duplicate_contacts`
  - `apple_prepare_unique_contact`

### Non-goal for this phase

Automatic contact merge is out of scope. This phase is detection and disambiguation, not destructive cleanup.

## Workstream 3: Persistent Digest Folder Preference

### Problem

Daily and weekly digests currently land in a generic Notes destination unless the user manually sets a preference. That is not assistant-grade behavior.

### Design

Extend Apple-Tools preferences to support a dedicated digest folder:

- `default_digest_folder_id`
- `default_digest_folder_name`
- `default_digest_account_name`

Detection logic:

- prefer an existing folder named `Digests`
- if absent, optionally create a `Digests` folder in the preferred Notes account during explicit digest setup
- persist the chosen folder as the digest destination

New Apple-Tools helpers:

- `apple_detect_digest_folder`
- `apple_set_digest_folder`
- `apple_ensure_digest_folder`

Digest generation behavior:

- daily and weekly digest tools use the digest folder preference first
- if the folder is missing, they can auto-repair by re-detecting or creating it, depending on the workflow
- tool results should report the folder actually used

### Notes

This is intentionally separate from the general `default_notes_folder_id`. Digests are a special assistant artifact and deserve their own home.

## Workstream 4: Stronger Shortcuts Routing

### Problem

Shortcuts already exists in the suite, but Apple-Tools does not yet use it as an intentional bridge when native coverage is incomplete. Agents can miss the best path and improvise with shell or UI work.

### Design

Add Shortcut escalation policy in Apple-Tools.

New behavior:

- when a request is outside native MCP support but maps well to a likely shortcut workflow, Apple-Tools should prefer Shortcuts over ad hoc fallbacks
- if the request names a shortcut explicitly, Apple-Tools should route there first
- if the request is vague but shortcut-shaped, Apple-Tools should list likely shortcuts and choose only when confidence is sufficient

New Apple-Tools helpers:

- `apple_route_or_run_shortcut`
- `apple_list_shortcuts_for_capability`

Routing hints should cover:

- app gaps
- multi-app automation requests
- user-specific automations already captured in Shortcuts

### Safety

Apple-Tools should still show the chosen path clearly:

- native MCP path
- shortcut bridge path
- unsupported path

## Workstream 5: E2E Acceptance Rules and Docs

### Problem

The launch docs and demo prompts are not strict enough about what counts as a pass. That allows unsupported fallbacks to be mistaken for native MCP success.

### Design

Update tracked launch docs:

- `docs/launch/demo-script.md`
- `docs/launch/golden-workflows.md`
- `docs/launch/prompts/checklist-template.md`
- `docs/launch/prompts/per-server-e2e-checklist.md`
- root `README.md`
- `Apple-Tools-MCP/README.md`

Rules to document:

- do not use shell, curl, or external APIs when a native MCP already claims support
- do not use UI-only fallbacks for acceptance when a structured MCP exists for that capability
- Maps acceptance requires native Maps MCP success
- assistant workflows must report whether they used:
  - native domain MCP
  - unified Apple-Tools wrapper
  - Shortcuts bridge

Add a reproducible E2E checklist contract:

- pass
- blocked by permission
- unsupported
- failed

No silent fallback may convert `unsupported` or `failed` into `pass`.

## Public Interface Changes

Planned new tools in `Apple-Tools-MCP`:

- `apple_maps_search_places_strict`
- `apple_maps_get_directions_strict`
- `apple_find_duplicate_contacts`
- `apple_prepare_unique_contact`
- `apple_detect_digest_folder`
- `apple_set_digest_folder`
- `apple_ensure_digest_folder`
- `apple_route_or_run_shortcut`
- `apple_list_shortcuts_for_capability`

Planned new tools in `Apple Contacts MCP`:

- `contacts_find_duplicates`
- `contacts_suggest_merge_candidates`

Preference schema additions in Apple-Tools:

- `default_digest_folder_id`
- `default_digest_folder_name`
- `default_digest_account_name`

## Error Handling

Maps:

- explicit `MAPS_HELPER_UNAVAILABLE`
- explicit `MAPS_NATIVE_REQUIRED`
- no fallback result masquerading as native success

Contacts:

- explicit duplicate ambiguity responses
- evidence and candidate records included in the structured payload

Digests:

- explicit `DIGEST_FOLDER_MISSING`
- optional auto-repair path where appropriate

Shortcuts:

- explicit `SHORTCUT_ROUTE_UNCLEAR`
- explicit `SHORTCUT_NOT_FOUND`

## Testing Strategy

### Unit tests

- Apple-Tools Maps strict wrappers fail closed when helper is unavailable
- duplicate-contact detection covers:
  - exact duplicate names
  - nickname and parenthetical nickname
  - shared email
  - shared phone
- digest folder detection and creation logic
- shortcut routing policy decisions
- no acceptance path reports success when only non-native fallback data exists

### Integration tests

- Apple-Tools wrapper behavior against mocked Maps, Contacts, Notes, and Shortcuts responses
- preference persistence for digest folder setup

### Documentation verification

- every launch doc references the strict acceptance rules
- no public demo prompt suggests shell or external API fallback for native-supported capabilities

## Risks

1. Duplicate detection can be noisy.
Mitigation: ship confidence-scored results and avoid destructive auto-merge.

2. Digest folder auto-creation can create unwanted folders.
Mitigation: restrict auto-create to explicit setup helpers or digest workflows that clearly announce folder creation.

3. Shortcut routing can feel opaque.
Mitigation: include explicit route metadata in responses.

4. Maps helper failures can make the suite feel harsher.
Mitigation: fail clearly with remediation instead of silently degrading.

## Rollout Order

1. Maps strict wrappers and acceptance contract
2. Duplicate-contact detection
3. Digest folder preference and helpers
4. Shortcut routing improvements
5. Docs and E2E hardening

## Out of Scope for Later Phases

Phase 2:

- Focus status
- notification context
- Finder improvements
- iCloud workflow improvements

Phase 3:

- Music
- Podcasts
- Photos
- Health
- Screen Time

Each Phase 3 domain needs its own feasibility review before implementation.
