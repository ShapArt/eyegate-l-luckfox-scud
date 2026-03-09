#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
RUN_DIR="$ROOT/.run"
mkdir -p "$LOG_DIR" "$RUN_DIR"

FFMPEG_BIN="${FFMPEG_PATH:-$ROOT/tools/ffmpeg/ffmpeg}"
MEDIAMTX_BIN="$ROOT/tools/mediamtx/mediamtx"
if [[ ! -x "$FFMPEG_BIN" ]]; then
  if command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_BIN="ffmpeg"
  else
    echo "[rtsp_testsrc] ffmpeg not found"
    exit 1
  fi
fi

PID_FILE="$RUN_DIR/rtsp_testsrc.pid"
MTX_PID_FILE="$RUN_DIR/mediamtx.pid"

start() {
  if [[ -x "$MEDIAMTX_BIN" ]]; then
    if [[ -f "$MTX_PID_FILE" ]]; then
      mtx_pid="$(cat "$MTX_PID_FILE")"
      if [[ -n "$mtx_pid" ]] && kill -0 "$mtx_pid" 2>/dev/null; then
        echo "[rtsp_testsrc] mediamtx already running (pid $mtx_pid)"
      else
        rm -f "$MTX_PID_FILE"
      fi
    fi
    if [[ ! -f "$MTX_PID_FILE" ]]; then
      MTX_CONFIG="$ROOT/tools/mediamtx/mediamtx.yml"
      echo "[rtsp_testsrc] starting mediamtx on :8554"
      nohup "$MEDIAMTX_BIN" "$MTX_CONFIG" > "$LOG_DIR/mediamtx.log" 2>&1 &
      echo $! > "$MTX_PID_FILE"
      for _ in {1..20}; do
        if ss -lnt 2>/dev/null | grep -q ':8554'; then
          break
        fi
        sleep 0.2
      done
    fi
  else
    echo "[rtsp_testsrc] mediamtx not found; RTSP server may be unavailable"
  fi

  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[rtsp_testsrc] already running (pid $pid)"
      return
    fi
  fi
  echo "[rtsp_testsrc] starting testsrc RTSP on rtsp://127.0.0.1:8554/live/0"
  nohup "$FFMPEG_BIN" -hide_banner -loglevel warning \
    -re -f lavfi -i testsrc=size=960x720:rate=25 \
    -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p \
    -g 50 -keyint_min 50 -sc_threshold 0 \
    -f rtsp -rtsp_transport tcp \
    rtsp://127.0.0.1:8554/live/0 > "$LOG_DIR/rtsp_testsrc.log" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 0.3
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[rtsp_testsrc] ffmpeg exited early; check $LOG_DIR/rtsp_testsrc.log"
  fi
}

stop() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "[rtsp_testsrc] not running"
    return
  fi
  pid="$(cat "$PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
  fi
  rm -f "$PID_FILE"
  echo "[rtsp_testsrc] stopped"

  if [[ -f "$MTX_PID_FILE" ]]; then
    mtx_pid="$(cat "$MTX_PID_FILE")"
    if [[ -n "$mtx_pid" ]] && kill -0 "$mtx_pid" 2>/dev/null; then
      kill "$mtx_pid" || true
    fi
    rm -f "$MTX_PID_FILE"
    echo "[rtsp_testsrc] mediamtx stopped"
  fi
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  *) echo "usage: $0 {start|stop}"; exit 2 ;;
esac
