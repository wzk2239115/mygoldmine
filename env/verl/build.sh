#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "default" != "default" ] && NET_ARG=(--network "default")
    docker build "" -f "/home/wzk/mygoldmine/env/verl/Dockerfile" -t "mygoldmine/env:verl-test" "/home/wzk/mygoldmine/targets/verl"
