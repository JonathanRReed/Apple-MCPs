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

# The Contacts helper shares one block (TCC responsibility handling) with the
# EventKit helper. Compare the text between the BEGIN/END markers.
shared_block() {
  sed -n '/^\/\/ BEGIN SHARED HELPER RESPONSIBILITY$/,/^\/\/ END SHARED HELPER RESPONSIBILITY$/p' "$1"
}
pim_block="$(shared_block "$ROOT_DIR/Apple-Calendar-MCP/src/apple_calendar_mcp/apple_pim_bridge.swift")"
contacts_block="$(shared_block "$ROOT_DIR/AppleContacts-MCP/src/apple_contacts_mcp/contacts_bridge.swift")"
if [ -z "$pim_block" ] || [ "$pim_block" != "$contacts_block" ]; then
  echo "DRIFT: the SHARED HELPER RESPONSIBILITY block differs between apple_pim_bridge.swift and contacts_bridge.swift" >&2
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "Bridge copies are in sync."
fi
exit "$fail"
