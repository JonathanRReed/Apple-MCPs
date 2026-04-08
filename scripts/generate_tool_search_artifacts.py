from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
COMMON_PATHS = [
    ROOT_DIR / "AppleMCPCommon" / "src",
    ROOT_DIR / "AppleFiles-MCP" / "src",
    ROOT_DIR / "AppleSystem-MCP" / "src",
    ROOT_DIR / "AppleMaps-MCP" / "src",
    ROOT_DIR / "AppleContacts-MCP" / "src",
    ROOT_DIR / "AppleMail-MCP" / "src",
    ROOT_DIR / "AppleMessages-MCP" / "src",
    ROOT_DIR / "AppleNotes-MCP" / "src",
    ROOT_DIR / "AppleReminders-MCP" / "src",
    ROOT_DIR / "AppleShortcuts-MCP" / "src",
    ROOT_DIR / "Apple-Calendar-MCP" / "src",
    ROOT_DIR / "Apple-Tools-MCP" / "src",
]

for path in reversed(COMMON_PATHS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


SERVER_SPECS = [
    {"module": "apple_files_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "files.json"},
    {"module": "apple_system_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "system.json"},
    {"module": "apple_maps_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "maps.json"},
    {"module": "apple_contacts_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "contacts.json"},
    {"module": "apple_messages_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "messages.json"},
    {"module": "apple_notes_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "notes.json"},
    {"module": "apple_reminders_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "reminders.json"},
    {"module": "apple_shortcuts_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "shortcuts.json"},
    {"module": "apple_calendar_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "calendar.json"},
    {"module": "apple_agent_mcp.tools", "attr": "TOOL_DISCOVERY", "catalog": "apple-tools.json"},
    {"module": "apple_mail_mcp.tools", "factory": "create_server", "server_attr": "_tool_discovery", "catalog": "mail.json"},
]


def _load_discovery(spec: dict[str, Any]):
    module = __import__(spec["module"], fromlist=["*"])
    if "factory" in spec:
        server = getattr(module, spec["factory"])()
        return getattr(server, spec["server_attr"])
    return getattr(module, spec["attr"])


async def _generate() -> None:
    catalogs_dir = ROOT_DIR / "generated" / "tool_catalogs"
    wrappers_dir = ROOT_DIR / "generated" / "tool_wrappers" / "python"
    shutil.rmtree(catalogs_dir, ignore_errors=True)
    shutil.rmtree(wrappers_dir, ignore_errors=True)
    catalogs_dir.mkdir(parents=True, exist_ok=True)
    wrappers_dir.mkdir(parents=True, exist_ok=True)

    for spec in SERVER_SPECS:
        discovery = _load_discovery(spec)
        await discovery.write_catalog_json(catalogs_dir / spec["catalog"])
        await discovery.generate_python_wrappers(wrappers_dir)


def main() -> None:
    asyncio.run(_generate())


if __name__ == "__main__":
    main()
