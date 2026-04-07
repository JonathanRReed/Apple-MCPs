#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED_VENV="$ROOT/.venv"

if [ ! -x "$SHARED_VENV/bin/python3" ]; then
  bash "$ROOT/scripts/install_all.sh" "$SHARED_VENV"
fi

declare -A BINARIES=(
  ["AppleFiles-MCP"]="apple-files-mcp"
  ["AppleSystem-MCP"]="apple-system-mcp"
  ["AppleMaps-MCP"]="apple-maps-mcp"
  ["AppleMail-MCP"]="apple-mail-mcp"
  ["Apple-Calendar-MCP"]="apple-calendar-mcp"
  ["AppleReminders-MCP"]="apple-reminders-mcp"
  ["AppleMessages-MCP"]="apple-messages-mcp"
  ["AppleContacts-MCP"]="apple-contacts-mcp"
  ["AppleNotes-MCP"]="apple-notes-mcp"
  ["AppleShortcuts-MCP"]="apple-shortcuts-mcp"
  ["Apple-Tools-MCP"]="apple-tools-mcp"
)

run_inspector_check() {
  local package="$1"
  local method="$2"
  local expected_key="$3"
  local require_nonempty="${4:-1}"
  local binary="${BINARIES[$package]}"
  local output_file

  output_file="$(mktemp)"
  trap 'rm -f "$output_file"' RETURN

  echo "==> ${package}: ${method}"
  npx -y @modelcontextprotocol/inspector --cli "$SHARED_VENV/bin/$binary" --method "$method" >"$output_file"

  python3 - "$output_file" "$expected_key" "$package" "$method" "$require_nonempty" <<'PY'
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

  rm -f "$output_file"
  trap - RETURN
}

packages=(
  "AppleFiles-MCP"
  "AppleSystem-MCP"
  "AppleMaps-MCP"
  "AppleMail-MCP"
  "Apple-Calendar-MCP"
  "AppleReminders-MCP"
  "AppleMessages-MCP"
  "AppleContacts-MCP"
  "AppleNotes-MCP"
  "AppleShortcuts-MCP"
  "Apple-Tools-MCP"
)

for package in "${packages[@]}"; do
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
