#!/usr/bin/env bash
set -euo pipefail
docker run --rm -it --network "${NETWORK:-none}" \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \
  --memory 8g --cpus 4 \
  --mount type=bind,src="/home/wzk/mygoldmine/runs/watch/worktrees/sglang/c04bae2b3f5a",dst=/source-ro,readonly \
  --entrypoint /bin/bash "mygoldmine/env:sglang-c04bae2b" "$@"
