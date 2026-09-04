#!/usr/bin/env bash
# Smoke-checks every MCP server in this repo through the official MCP
# Inspector CLI: tools/list against all 11 servers, plus prompts/list and
# resources/list on the servers that expose them.
#
# Requirements: uv (https://docs.astral.sh/uv/) and Node.js (npx).
# Portable to macOS's stock bash 3.2 (no associative arrays, no bash 4isms).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The inspector CLI is spawned with cwd inherited from this script, and
# `uv run` discovers the workspace from cwd, so run everything from the root.
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required (https://docs.astral.sh/uv/). Install it and re-run." >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "error: npx (Node.js) is required to run @modelcontextprotocol/inspector." >&2
  exit 1
fi

# Ensure the shared workspace venv has every server's console script
# installed. --inexact adds anything missing without uninstalling extras a
# developer may have synced (e.g. pytest/ruff from the dev extra).
uv sync --all-packages --inexact

# Map a package directory to its console-script name (bash 3.2 has no
# associative arrays, so use a case statement).
binary_for() {
  case "$1" in
    AppleFiles-MCP) echo "apple-files-mcp" ;;
    AppleSystem-MCP) echo "apple-system-mcp" ;;
    AppleMaps-MCP) echo "apple-maps-mcp" ;;
    AppleMail-MCP) echo "apple-mail-mcp" ;;
    Apple-Calendar-MCP) echo "apple-calendar-mcp" ;;
    AppleReminders-MCP) echo "apple-reminders-mcp" ;;
    AppleMessages-MCP) echo "apple-messages-mcp" ;;
    AppleContacts-MCP) echo "apple-contacts-mcp" ;;
    AppleNotes-MCP) echo "apple-notes-mcp" ;;
    AppleShortcuts-MCP) echo "apple-shortcuts-mcp" ;;
    Apple-Tools-MCP) echo "apple-tools-mcp" ;;
    *)
      echo "error: unknown package '$1'" >&2
      return 1
      ;;
  esac
}

CHECK_OUTPUT="$(mktemp)"
trap 'rm -f "$CHECK_OUTPUT"' EXIT

run_inspector_check() {
  local package="$1"
  local method="$2"
  local expected_key="$3"
  local require_nonempty="${4:-1}"
  local binary
  binary="$(binary_for "$package")"

  echo "==> ${package}: ${method}"
  # Launch the server through `uv run` so it uses the shared workspace venv.
  # Note: the inspector CLI mis-parses extra dash-flags in the server command,
  # so the command must stay flag-free; uv finds the workspace via cwd.
  npx -y @modelcontextprotocol/inspector@2.5.0 --cli uv run "$binary" --method "$method" >"$CHECK_OUTPUT"

  uv run --no-sync python - "$CHECK_OUTPUT" "$expected_key" "$package" "$method" "$require_nonempty" <<'PY'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
expected_key = sys.argv[2]
package = sys.argv[3]
method = sys.argv[4]
require_nonempty = sys.argv[5] == "1"

payload = json.loads(output_path.read_text())
if expected_key not in payload:
    raise SystemExit(f"{package} {method} did not return top-level key '{expected_key}'")

items = payload[expected_key]
if not isinstance(items, list):
    raise SystemExit(f"{package} {method} returned non-list payload for '{expected_key}'")

if require_nonempty and not items:
    raise SystemExit(f"{package} {method} returned an empty '{expected_key}' list")

print(f"OK {package} {method}: {len(items)} {expected_key}")
PY
}

packages="
AppleFiles-MCP
AppleSystem-MCP
AppleMaps-MCP
AppleMail-MCP
Apple-Calendar-MCP
AppleReminders-MCP
AppleMessages-MCP
AppleContacts-MCP
AppleNotes-MCP
AppleShortcuts-MCP
Apple-Tools-MCP
"

for package in $packages; do
  run_inspector_check "$package" "tools/list" "tools"
done

run_inspector_check "AppleFiles-MCP" "prompts/list" "prompts"
run_inspector_check "AppleFiles-MCP" "resources/list" "resources"
run_inspector_check "AppleSystem-MCP" "prompts/list" "prompts"
run_inspector_check "AppleSystem-MCP" "resources/list" "resources"
run_inspector_check "AppleMaps-MCP" "prompts/list" "prompts"
run_inspector_check "AppleMaps-MCP" "resources/list" "resources"
run_inspector_check "Apple-Tools-MCP" "prompts/list" "prompts"
run_inspector_check "Apple-Tools-MCP" "resources/list" "resources"

echo "Inspector smoke checks passed."
