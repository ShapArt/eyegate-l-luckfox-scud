#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../init.d/S99rtsp"
TARGET="/etc/init.d/S99rtsp"

if [ ! -f "$TEMPLATE" ]; then
  echo "Template not found: $TEMPLATE"
  exit 1
fi

BIN="$(find / -type f -name simple_vi_bind_venc_rtsp 2>/dev/null | head -n 1)"
if [ -z "$BIN" ]; then
  echo "simple_vi_bind_venc_rtsp not found"
  exit 1
fi

sed "s|__RTSP_BIN__|$BIN|g" "$TEMPLATE" > "$TARGET"
chmod +x "$TARGET"

echo "Installed $TARGET -> $BIN"
if [ -x "$TARGET" ]; then
  "$TARGET" restart || true
fi
