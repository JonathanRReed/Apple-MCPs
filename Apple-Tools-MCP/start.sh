#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Preferred path: let uv manage the environment (workspace-aware, resolves the
# right Python and dependencies automatically).
if command -v uv >/dev/null 2>&1; then
  exec uv run --project "$DIR" python "$DIR/server.py" "$@"
fi

# Legacy fallback: plain venv bootstrap.
PYTHON_BIN="${APPLE_MCP_PYTHON:-python3}"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "error: Python 3.11+ is required (found: $("$PYTHON_BIN" --version 2>&1)). Install uv (https://docs.astral.sh/uv/) or set APPLE_MCP_PYTHON to a newer interpreter." >&2
  exit 1
fi

VENV="$DIR/.venv"
STAMP="$VENV/.requirements.sha256"
WANT_HASH="$(shasum -a 256 "$DIR/requirements.txt" | awk '{print $1}')"

needs_bootstrap=0
if [ ! -x "$VENV/bin/python" ]; then
  needs_bootstrap=1
elif ! "$VENV/bin/python" -c 'import mcp, pydantic, apple_mcp_common' >/dev/null 2>&1; then
  needs_bootstrap=1
elif [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$WANT_HASH" ]; then
  needs_bootstrap=1
fi

if [ "$needs_bootstrap" = "1" ]; then
  "$PYTHON_BIN" -m venv "$VENV"
  # Run pip from the server directory so relative editable paths in
  # requirements.txt (e.g. ../AppleMCPCommon) resolve regardless of the
  # caller's working directory.
  (cd "$DIR" && "$VENV/bin/python" -m pip install --quiet --upgrade pip && "$VENV/bin/python" -m pip install --quiet -r requirements.txt)
  printf '%s' "$WANT_HASH" > "$STAMP"
fi

exec "$VENV/bin/python" "$DIR/server.py" "$@"
