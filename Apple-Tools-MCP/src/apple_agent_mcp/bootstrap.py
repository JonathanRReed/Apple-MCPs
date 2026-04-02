from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

@dataclass(frozen=True)
class DomainPackage:
    folder: str
    module: str
    distribution: str


DOMAIN_PACKAGES = (
    DomainPackage("AppleMail-MCP", "apple_mail_mcp", "apple-mail-mcp"),
    DomainPackage("Apple-Calendar-MCP", "apple_calendar_mcp", "apple-calendar-mcp"),
    DomainPackage("AppleReminders-MCP", "apple_reminders_mcp", "apple-reminders-mcp"),
    DomainPackage("AppleShortcuts-MCP", "apple_shortcuts_mcp", "apple-shortcuts-mcp"),
    DomainPackage("AppleNotes-MCP", "apple_notes_mcp", "apple-notes-mcp"),
    DomainPackage("AppleMessages-MCP", "apple_messages_mcp", "apple-messages-mcp"),
    DomainPackage("AppleContacts-MCP", "apple_contacts_mcp", "apple-contacts-mcp"),
    DomainPackage("AppleFiles-MCP", "apple_files_mcp", "apple-files-mcp"),
    DomainPackage("AppleSystem-MCP", "apple_system_mcp", "apple-system-mcp"),
    DomainPackage("AppleMaps-MCP", "apple_maps_mcp", "apple-maps-mcp"),
)


def _repo_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _missing_packages() -> list[DomainPackage]:
    return [package for package in DOMAIN_PACKAGES if not _module_available(package.module)]


def ensure_domain_paths() -> Path:
    missing = _missing_packages()
    if not missing:
        return _repo_dir()

    repo_dir = _repo_dir()
    for package in reversed(missing):
        src_dir = repo_dir / package.folder / "src"
        if src_dir.is_dir() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

    unresolved = _missing_packages()
    if unresolved:
        names = ", ".join(package.distribution for package in unresolved)
        raise ImportError(
            "Apple-Tools-MCP could not import required standalone packages: "
            f"{names}. Install the standalone Apple MCP packages into this environment, "
            "or run Apple-Tools-MCP from the Apple-MCPs monorepo so sibling src directories are available."
        )
    return repo_dir
