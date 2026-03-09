#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
RUN_DIR="$ROOT/.run"
mkdir -p "$LOG_DIR" "$RUN_DIR"

if [[ "${HOME:-}" != /* ]]; then
  HOME="$(getent passwd "$USER" | cut -d: -f6)"
  export HOME
fi

NODE_VER="${NODE_VER:-20.11.1}"
LOCAL_NODE_BIN="${HOME}/.local/node-${NODE_VER}/bin"
if [[ -x "${LOCAL_NODE_BIN}/node" ]]; then
  export PATH="${LOCAL_NODE_BIN}:$PATH"
fi

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -v | tr -d 'v' | cut -d. -f1 || echo 0)"
  if [[ "$NODE_MAJOR" -lt 18 && -x "${LOCAL_NODE_BIN}/node" ]]; then
    export PATH="${LOCAL_NODE_BIN}:$PATH"
  fi
fi

FRONTEND_DIR="$ROOT/web/app"
if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "[frontend] web/app not found; skipping"
  exit 0
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "[frontend] npm not found; run ./scripts/install_node.sh in WSL"
  exit 0
fi

PID_FILE="$RUN_DIR/frontend.pid"
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "[frontend] already running (pid $PID)"
    exit 0
  fi
fi

PORT_VAL="${VITE_PORT:-5173}"

cd "$FRONTEND_DIR"
if [[ ! -d node_modules ]]; then
  npm install
fi

echo "[frontend] npm run dev -- --host 0.0.0.0 --port $PORT_VAL"
nohup npm run dev -- --host 0.0.0.0 --port "$PORT_VAL" > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$PID_FILE"
echo "[frontend] pid $(cat "$PID_FILE")"
