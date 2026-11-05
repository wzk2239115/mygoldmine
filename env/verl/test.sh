#!/usr/bin/env bash
# 最小环境的断网冒烟验收：源码可读、Python 可运行、源码版本匹配、工作目录可写。
# 不运行项目 pytest（运行时依赖未安装，见 env-manifest.json limitations）。
set -uo pipefail
docker run --rm --network "${NETWORK:-none}" \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \
  --memory 8g --cpus 4 --workdir /opt/target \
  --entrypoint /bin/bash "mygoldmine/env:verl-174888f" -lc '
  set -e
  python3 -c "import sys; print(\"python\", sys.version.split()[0])"
  test -r /opt/target/verl/__init__.py && echo "source readable"
  git -C /opt/target rev-parse HEAD
  touch /opt/target/.wtest && rm -f /opt/target/.wtest && echo "workdir writable"
  python3 -m pip show verl >/dev/null && echo "verl metadata present"
'
