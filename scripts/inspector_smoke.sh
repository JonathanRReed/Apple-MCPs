#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_inspector_check() {
  local package="$1"
  local method="$2"
  local expected_key="$3"
  local require_nonempty="${4:-1}"
  local output_file

  output_file="$(mktemp)"
  trap 'rm -f "$output_file"' RETURN

  echo "==> ${package}: ${method}"
  (
    cd "$ROOT/$package"
    npx -y @modelcontextprotocol/inspector --cli bash ./start.sh --method "$method" >"$output_file"
  )

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
