#!/usr/bin/env bash
set -euo pipefail
docker run --rm --network "${NETWORK:-none}" \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \
  --memory 8g --cpus 4 --workdir /opt/target \
  --entrypoint /bin/bash "mygoldmine/env:verl-test" -lc python3\ -m\ pytest\ -q
