#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${1:-$ROOT_DIR/.venv}"

PACKAGES=(
  "AppleMCPCommon"
  "AppleMail-MCP"
  "Apple-Calendar-MCP"
  "AppleReminders-MCP"
  "AppleMessages-MCP"
  "AppleContacts-MCP"
  "AppleNotes-MCP"
  "AppleShortcuts-MCP"
  "AppleFiles-MCP"
  "AppleSystem-MCP"
  "AppleMaps-MCP"
  "Apple-Tools-MCP"
)

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel

for package in "${PACKAGES[@]}"; do
  "$VENV_DIR/bin/pip" install --quiet --editable "$ROOT_DIR/$package"
done

cat <<EOF
Installed Apple MCP packages into:
  $VENV_DIR

Run the unified server with:
  $VENV_DIR/bin/apple-tools-mcp

Or run any standalone server with:
  $VENV_DIR/bin/apple-mail-mcp
  $VENV_DIR/bin/apple-calendar-mcp
  $VENV_DIR/bin/apple-reminders-mcp
  $VENV_DIR/bin/apple-messages-mcp
  $VENV_DIR/bin/apple-contacts-mcp
  $VENV_DIR/bin/apple-notes-mcp
  $VENV_DIR/bin/apple-shortcuts-mcp
  $VENV_DIR/bin/apple-files-mcp
  $VENV_DIR/bin/apple-system-mcp
  $VENV_DIR/bin/apple-maps-mcp
EOF
