#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/sglang/Dockerfile" -t "mygoldmine/env:sglang-c04bae2b" "/home/wzk/mygoldmine/runs/watch/worktrees/sglang/c04bae2b3f5a"
