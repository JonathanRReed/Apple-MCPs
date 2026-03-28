from __future__ import annotations

from pathlib import Path
import sys

DOMAIN_FOLDERS = (
    "AppleMail-MCP",
    "Apple-Calendar-MCP",
    "AppleReminders-MCP",
    "AppleShortcuts-MCP",
    "AppleNotes-MCP",
    "AppleMessages-MCP",
    "AppleContacts-MCP",
)


def ensure_domain_paths() -> Path:
    repo_dir = Path(__file__).resolve().parents[3]
    for folder_name in reversed(DOMAIN_FOLDERS):
        src_dir = repo_dir / folder_name / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
    return repo_dir
