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
- search-first discovery through `search_tools` and `get_tool_info`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleFiles-MCP
./start.sh
```

`start.sh` bootstraps and repairs `.venv` as needed, reinstalls when `requirements.txt` changes, and starts the server over `stdio`.

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-files": {
      "command": "/path/to/Apple-MCPs/AppleFiles-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "/Users/you/Desktop,/Users/you/Documents,/Users/you/Downloads,/Users/you/Library/Mobile Documents/com~apple~CloudDocs",
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

## Prompting Notes

- `tools/list` is intentionally minimal. Use `search_tools` first, then `get_tool_info` for the deferred Files tool you need.
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

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleFiles-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Files tool surface is loaded into context
- Call `files_health` first
- If access looks wrong, call `files_permission_guide`
- Confirm `APPLE_FILES_MCP_ALLOWED_ROOTS` before any file mutation workflow
