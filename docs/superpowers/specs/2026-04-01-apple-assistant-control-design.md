# Apple Assistant Control Design

Date: 2026-04-01
Status: Proposed
Scope: Core launch suite, excluding Safari and Apple Home

## Goal

Make the Apple MCP suite capable of turning a general-purpose agent into a practical macOS personal assistant. The suite should complete the kinds of tasks a human assistant would handle across Apple apps and macOS itself, without pretending to offer unrestricted remote-control behavior where macOS automation is brittle or unsupported.

The launch bar is:

- standalone MCPs remain first-class and independently installable
- `Apple-Tools-MCP` remains the single unified entrypoint
- native app-domain MCPs stay the source of truth for app behavior
- macOS control gaps are filled by `AppleSystem-MCP`
- every mutating path is explicit, testable, and honest about whether it used native automation or GUI fallback

## User Need

The suite should let an agent:

- communicate through Mail and Messages using the right contact and account
- manage events, reminders, notes, files, and routes
- inspect and change the assistant-relevant parts of macOS settings
- recover gracefully when a native MCP cannot complete a task
- behave like a real Apple-native assistant rather than a loose collection of app tools

The suite does not need to simulate every low-level human interaction. It needs to complete assistant tasks reliably.

## Approaches

### 1. Native APIs only

Use only app-local AppleScript, Swift helpers, and domain tools. Do not add any GUI fallback path.

Pros:

- safest and simplest model
- easiest to reason about and test
- fewer macOS privacy and accessibility dependencies

Cons:

- leaves real gaps in system settings and app control
- some assistant tasks remain impossible even though a human could complete them
- makes `Apple-Tools-MCP` feel incomplete

### 2. Generic GUI automation everywhere

Treat the Mac like a desktop robot. Add broad System Events automation and route missing behaviors through UI scripting by default.

Pros:

- highest theoretical coverage
- can reach UI-only settings and workflows

Cons:

- fragile across OS versions, localization, and UI layout changes
- much harder to test and maintain
- risk of shipping fake reliability

### 3. Hybrid control plane, recommended

Keep native APIs and per-app MCPs as the primary path. Add a bounded GUI fallback layer inside `AppleSystem-MCP` for gaps that matter to assistant workflows. Expose whether fallback was used in every response.

Pros:

- best balance of coverage and reliability
- keeps standalone MCP contracts clear
- gives `Apple-Tools-MCP` a real assistant-grade fallback path

Cons:

- more implementation work than the native-only model
- requires explicit scope discipline

Recommendation: approach 3.

## Architecture

### Standalone MCPs

Each domain MCP remains authoritative for its app:

- Mail, Messages, Contacts, Calendar, Reminders, Notes, Shortcuts, Files, Maps, System

Those servers keep their native read and write surfaces. They should not reimplement another domain's logic.

### AppleSystem-MCP

`AppleSystem-MCP` becomes the macOS control plane. It owns:

- structured system status and settings reads
- safe, explicit settings writes
- GUI fallback primitives for frontmost-app automation
- a limited set of higher-level system actions that are broadly useful to assistants

### Apple-Tools-MCP

`Apple-Tools-MCP` becomes the orchestration layer. It should:

- prefer domain-native tools first
- fall back to System control only when the native domain cannot complete the action
- return preview data for risky mutations
- surface `used_gui_fallback: true` whenever GUI automation was required

## Control Scope

### A. System reads

`AppleSystem-MCP` should provide structured reads for assistant-relevant settings and context:

- appearance: light or dark mode, accent, highlight, wallpaper preference keys where readable
- accessibility: reduce motion, increase contrast, reduce transparency, hover text, text-size related preference keys where readable
- Finder: show extensions, show hidden files, path bar, status bar, default view style
- Dock: autohide, recents, size, magnification, orientation
- input and desktop context: clipboard, frontmost app, running apps, battery
- arbitrary preference-domain read for advanced fallback inspection

This does not mean every System Settings pane is fully modeled. It means the assistant-relevant settings surface is broad, structured, and trustworthy.

### B. System writes

`AppleSystem-MCP` should provide explicit write tools for a bounded settings set:

- appearance mode
- show all filename extensions
- show hidden files
- Finder path bar
- Finder status bar
- Dock autohide
- Dock show recents
- accessibility reduce motion
- accessibility increase contrast
- accessibility reduce transparency

Write tools should:

- validate inputs strictly
- use the native `defaults` path where possible
- restart affected system components only when required
- return both the requested value and the observed post-write value
- remain explicit, not a generic arbitrary-domain write API

### C. GUI fallback primitives

`AppleSystem-MCP` should add a narrow set of reusable GUI tools:

- activate application
- list menu bar items for the frontmost app
- click a named menu path
- press a key or key chord
- type text into the frontmost control
- click a button or UI element by label in the frontmost window
- choose a pop-up value in the frontmost window

These tools are fallback primitives, not the preferred path. They must require Accessibility permission and clearly report that GUI automation was used.

### D. Unified fallback routing

`Apple-Tools-MCP` should use the following order:

1. native standalone MCP tool
2. bounded `AppleSystem-MCP` fallback if native support is missing
3. actionable error that explains the missing permission or unsupported path

Examples:

- if a system setting change is requested, route directly to explicit System write tools
- if an app-native MCP can complete the task, never prefer generic UI scripting
- if a user asks for a simple app-launch or menu action that has no native domain equivalent, use System fallback

## App-Domain Improvements

### Mail

- keep sender-account selection dynamic and confirmed in responses
- keep thread-level helpers first-class
- improve “latest relevant message” targeting rather than forcing message-id-first usage

### Contacts

- keep person resolution central to communication routing
- preserve preferred-channel logic
- keep method editing explicit and structured

### Calendar

- keep collaboration fields, attendees, and recurrence readable
- use Calendar first for event mutation, not System fallback

### Reminders and Notes

- strengthen cross-linking between follow-up tasks and reference notes
- keep explicit boundaries: action items go to Reminders, reference material goes to Notes

### Files, Maps, and System

- show up in unified briefings and daily context
- remain directly callable as standalone domains

## Safety Model

The suite should be assistant-capable, not reckless.

- explicit writes are preferred over generic writes
- GUI fallback should be narrow and auditable
- destructive paths should preserve preview behavior where practical
- no tool should pretend success when macOS permissions or app capabilities block the action

Non-goals:

- arbitrary full desktop control
- bypassing macOS privacy prompts or accessibility restrictions
- fake support for settings or actions that are not reliably automatable

## Testing

### Standalone validation

- unit tests for each new System read and write path
- tests for fallback response metadata such as `used_gui_fallback`
- tests for post-write verification behavior

### Unified validation

- Apple-Tools tests for native-first routing and fallback routing
- fresh-install validation through `scripts/install_all.sh`
- `scripts/inspector_smoke.sh`
- MCP conformance against `Apple-Tools-MCP` over `streamable-http`

### Live smoke expectations

Before launch, the operator should verify:

- one self-send Mail flow with explicit `from_account`
- one self-send Messages flow
- one Calendar create or update flow
- one Reminder create flow
- one Note create or append flow
- one System read and one System write flow

## Rollout

### Phase 1

- broaden `AppleSystem-MCP` read surface
- add explicit, safe System write tools

### Phase 2

- add narrow GUI fallback primitives to `AppleSystem-MCP`
- surface fallback metadata in responses

### Phase 3

- wire native-first and fallback-aware orchestration into `Apple-Tools-MCP`
- fill remaining assistant-facing gaps in Mail, Notes, Reminders, Files, Maps, and System integration

## Launch Definition

The suite is launch-ready when:

- every standalone MCP is independently installable
- `Apple-Tools-MCP` works as a true unified entrypoint
- the System server covers assistant-relevant macOS reads and writes
- fallback behavior is explicit and bounded
- docs clearly describe permissions, fallback behavior, and capability boundaries
