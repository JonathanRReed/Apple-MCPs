#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python3"
REQUIREMENTS_FILE="$DIR/requirements.txt"
STAMP_FILE="$VENV_DIR/.requirements.sha256"

need_bootstrap=0

if [ ! -x "$PYTHON_BIN" ]; then
    python3 -m venv "$VENV_DIR"
    need_bootstrap=1
fi

expected_hash="$(shasum -a 256 "$REQUIREMENTS_FILE" | awk '{print $1}')"
current_hash="$(cat "$STAMP_FILE" 2>/dev/null || true)"

if [ "$current_hash" != "$expected_hash" ]; then
    need_bootstrap=1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

required = ("mcp", "pydantic")
missing = [name for name in required if importlib.util.find_spec(name) is None]
raise SystemExit(0 if not missing else 1)
PY
then
    need_bootstrap=1
fi

if [ "$need_bootstrap" -eq 1 ]; then
    "$PYTHON_BIN" -m pip install -q --upgrade pip setuptools wheel
    "$PYTHON_BIN" -m pip install -q -r "$REQUIREMENTS_FILE"
    printf '%s\n' "$expected_hash" > "$STAMP_FILE"
fi

exec "$PYTHON_BIN" "$DIR/server.py"
