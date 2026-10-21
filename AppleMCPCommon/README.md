# AppleMCPCommon

Shared Python helpers for the Apple MCP suite.

This internal package provides:

- search-first tool discovery
- catalog export helpers
- generated wrapper helpers
- shared parsing helpers for deferred tool-call responses
- safety-mode wording (`apple_mcp_common.safety`) so blocked tools and health checks tell users which setting to change
- bundle launch cleanup (`apple_mcp_common.bundle`) for Claude Desktop settings a client left unsubstituted
- generated artifacts under `generated/tool_catalogs` and `generated/tool_wrappers/python`

It is not a user-facing MCP server.
