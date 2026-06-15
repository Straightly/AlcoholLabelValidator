#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"
HOST="${ALV_HOST:-127.0.0.1}"
PORT="${ALV_PORT:-8000}"
export ALV_OCR_ENGINE="paddle"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing .venv. Follow the Linux setup instructions in README.md first." >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ ! -f portals/officer/dist/index.html ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "The frontend is not built and npm is unavailable." >&2
    exit 1
  fi
  npm --prefix portals/officer run build
fi

echo "Alcohol Label Validator: http://$HOST:$PORT/ (PaddleOCR enabled)"
exec "$PYTHON" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
