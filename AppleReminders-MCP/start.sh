#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$DIR/.venv/bin/python3" ]; then
    python3 -m venv "$DIR/.venv"
    "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
fi

exec "$DIR/.venv/bin/python3" "$DIR/server.py"
