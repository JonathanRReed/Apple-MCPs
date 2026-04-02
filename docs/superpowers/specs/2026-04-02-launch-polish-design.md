# Launch Polish and Release Audit Design

Date: 2026-04-02
Scope: Final launch polish, release audit, and surface cleanup for the Apple MCP suite
Status: Proposed

## Goal

Run one final suite-wide pass that treats the repository as a launch product, not just a codebase. The pass should fix correctness issues, remove or consolidate redundant tool surface where that improves model performance, tighten packaging and docs, and make small high-value improvements that reduce user or agent friction without broadening scope.

Success means:

- no known launch blockers remain in the shipped MCPs or the unified server
- standalone MCPs and `Apple-Tools-MCP` present a consistent runtime contract
- tool surfaces are as small and strong as practical, with redundant or weaker overlap reduced where safe
- install and packaging paths are reliable from both monorepo and installed environments
- launch docs, checklists, and prompts reflect real behavior, limits, and best practices
- improvements made during this pass increase assistant quality without adding bloat

## Non-Goals

- adding new app domains
- adding tools just to increase capability count
- speculative assistant features that are not necessary for launch quality
- broad UI automation expansion beyond the already approved bounded fallback model
- entitlement-backed or paid-signing features

## Principles

1. Fix launch blockers first.
2. Prefer fewer, stronger tools over a wider but noisier surface.
3. Keep standalone MCPs as source of truth for domain behavior.
4. Improve the unified layer where it makes routing more native or more reliable.
5. Do not keep weak overlaps if one path is clearly the better contract.
6. Be honest about platform limits instead of smoothing them over with hidden fallbacks.

## Audit Areas

### 1. Correctness and Reliability

Check:

- broken code paths
- stale instruction strings that route agents incorrectly
- mismatched runtime defaults
- packaging drift
- helper-resource path issues
- install or reload regressions
- incorrect health or permission reporting

Fix anything that could cause an E2E run to fail, silently degrade, or mislead the operator.

### 2. Tool Surface Quality

Audit tool overlap across standalone MCPs and `Apple-Tools-MCP`.

Look for:

- duplicate tools that differ only by naming or wrapper thickness
- weak wrappers that add noise without improving routing
- overlapping assistant-facing tools where one should be the canonical path
- low-signal tools that hurt model routing more than they help

Actions allowed:

- consolidate overlapping tools
- hide or remove clearly redundant assistant-facing wrappers
- improve descriptions and instruction strings so discovery is cleaner
- keep raw standalone domain tools when they are still needed as source-of-truth primitives

Constraint:

- do not remove real capability that a user or agent needs
- only reduce surface where a stronger path clearly exists

### 3. Packaging and Install Paths

Audit:

- standalone `start.sh` flows
- installed package data for AppleScripts and helper resources
- monorepo fallback versus installed-package imports
- manifests and runtime defaults
- root install helpers and README setup examples

Success bar:

- fresh install works without manual copying or patching
- standalone and unified behavior are consistent with docs
- manifest-based installs and direct `start.sh` installs do not surprise the user with weaker defaults or missing assets

### 4. Health, Recovery, and Failure Honesty

Audit:

- health tools
- permission guides
- launch checklists
- failure-mode docs
- strict native-only acceptance paths such as Maps
- truthful support boundaries such as Focus and notifications

Improve any confusing or under-specified recovery path.

### 5. Small High-Value Improvements

Allowed only when they satisfy all of the following:

- improve reliability, routing, or assistant-native feel
- are tightly scoped
- do not introduce a large new surface area
- do not create another MCP or major subsystem

Examples of acceptable improvements:

- better default detection or persistence
- better disambiguation helpers
- clearer canonical wrappers
- stronger summary resources
- simpler health payloads
- better tool descriptions for model selection

Examples that should be rejected in this pass:

- new domains
- wide new automation surfaces
- large feature families
- low-signal helper tools that duplicate existing capability

## Expected Deliverables

### Standalone MCPs

Each shipped MCP should leave this pass with:

- reliable install behavior
- truthful health and permission reporting
- clean README launch guidance
- no obviously redundant or misleading tool names inside its own domain

### Apple-Tools-MCP

The unified server should leave this pass with:

- a clean assistant-facing surface
- strong model-facing instructions
- wrappers only where they improve routing, defaults, or safety
- fewer ambiguous overlaps where a canonical assistant path exists
- overview, today, prompt, and checklist surfaces aligned with the real product contract

## Public Interface Changes Allowed

This pass may:

- consolidate overlapping assistant-facing tools
- rename tools if a clearer contract is needed
- remove or stop documenting weak or redundant wrappers
- tighten descriptions, manifests, prompts, and checklist language

This pass should avoid:

- broad new feature growth
- new MCP packages
- large migration burdens for launch users

## Testing Strategy

### Code verification

- `ruff check` for touched packages
- focused `pytest` for touched packages
- repo-wide smoke paths where practical
- installed-environment validation when packaging or import behavior changes

### Product verification

- health checks for every shipped domain
- prompt and resource discovery in the unified surface
- review of public install examples and safety-mode examples
- launch checklist alignment with actual runtime behavior

### Surface review

- identify assistant-facing redundancy
- confirm any removals or consolidations improve clarity
- confirm tool count does not increase without strong justification

## Risks

1. Consolidation may remove a tool someone already depends on.
Mitigation: only consolidate when there is a clearly stronger canonical path and the removed surface is redundant rather than uniquely capable.

2. Polishing can turn into last-minute feature creep.
Mitigation: reject anything that expands scope more than it reduces friction.

3. Unifying too aggressively can weaken standalone MCP usefulness.
Mitigation: keep standalone MCPs as source of truth and focus consolidation mainly on the assistant-facing unified layer.

## Rollout Order

1. audit current surface and identify blockers, redundancies, and launch-drift
2. fix correctness and packaging issues
3. clean up tool overlap and assistant-facing descriptions
4. make small high-value improvements that reduce friction
5. update docs, prompts, and launch checklists
6. run final verification and repo cleanup

## Acceptance Bar

Do not call this pass complete until:

- no known launch blockers remain
- no public launch docs contradict runtime behavior
- the unified tool surface is cleaner, not noisier
- the repo remains honest about platform limits
- changes improve assistant quality without introducing bloat
