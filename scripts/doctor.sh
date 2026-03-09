#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[doctor] repo: $ROOT"

ENV_FILE="${EYEGATE_ENV_FILE:-$ROOT/.env}"
if [[ "$ENV_FILE" != /* ]]; then
  ENV_FILE="$ROOT/$ENV_FILE"
fi
if [[ -f "$ENV_FILE" ]]; then
  echo "[doctor] using env file: $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "[doctor] .env not found, expected at $ENV_FILE"
fi

detect_windows_host() {
  if grep -qi microsoft /proc/version 2>/dev/null; then
    local gw
    gw="$(ip route | awk '/^default/ {print $3; exit}')"
    if [[ -n "$gw" ]]; then
      echo "$gw"
      return
    fi
    local ns
    ns="$(awk '/^nameserver/ {print $2; exit}' /etc/resolv.conf 2>/dev/null || true)"
    if [[ -n "$ns" ]]; then
      echo "$ns"
      return
    fi
  fi
  echo "127.0.0.1"
}

WINDOWS_HOST="${WINDOWS_HOST:-$(detect_windows_host)}"
RTSP_URL="${CAMERA_RTSP_URL:-${VISION_CAMERA_SOURCE:-rtsp://${WINDOWS_HOST}:8554/live/0}}"
if [[ "$RTSP_URL" == *"<WINDOWS_HOST>"* ]]; then
  RTSP_URL="${RTSP_URL//<WINDOWS_HOST>/$WINDOWS_HOST}"
fi

echo "[doctor] Windows host: $WINDOWS_HOST"
echo "[doctor] RTSP URL: $RTSP_URL"
if [[ "$RTSP_URL" == "rtsp://127.0.0.1:8554/live/0" && "$WINDOWS_HOST" != "127.0.0.1" ]]; then
  echo "[doctor] WARNING: RTSP URL points to 127.0.0.1; expected $WINDOWS_HOST in WSL."
fi

check_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  if timeout 1 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null; then
    echo "[doctor] ${label} OK (${host}:${port})"
  else
    echo "[doctor] ${label} FAIL (${host}:${port})"
  fi
}

check_port "$WINDOWS_HOST" 8554 "RTSP port"
check_port "$WINDOWS_HOST" 2222 "SSH forward"

PY="$ROOT/.venv/bin/python"
if [[ -x "$PY" ]]; then
  echo "[doctor] python venv: OK ($PY)"
else
  echo "[doctor] python venv: missing ($PY)"
fi
command -v node >/dev/null 2>&1 && echo "[doctor] node: OK" || echo "[doctor] node: missing"
command -v npm >/dev/null 2>&1 && echo "[doctor] npm: OK" || echo "[doctor] npm: missing"

echo "[doctor] ports in use:"
if command -v ss >/dev/null 2>&1; then
  ss -lnt | awk 'NR==1 || /:8000|:5173/' || true
else
  echo "[doctor] ss not found"
fi

if command -v ssh >/dev/null 2>&1; then
  if remote_ts=$(ssh -p 2222 -o BatchMode=yes -o ConnectTimeout=2 "root@${WINDOWS_HOST}" "date +%s" 2>/dev/null); then
    local_ts=$(date +%s)
    delta=$(( local_ts - remote_ts ))
    if [[ "$delta" -gt 2592000 ]]; then
      echo "[doctor] WARNING: Luckfox time is far behind (delta ${delta}s)."
    else
      echo "[doctor] Luckfox time OK (delta ${delta}s)."
    fi
  else
    echo "[doctor] could not read Luckfox time (ssh auth or connection failed)"
  fi
else
  echo "[doctor] ssh not available for time check"
fi
