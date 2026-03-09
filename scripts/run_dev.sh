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

ENV_FILE="${EYEGATE_ENV_FILE:-$ROOT/.env}"
if [[ "$ENV_FILE" != /* ]]; then
  ENV_FILE="$ROOT/$ENV_FILE"
fi
if [[ -f "$ENV_FILE" ]]; then
  echo "[dev] using env file: $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "[dev] .env not found, expected at $ENV_FILE"
fi
export ENV_FILE

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
export WINDOWS_HOST

if [[ -z "${CAMERA_RTSP_URL:-}" ]]; then
  CAMERA_RTSP_URL="rtsp://${WINDOWS_HOST}:8554/live/0"
elif [[ "$CAMERA_RTSP_URL" == *"<WINDOWS_HOST>"* ]]; then
  CAMERA_RTSP_URL="${CAMERA_RTSP_URL//<WINDOWS_HOST>/$WINDOWS_HOST}"
fi

if [[ "${RTSP_TESTSRC:-0}" == "1" ]]; then
  "$ROOT/scripts/rtsp_testsrc.sh" start
  CAMERA_RTSP_URL="rtsp://127.0.0.1:8554/live/0"
fi

rewrite_rtsp_host() {
  local src="$1"
  local win_host="$2"
  local rest hostport path portpart
  if [[ "$src" != rtsp://* ]]; then
    echo "$src"
    return
  fi
  rest="${src#rtsp://}"
  hostport="${rest%%/*}"
  path="${rest#"$hostport"}"
  case "$hostport" in
    127.0.0.1|127.0.0.1:*)
      portpart="${hostport#127.0.0.1}"
      echo "rtsp://${win_host}${portpart}${path}"
      return
      ;;
    localhost|localhost:*)
      portpart="${hostport#localhost}"
      echo "rtsp://${win_host}${portpart}${path}"
      return
      ;;
    0.0.0.0|0.0.0.0:*)
      portpart="${hostport#0.0.0.0}"
      echo "rtsp://${win_host}${portpart}${path}"
      return
      ;;
    "[::1]"|"[::1]":*)
      portpart="${hostport#"[::1]"}"
      echo "rtsp://${win_host}${portpart}${path}"
      return
      ;;
  esac
  echo "$src"
}

if [[ "${RTSP_TESTSRC:-0}" != "1" && "$WINDOWS_HOST" != "127.0.0.1" ]]; then
  rewritten="$(rewrite_rtsp_host "$CAMERA_RTSP_URL" "$WINDOWS_HOST")"
  if [[ "$rewritten" != "$CAMERA_RTSP_URL" ]]; then
    echo "[dev] Rewrote CAMERA_RTSP_URL for WSL: $CAMERA_RTSP_URL -> $rewritten"
    CAMERA_RTSP_URL="$rewritten"
  fi
fi
if [[ -z "${VISION_CAMERA_SOURCE:-}" ]]; then
  VISION_CAMERA_SOURCE="$CAMERA_RTSP_URL"
fi
export CAMERA_RTSP_URL
export VISION_CAMERA_SOURCE

if [[ "$CAMERA_RTSP_URL" == "rtsp://127.0.0.1:8554/live/0" && "$WINDOWS_HOST" != "127.0.0.1" ]]; then
  echo "[dev] WARNING: CAMERA_RTSP_URL points to 127.0.0.1; expected $WINDOWS_HOST in WSL."
fi

echo "[dev] Windows host resolved to $WINDOWS_HOST; RTSP=$CAMERA_RTSP_URL; SSH forward=ssh -p 2222 root@$WINDOWS_HOST"

"$ROOT/scripts/run_backend.sh"
"$ROOT/scripts/run_frontend.sh"

HOST_VAL="${EYEGATE_HOST:-${HOST:-0.0.0.0}}"
PORT_VAL="${EYEGATE_PORT:-${PORT:-8000}}"
FRONT_PORT="${VITE_PORT:-5173}"

echo "[dev] backend: http://127.0.0.1:${PORT_VAL}"
echo "[dev] frontend: http://127.0.0.1:${FRONT_PORT}"
echo "[dev] pages: /monitor /kiosk /sim /admin /enroll"
echo "[dev] logs: $LOG_DIR/backend.log $LOG_DIR/frontend.log"
echo "[dev] stop: ./scripts/stop_dev.sh"

cleanup() {
  "$ROOT/scripts/stop_dev.sh" || true
}
trap cleanup INT TERM EXIT

LOGS=()
[[ -f "$LOG_DIR/backend.log" ]] && LOGS+=("$LOG_DIR/backend.log")
[[ -f "$LOG_DIR/frontend.log" ]] && LOGS+=("$LOG_DIR/frontend.log")
if [[ ${#LOGS[@]} -gt 0 ]]; then
  tail -n 50 -f "${LOGS[@]}"
else
  wait
fi
