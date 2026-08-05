#!/bin/bash
# The EventKit Swift bridge is intentionally vendored into each package that
# compiles it. This check fails when the copies drift apart.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail=0
if ! diff -q \
  "$ROOT_DIR/Apple-Calendar-MCP/src/apple_calendar_mcp/apple_pim_bridge.swift" \
  "$ROOT_DIR/AppleReminders-MCP/src/apple_reminders_mcp/apple_pim_bridge.swift" >/dev/null; then
  echo "DRIFT: apple_pim_bridge.swift differs between Apple-Calendar-MCP and AppleReminders-MCP" >&2
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "Bridge copies are in sync."
fi
exit "$fail"
