#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
[ "${NETWORK:-default}" != "default" ] && NET_ARG=(--network "${NETWORK:-default}")
docker build "${NET_ARG[@]}" \
  -f "/home/wzk/mygoldmine/env/verl/Dockerfile" \
  -t "mygoldmine/env:verl-174888f" \
  "/home/wzk/mygoldmine/targets/verl"
