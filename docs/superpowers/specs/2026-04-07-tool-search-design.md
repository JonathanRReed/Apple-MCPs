# Search-First Tool Discovery and Code Wrapper Design

Date: 2026-04-07
Scope: Search-first MCP tool discovery, deferred schemas, and generated code wrappers across the Apple MCP suite
Status: Proposed

## Goal

Replace the current full-surface `tools/list` behavior with a search-first discovery model that keeps default MCP context small, preserves direct tool execution, and gives code-execution agents a generated wrapper layer that can be loaded incrementally.

Success means:

- every standalone Apple MCP and `Apple-Tools-MCP` exposes a small always-on tool surface
- discovery happens through explicit search and info tools instead of full default schema listing
- full tool schemas and examples are available on demand for any cataloged tool
- direct `call_tool` still works for cataloged tools even if they were never returned by the default `tools/list`
- generated code wrappers stay in sync with the live MCP tool registry
- README and protocol claims about deferred tool loading match actual runtime behavior

## Non-Goals

- preserving full `tools/list` compatibility for legacy clients as the default behavior
- changing domain ownership boundaries between standalone MCPs and `Apple-Tools-MCP`
- adding new Apple app domains
- introducing a stateful load-before-call requirement for tool execution
- hand-maintaining wrapper files or search metadata

## Principles

1. Optimize for search-aware clients and code-execution agents.
2. Keep one source of truth for runtime tool definitions, discovery metadata, and generated wrappers.
3. Preserve direct execution semantics once a tool name is known.
4. Keep the default discovery surface small, explicit, and deterministic.
5. Make failure paths helpful by returning likely matches and next actions.
6. Prefer shared infrastructure over per-server custom discovery logic.

## Scope

This design includes three workstreams:

1. shared search-first discovery infrastructure
2. search-first `tools/list` behavior for every Apple MCP server
3. generated code wrappers and wrapper indexes for code-execution clients

## Current Problem

The repository documentation already claims deferred tool behavior, but the runtime contract does not match that claim consistently.

Today:

- `Apple-Tools-MCP` overrides `list_tools` but still returns the full registered surface
- standalone servers mostly rely on default FastMCP tool listing, which also returns full tool schemas
- clients pay the context cost of the entire tool surface before they know which domain or tool they need
- code-execution agents have no generated wrapper layer, so they either ingest large tool surfaces or improvise their own invocation patterns

The result is extra context churn, weaker routing, and a mismatch between docs and protocol behavior.

## Approach

Use a search-first contract across the suite.

Each server will expose a tiny always-loaded surface:

- `search_tools`
- `get_tool_info`
- health
- permission guide
- permission recheck
- prompt and resource fallback tools where they remain useful
- a very small set of hot-path tools only when there is a strong latency justification

All other action tools become deferred from the perspective of `tools/list`, but remain callable by name.

The suite will generate and use a local discovery catalog per server. That catalog will power ranked tool search, on-demand schema lookup, and generated code wrappers for code-execution clients.

## Architecture

### Shared Discovery Module

Add a shared Python module that all Apple MCP servers can use for:

- registering catalog metadata for tools
- generating compact tool descriptors from runtime definitions
- exposing minimal `tools/list` behavior
- serving `search_tools`
- serving `get_tool_info`
- validating catalog to registry consistency

This shared module should be used by both the standalone servers and `Apple-Tools-MCP` so the suite does not drift into two discovery implementations.

### Generated Tool Catalogs

Each server gets a generated catalog file derived from the runtime tool registry and a small amount of author-maintained metadata.

Each catalog entry includes:

- `name`
- `domain`
- `title`
- `description`
- `usage_intent`
- `tags`
- `aliases`
- `risk_level`
- `read_only`
- `argument_summary`
- `example_calls`
- `schema_ref`

The catalog should be compact enough to search cheaply, but rich enough that a client can often choose a tool without loading the full schema first.

### On-Demand Tool Info

`get_tool_info(name, include_schema=true, include_examples=true)` returns the full definition for one tool.

Returned data should include:

- canonical tool name
- title and description
- full input schema
- structured-output metadata when available
- example calls
- hints such as read-only, idempotent, mutation risk, or permission-sensitive behavior

`get_tool_info` is an inspection path, not a prerequisite for execution.

### Generated Code Wrappers

Generate a code wrapper layer for all cataloged tools under a shared output directory.

Wrappers should be grouped by server and provide:

- one small typed wrapper per tool
- a shared transport client helper
- a wrapper index by server and by tool name
- docstrings copied from the same metadata used by the catalog
- example call snippets where practical

This gives code-execution agents a filesystem-searchable interface that can be loaded incrementally, mirroring the search-first model on the MCP side.

## Discovery Behavior

### Minimal `tools/list`

Default `tools/list` should be intentionally minimal.

It returns only:

- discovery tools
- health and permission tools
- prompt or resource fallback tools that are meant to remain always visible
- a tiny hot-path set only when explicitly justified

Default list output should be deterministic and compact, with no server-specific surprises.

### `search_tools`

Add `search_tools(query, limit=10, domain_tags=None, mode=\"compact\")`.

Behavior:

- searches the generated catalog
- ranks by exact name, alias, tag, domain, and semantic description overlap
- returns compact summaries by default
- supports richer modes for clients that want examples or schema refs inline

A `search_tools` result should include:

- `name`
- `title`
- `description`
- `domain`
- `tags`
- `risk_level`
- `argument_summary`
- `example_calls`
- `score` or ordering metadata

### Direct Tool Calls

Any cataloged tool remains callable through normal `call_tool(name, arguments)` even if it was not present in default `tools/list`.

This avoids a brittle stateful load flow and preserves a simple execution model:

1. discover by search or prior knowledge
2. optionally inspect with `get_tool_info`
3. call directly

### Unknown Tool Errors

If a client calls an unknown tool, the error response should include:

- the unknown name
- closest catalog matches
- a short recommendation to use `search_tools`

## Hot-Path Visibility Policy

The default policy is fully search-first. A tool should remain always visible only if all of the following are true:

- it is used as an operational prerequisite or recovery path
- search latency would materially hurt the common workflow
- exposing it always does not meaningfully bloat the default list

Examples that should remain visible:

- health
- permission guide
- permission recheck

Examples that should usually not remain visible:

- broad domain action tools
- one-off mutation helpers
- most delegated standalone tools in `Apple-Tools-MCP`

## Standalone Servers

Each standalone server should adopt the shared discovery contract.

That means:

- override default FastMCP `tools/list` behavior with the shared minimal list path
- register discovery tools consistently
- generate a per-server catalog during the build or verification flow
- keep the existing domain tool implementations as the execution source of truth

The standalone servers should not each invent their own search semantics.

## Apple-Tools-MCP

`Apple-Tools-MCP` should adopt the same search-first contract but with unified cross-domain metadata.

Additional requirements:

- delegated tools remain directly callable
- unified helpers and standalone delegated tools share one searchable catalog surface
- task-capable tools still advertise task support when loaded through `get_tool_info`
- prompts and resources stay discoverable through their existing protocol paths, with tool fallbacks left visible only where still necessary

The unified server should feel like the best search surface in the suite, not a larger copy of the standalone problem.

## Catalog Generation Model

The catalog should be generated from runtime registration data plus a small checked-in metadata layer.

Split responsibilities:

- runtime registry remains the source of truth for callable tool names and schemas
- checked-in metadata fills in aliases, tags, usage intent, and examples
- generation step validates that metadata entries map to real runtime tools

This prevents wrapper drift and avoids forcing verbose search metadata into every tool decorator.

## Code Wrapper Generation Model

Wrapper generation should produce:

- a per-server module tree
- a top-level registry file for search and lookup
- shared client helpers for MCP transport calls
- generated signatures that match the corresponding tool input schemas closely

Wrappers should be treated as generated artifacts with validation in tests, not as hand-edited source files.

## Rollout Plan

1. build the shared discovery module and catalog schema
2. migrate one standalone server and `Apple-Tools-MCP` as reference implementations
3. migrate the remaining standalone servers onto the shared pattern
4. add generated code wrappers and wrapper indexes
5. update docs, install guidance, and verification scripts to reflect the new contract

The default runtime mode should be search-first. A temporary compatibility flag may exist for debugging, but should not shape the primary design.

## Error Handling

### Search failures

When search returns no strong match, return:

- nearby matches
- related tags or domains
- suggested refined queries

### Catalog drift

If a catalog entry exists for a tool that is not actually callable, treat that as a build or generation failure and catch it in tests.

If a runtime tool exists without catalog coverage, that should also fail validation because it breaks the search-first contract.

### Wrapper drift

If generated wrappers no longer match the live registry or catalog metadata, fail generation checks and test verification.

## Testing Strategy

### Unit tests

- catalog entry normalization
- alias and tag ranking
- `search_tools` result shaping
- `get_tool_info` schema and example expansion
- unknown tool suggestion logic

### Server contract tests

- `tools/list` stays minimal and deterministic
- direct `call_tool` works for deferred tools
- health and permission tools remain visible
- `Apple-Tools-MCP` and standalone servers expose the same discovery contract

### Generation tests

- every runtime tool has exactly one catalog entry
- every catalog entry maps to a real runtime tool
- generated wrappers match live tool names and argument shapes

### Product verification

- MCP Inspector checks discovery behavior
- README examples reflect actual search-first flows
- code-execution wrapper examples work end to end

## Risks

1. Search quality may be weak if aliases and examples are under-specified.
Mitigation: treat metadata quality as part of the contract and test common synonyms.

2. Minimal `tools/list` may degrade older clients that depend on full default listing.
Mitigation: accept this trade-off by design, keep direct calls working, and optionally retain a temporary debug compatibility flag.

3. Generated wrappers may drift from runtime schemas.
Mitigation: make generation deterministic and block drift in tests.

4. Per-server migration could create inconsistent discovery behavior during rollout.
Mitigation: land the shared module first and migrate servers onto a single pattern.

## Acceptance Bar

Do not call this work complete until:

- every shipped Apple MCP uses the search-first discovery contract
- the default `tools/list` output is intentionally small across the suite
- `search_tools` and `get_tool_info` are the documented and tested discovery path
- direct tool execution works for deferred tools
- generated code wrappers exist and are validated against the live registry
- public docs no longer claim deferred behavior that the runtime does not actually implement
