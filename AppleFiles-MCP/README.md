<!-- mcp-name: io.github.JonathanRReed/apple-files-mcp -->

# Apple Files MCP

Local MCP server for file, Finder-adjacent, and iCloud Drive workflows on macOS.

## Capabilities

- list allowed file roots
- inspect directory contents
- search files and folders by name
- read UTF-8 text files
- inspect file metadata
- list recent files
- open a path in the default app
- reveal a path in Finder
- read and write Finder tags
- list recent locations
- report local iCloud Drive availability
- create folders
- move or rename paths
- delete files or empty folders
- resources: `files://allowed-roots`, `files://recent`, `files://recent-locations`, `files://icloud-status`
- prompts: `files_prepare_attachment`, `files_organize_workspace`
- tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-files-mcp
```

No clone, no venv management.

</details>

<details>
<summary>From a clone</summary>

```bash
git clone https://github.com/JonathanRReed/Apple-MCPs.git
cd Apple-MCPs
uv sync --all-packages
```

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-files-mcp`). You can also point an MCP client at `AppleFiles-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-files": {
      "command": "uvx",
      "args": ["apple-files-mcp"],
      "env": {
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "/Users/you/Desktop,/Users/you/Documents,/Users/you/Downloads,/Users/you/Library/Mobile Documents/com~apple~CloudDocs",
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleFiles-MCP/start.sh` as the command with empty `args`.

Claude Code:

```bash
claude mcp add --transport stdio --scope project apple-files -- uvx apple-files-mcp
```

## Transport

`stdio` is the default and recommended transport. Set `APPLE_FILES_MCP_TRANSPORT=streamable-http` (with optional `APPLE_FILES_MCP_HOST` and `APPLE_FILES_MCP_PORT`) to serve Streamable HTTP instead.

## Prompting Notes

- `tools/list` returns the full Files tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Files tool they need.
- Use this server before Mail, Messages, Notes, or Shortcuts when the user references a local file or attachment.
- Use this server for Finder-style workflows, iCloud Drive paths, and file tagging, not raw shell fallbacks.
- Confirm the exact path before sending or attaching a file.
- Keep `APPLE_FILES_MCP_ALLOWED_ROOTS` narrow for safety.
- Include the local iCloud Drive root when you want the assistant to work with iCloud documents.
- Use `APPLE_FILES_MCP_SAFETY_MODE=safe_manage` for assistant workflows that need create and move, and `full_access` only for delete workflows.

## Health And Recovery

- `files_health`
- `files_permission_guide`
- `files_list_allowed_roots`
- `files_get_icloud_status`
- `files_list_recent_locations`
- `files_get_tags`

## Launch Checklist

- Add `uvx apple-files-mcp` (or a clone's `AppleFiles-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Files tool surface is loaded into context
- Call `files_health` first
- If access looks wrong, call `files_permission_guide`
- Confirm `APPLE_FILES_MCP_ALLOWED_ROOTS` before any file mutation workflow
