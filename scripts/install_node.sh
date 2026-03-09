#!/usr/bin/env bash
set -euo pipefail

NODE_VER=${NODE_VER:-20.11.1}
PREFIX="${HOME}/.local/node-${NODE_VER}"

if [[ ! -x "${PREFIX}/bin/node" ]]; then
  mkdir -p "${PREFIX}"
  cd "${PREFIX}"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VER}/node-v${NODE_VER}-linux-x64.tar.xz" -o node.tar.xz
  tar -xJf node.tar.xz --strip-components=1
  rm node.tar.xz
fi

exec "${PREFIX}/bin/node" "$@"
