#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${EYEGATE_ENV_FILE:-$ROOT/.env}"
if [[ "$ENV_FILE" != /* ]]; then
  ENV_FILE="$ROOT/$ENV_FILE"
fi
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

RTSP_URL="${CAMERA_RTSP_URL:-${VISION_CAMERA_SOURCE:-rtsp://127.0.0.1:8554/live/0}}"
RTSP_TRANSPORT="${RTSP_TRANSPORT:-tcp}"
LOCAL_FFMPEG="$ROOT/tools/ffmpeg/ffmpeg"
LOCAL_FFPROBE="$ROOT/tools/ffmpeg/ffprobe"
FFMPEG_BIN="ffmpeg"
FFPROBE_BIN="ffprobe"
if [[ -x "$LOCAL_FFMPEG" ]]; then
  FFMPEG_BIN="$LOCAL_FFMPEG"
fi
if [[ -x "$LOCAL_FFPROBE" ]]; then
  FFPROBE_BIN="$LOCAL_FFPROBE"
fi

echo "[rtsp_diag] RTSP URL: $RTSP_URL"
echo "[rtsp_diag] RTSP transport: $RTSP_TRANSPORT"

probe_rtsp() {
  if command -v "$FFPROBE_BIN" >/dev/null 2>&1; then
    timeout 3 "$FFPROBE_BIN" -v error -rtsp_transport "$RTSP_TRANSPORT" \
      -select_streams v:0 -show_entries stream=codec_name,width,height \
      -of default=nw=1 "$RTSP_URL" >/dev/null
    return $?
  fi
  if command -v "$FFMPEG_BIN" >/dev/null 2>&1; then
    timeout 3 "$FFMPEG_BIN" -hide_banner -loglevel error -rtsp_transport "$RTSP_TRANSPORT" \
      -i "$RTSP_URL" -t 2 -f null - >/dev/null 2>&1
    return $?
  fi
  echo "[rtsp_diag] ffprobe/ffmpeg not found"
  return 2
}

if probe_rtsp; then
  echo "[rtsp_diag] RTSP probe: OK"
else
  echo "[rtsp_diag] RTSP probe: FAIL"
fi

echo "[rtsp_diag] listeners on 8554:"
if command -v ss >/dev/null 2>&1; then
  ss -lntp | awk 'NR==1 || /:8554/' || true
else
  echo "[rtsp_diag] ss not found"
fi

if [[ -f /.dockerenv ]]; then
  echo "[rtsp_diag] Docker detected"
  if command -v getent >/dev/null 2>&1; then
    host_ip="$(getent hosts host.docker.internal | awk '{print $1}' | head -n1 || true)"
    if [[ -n "$host_ip" ]]; then
      echo "[rtsp_diag] host.docker.internal -> $host_ip"
    else
      echo "[rtsp_diag] host.docker.internal not resolvable"
    fi
  fi
  if timeout 1 bash -c "cat < /dev/null > /dev/tcp/host.docker.internal/8554" 2>/dev/null; then
    echo "[rtsp_diag] host.docker.internal:8554 reachable"
  else
    echo "[rtsp_diag] host.docker.internal:8554 unreachable"
  fi
fi
