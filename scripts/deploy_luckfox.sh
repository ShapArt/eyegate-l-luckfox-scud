#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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

HOST="${LUCKFOX_HOST:-${WINDOWS_HOST:-$(detect_windows_host)}}"
PORT="${LUCKFOX_SSH_PORT:-2222}"
DEST="/tmp/eyegate-luckfox"

FIX_SSHD=0
INSTALL_RTSP=0

for arg in "$@"; do
  case "$arg" in
    --fix-sshd) FIX_SSHD=1 ;;
    --install-rtsp) INSTALL_RTSP=1 ;;
    --all) FIX_SSHD=1; INSTALL_RTSP=1 ;;
  esac
done

echo "[deploy] target: root@${HOST}:${PORT}"
ssh -p "$PORT" "root@${HOST}" "mkdir -p $DEST/init.d $DEST/scripts"

scp -P "$PORT" luckfox/init.d/S99rtsp "root@${HOST}:${DEST}/init.d/"
scp -P "$PORT" luckfox/scripts/*.sh "root@${HOST}:${DEST}/scripts/"

if [[ "$FIX_SSHD" -eq 1 ]]; then
  ssh -p "$PORT" "root@${HOST}" "$DEST/scripts/fix_sshd.sh"
fi
if [[ "$INSTALL_RTSP" -eq 1 ]]; then
  ssh -p "$PORT" "root@${HOST}" "$DEST/scripts/install_rtsp_autostart.sh"
fi

echo "[deploy] done"
