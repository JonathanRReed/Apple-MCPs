# Apple-MCPs

Apple-native MCP servers for macOS.

This repo gives AI agents direct, local access to core Apple apps through the Model Context Protocol, or MCP. In practice, that means an agent can call structured tools, read lightweight resources, and use built-in prompts instead of trying to control your Mac blindly.

## What MCP Means Here

Each MCP server in this repo runs locally on your Mac and exposes app-specific capabilities over `stdio`.

- tools let an agent take actions, like creating a reminder or sending a message
- resources let an agent read compact snapshots, like recent notes or today’s reminders
- prompts give agents better app-specific workflows, like planning the day or triaging communication

Because these servers run on your Mac, the Apple apps stay the system of record.

## Servers

- [Apple AIO MCP](./Apple-AIO-MCP/README.md), recommended. One unified server for Mail, Calendar, Reminders, Messages, Notes, and Shortcuts.
- [Apple Mail MCP](./AppleMail-MCP/README.md), for Mail-only workflows.
- [Apple Calendar MCP](./ICal-MCP/README.md), for Calendar-only workflows.
- [Apple Reminders MCP](./AppleReminders-MCP/README.md), for task and reminder workflows.
- [Apple Messages MCP](./AppleMessages-MCP/README.md), for iMessage and Messages workflows.
- [Apple Notes MCP](./AppleNotes-MCP/README.md), for notes and knowledge workflows.
- [Apple Shortcuts MCP](./AppleShortcuts-MCP/README.md), for running Apple Shortcuts from agents.

## Which One To Use

- Use `Apple-AIO-MCP` if you want one assistant entrypoint across the Apple apps in this repo.
- Use the standalone servers if you want tighter app boundaries, simpler permissions, or separate agent configs.

## Install On This Mac

<details>
<summary>Recommended, install the all-in-one server</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/Apple-AIO-MCP
./start.sh
```

`start.sh` creates a local virtual environment on first run, installs the Python dependencies from `requirements.txt`, and starts the MCP server over `stdio`.

</details>

<details>
<summary>Install one standalone server instead</summary>

Example:

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleMessages-MCP
./start.sh
```

Every server folder follows the same pattern:

- `manifest.json`
- `start.sh`
- `server.py`
- `README.md`
- `src/`
- `tests/`

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client, stdio config</summary>

Most MCP clients that support local `stdio` servers can point directly at a server `start.sh`.

Example for the all-in-one server:

```json
{
  "mcpServers": {
    "apple-aio": {
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/Apple-AIO-MCP/start.sh",
      "args": [],
      "env": {}
    }
  }
}
```

Example for a standalone server:

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleReminders-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

</details>

<details>
<summary>Claude Code example</summary>

Add the all-in-one server:

```bash
claude mcp add --transport stdio --scope project \
  apple-aio \
  -- /Users/jonathanreed/Downloads/Apple-MCPs/Apple-AIO-MCP/start.sh
```

Add a standalone server:

```bash
claude mcp add --transport stdio --scope project \
  apple-notes \
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleNotes-MCP/start.sh
```

</details>

## macOS Permissions

Different Apple apps require different permissions:

| Server | What macOS may ask for |
| --- | --- |
| Apple Mail | Automation access to Mail |
| Apple Calendar | Calendar access |
| Apple Reminders | Reminders access |
| Apple Messages | Automation access to Messages, plus Full Disk Access for history |
| Apple Notes | Automation access to Notes |
| Apple Shortcuts | Usually no separate privacy prompt |

## Repo Layout

- `Apple-AIO-MCP/`, unified server
- `AppleMail-MCP/`, Mail
- `ICal-MCP/`, Calendar
- `AppleReminders-MCP/`, Reminders
- `AppleMessages-MCP/`, Messages
- `AppleNotes-MCP/`, Notes
- `AppleShortcuts-MCP/`, Shortcuts
- `SharedAppleBridge/`, shared native bridge code used by EventKit-backed servers
- `.build/`, local helper build output

## Notes

- This suite is for macOS.
- Apple Messages history access still needs Full Disk Access.
- `ICal-MCP` keeps its historical folder name, but it is the Apple Calendar server.
