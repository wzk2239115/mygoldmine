#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/codex/Dockerfile" -t "mygoldmine/env:codex-970111f" "/home/wzk/mygoldmine/targets/codex"
