#!/usr/bin/env bash
# 验收：断网、无 GPU 的 CPU 容器内执行已选定的 CPU 测试集合。
# 不运行 tests/ 全量（多数用例依赖 GPU / Ray / 分布式环境，见 env-manifest.json limitations）。
set -euo pipefail
docker run --rm --network "${NETWORK:-none}" \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \
  --memory 8g --cpus 4 --workdir /opt/target \
  --entrypoint /bin/bash "mygoldmine/env:verl-174888f" -lc \
  'python3 -m pytest -q tests/test_protocol_on_cpu.py tests/test_base_config_on_cpu.py tests/test_protocol_v2_on_cpu.py'
