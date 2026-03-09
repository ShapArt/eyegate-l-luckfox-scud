#!/usr/bin/env bash
set -euo pipefail

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

NOW="$(date "+%Y-%m-%d %H:%M:%S")"
echo "Setting Luckfox time to: $NOW"
ssh -p "$PORT" "root@${HOST}" "date -s \"$NOW\""
