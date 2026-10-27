#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/smoke-target/Dockerfile" -t "mygoldmine/env:smoke-target-7b1666b" "/home/wzk/mygoldmine/tests/fixtures/smoke-target"
