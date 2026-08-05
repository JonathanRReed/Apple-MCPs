#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Preferred path: uv workspace sync (creates $ROOT_DIR/.venv with every server
# and its console script installed).
if command -v uv >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && uv sync --all-packages)
  cat <<EOF
Installed the Apple MCP workspace into:
  $ROOT_DIR/.venv

Run the unified server with:
  $ROOT_DIR/.venv/bin/apple-tools-mcp

Or any standalone server, e.g.:
  $ROOT_DIR/.venv/bin/apple-mail-mcp
EOF
  exit 0
fi

# Legacy fallback: plain venv + pip, dependency order matters.
VENV_DIR="${1:-$ROOT_DIR/.venv}"
PYTHON_BIN="${APPLE_MCP_PYTHON:-python3}"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "error: Python 3.11+ is required (found: $("$PYTHON_BIN" --version 2>&1)). Install uv (https://docs.astral.sh/uv/) or set APPLE_MCP_PYTHON." >&2
  exit 1
fi

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

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel

for package in "${PACKAGES[@]}"; do
  "$VENV_DIR/bin/pip" install --quiet --editable "$ROOT_DIR/$package"
done

cat <<EOF
Installed Apple MCP packages into:
  $VENV_DIR

Run the unified server with:
  $VENV_DIR/bin/apple-tools-mcp

Or any standalone server, e.g.:
  $VENV_DIR/bin/apple-mail-mcp
EOF
