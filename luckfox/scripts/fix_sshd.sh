#!/bin/sh
set -e

CONF="/etc/ssh/sshd_config"
BACKUP="/etc/ssh/sshd_config.bak.$(date +%s)"

if [ ! -f "$CONF" ]; then
  echo "sshd_config not found: $CONF"
  exit 1
fi

cp "$CONF" "$BACKUP"
sed -i '/^UsePAM/d' "$CONF"

echo "Backup: $BACKUP"
/etc/init.d/S50sshd restart
/etc/init.d/S50sshd status || true
