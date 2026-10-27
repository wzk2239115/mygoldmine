#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/vllm/Dockerfile" -t "mygoldmine/env:vllm-20bf65a" "/home/wzk/mygoldmine/targets/vllm"
