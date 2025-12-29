#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VENV_DIR="$DIR/.venv"

if [ -d "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python" ]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
else
  PY=$(command -v python3 || true)
  if [ -z "${PY:-}" ]; then
    PY=$(command -v python || true)
  fi
  if [ -z "${PY:-}" ]; then
    echo "Python not found" >&2
    exit 1
  fi
  "$PY" -m venv "$VENV_DIR"
  PYTHON_BIN="$VENV_DIR/bin/python"
  "$VENV_DIR/bin/pip" install -r requirements.txt
fi

if ! "$VENV_DIR/bin/python" -c "import httpx, pydantic" >/dev/null 2>&1; then
  "$VENV_DIR/bin/pip" install -r requirements.txt
fi

if [ -f ".env" ]; then
  set -a
  . ".env"
  set +a
fi

export PYTHONUNBUFFERED=1
exec "$VENV_DIR/bin/python" monitor.py
