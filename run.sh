#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing .venv. Follow the Linux setup instructions in README.md first." >&2
  exit 1
fi

"$PYTHON" -c '
import sys
if sys.version_info[:2] not in {(3, 11), (3, 12)}:
    raise SystemExit("Python 3.11 or 3.12 is required.")
'

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required. Install the current Node.js LTS release." >&2
  exit 1
fi

if [[ ! -d "$ROOT_DIR/portals/officer/node_modules" ]]; then
  echo "Frontend packages are missing. Run: npm --prefix portals/officer ci" >&2
  exit 1
fi

backend_pid=""
cleanup() {
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"
"$PYTHON" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
backend_pid=$!

echo "Alcohol Label Validator: http://127.0.0.1:5174/"
npm --prefix portals/officer run dev -- --host 127.0.0.1
