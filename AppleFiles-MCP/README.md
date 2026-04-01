# Apple Files MCP

Local MCP server for file and folder access on macOS.

## Capabilities

- list allowed file roots
- inspect directory contents
- search files and folders by name
- read UTF-8 text files
- inspect file metadata
- list recent files
- create folders
- move or rename paths
- delete files or empty folders
- resources: `files://allowed-roots`, `files://recent`
- prompts: `files_prepare_attachment`, `files_organize_workspace`

## Install On This Mac

```bash
cd /path/to/Apple-MCPs/AppleFiles-MCP
./start.sh
```

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-files": {
      "command": "/path/to/Apple-MCPs/AppleFiles-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "/Users/you/Desktop,/Users/you/Documents,/Users/you/Downloads",
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_readonly"
      }
    }
  }
}
```

## Prompting Notes

- Use this server before Mail, Messages, Notes, or Shortcuts when the user references a local file or attachment.
- Confirm the exact path before sending or attaching a file.
- Keep `APPLE_FILES_MCP_ALLOWED_ROOTS` narrow for safety.
- Use `APPLE_FILES_MCP_SAFETY_MODE=safe_readonly` by default, `safe_manage` for create and move, and `full_access` only for delete workflows.

## Health And Recovery

- `files_health`
- `files_permission_guide`
- `files_list_allowed_roots`
