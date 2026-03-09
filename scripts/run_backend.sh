#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
RUN_DIR="$ROOT/.run"
mkdir -p "$LOG_DIR" "$RUN_DIR"

ENV_FILE="${ENV_FILE:-${EYEGATE_ENV_FILE:-$ROOT/.env}}"
if [[ "$ENV_FILE" != /* ]]; then
  ENV_FILE="$ROOT/$ENV_FILE"
fi
if [[ -f "$ENV_FILE" ]]; then
  echo "[backend] using env file: $ENV_FILE"
else
  echo "[backend] .env not found, expected at $ENV_FILE"
  ENV_FILE=""
fi

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" && -x "/home/shapart/eyegate/.venv/bin/python" ]]; then
  PY="/home/shapart/eyegate/.venv/bin/python"
fi
if [[ ! -x "$PY" ]]; then
  echo "[backend] ERROR: venv python not found (.venv/bin/python)"
  exit 1
fi
export PATH="$(dirname "$PY"):$PATH"

PID_FILE="$RUN_DIR/backend.pid"
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "[backend] already running (pid $PID)"
    exit 0
  fi
fi

HOST_VAL="${EYEGATE_HOST:-${HOST:-0.0.0.0}}"
PORT_VAL="${EYEGATE_PORT:-${PORT:-8000}}"

CMD=("$PY" -m uvicorn server.main:app --reload --host "$HOST_VAL" --port "$PORT_VAL")
if [[ -n "$ENV_FILE" ]]; then
  CMD+=("--env-file" "$ENV_FILE")
fi

echo "[backend] ${CMD[*]}"
nohup "${CMD[@]}" > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$PID_FILE"
echo "[backend] pid $(cat "$PID_FILE")"
