#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/sglang/Dockerfile" -t "mygoldmine/env:sglang-3a62cdf" "/home/wzk/mygoldmine/targets/sglang"
