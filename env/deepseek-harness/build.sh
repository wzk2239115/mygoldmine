#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/deepseek-harness/Dockerfile" -t "mygoldmine/env:deepseek-harness-22ddee37" "/home/wzk/mygoldmine/targets/deepseek-harness"
