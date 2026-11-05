#!/usr/bin/env bash
# 构建并验收审计运行镜像。只有冒烟通过后才更新正式标签。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE="${RUNNER_IMAGE:-mygoldmine:dev}"
DOCKERFILE="$ROOT/docker/Dockerfile"
CONTEXT="$ROOT"
OUTPUT=""
SMOKE=1
NO_CACHE=0
DRY_RUN=0
SKIP_VALIDATION=0
BUILD_NETWORK="${RUNNER_BUILD_NETWORK:-}"
declare -a BUILD_ARGS=()

log() { printf '[runner] %s\n' "$*" >&2; }
die() { printf '[runner] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: build_runner.sh [选项]

选项:
  --image <镜像标签>      正式镜像标签（默认 mygoldmine:dev）
  --dockerfile <文件>     运行镜像 Dockerfile（默认 docker/Dockerfile）
  --context <目录>        构建上下文（默认仓库根目录）
  --output <文件>         将构建结果写入 JSON 文件
  --network <模式>        传给镜像构建的网络模式
  --build-arg <键=值>     追加镜像构建参数，可重复
  --no-smoke             构建后不运行镜像内冒烟检查
  --no-cache             不使用 Docker 构建缓存
  --skip-validation      跳过 runner 依赖清单校验
  --dry-run              只打印构建和冒烟命令，不执行
  -h, --help             显示本帮助

流程:
  1. 校验 runner/requirements.txt 只包含允许清单中的包；
  2. 用临时标签构建镜像；
  3. 在断网、无特权容器中运行 smoke_runner.py；
  4. 冒烟通过后才把临时标签更新为正式标签。
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --image) [ "$#" -ge 2 ] || die "--image 需要参数" 3; IMAGE="$2"; shift ;;
        --dockerfile) [ "$#" -ge 2 ] || die "--dockerfile 需要参数" 3; DOCKERFILE="$2"; shift ;;
        --context) [ "$#" -ge 2 ] || die "--context 需要参数" 3; CONTEXT="$2"; shift ;;
        --output) [ "$#" -ge 2 ] || die "--output 需要参数" 3; OUTPUT="$2"; shift ;;
        --network) [ "$#" -ge 2 ] || die "--network 需要参数" 3; BUILD_NETWORK="$2"; shift ;;
        --build-arg) [ "$#" -ge 2 ] || die "--build-arg 需要参数" 3; BUILD_ARGS+=("$2"); shift ;;
        --no-smoke) SMOKE=0 ;;
        --no-cache) NO_CACHE=1 ;;
        --skip-validation) SKIP_VALIDATION=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" 3 ;;
    esac
    shift
done

[ -n "$IMAGE" ] || die "镜像标签不能为空" 3
[ -f "$DOCKERFILE" ] || die "Dockerfile 不存在: $DOCKERFILE" 4
[ -d "$CONTEXT" ] || die "构建上下文不存在: $CONTEXT" 4
hash python3 2>/dev/null || die "缺少 python3" 4
if [ -n "$OUTPUT" ]; then OUTPUT="$(realpath -m "$OUTPUT")"; fi

if [ "$SKIP_VALIDATION" -eq 0 ]; then
    python3 "$ROOT/scripts/runner/validate_requirements.py" \
        --requirements "$ROOT/runner/requirements.txt" \
        --allowlist "$ROOT/runner/allowed-packages.txt" \
        || die "runner 依赖清单校验失败" 3
fi

CANDIDATE="${IMAGE}-candidate-$(date -u +%Y%m%dT%H%M%SZ)-$$"
BUILD_CMD=(docker build -f "$DOCKERFILE" -t "$CANDIDATE"
    --build-arg "UID=$(id -u)" --build-arg "GID=$(id -g)")
[ "$NO_CACHE" -eq 1 ] && BUILD_CMD+=(--no-cache)
[ -n "$BUILD_NETWORK" ] && BUILD_CMD+=(--network "$BUILD_NETWORK")
for item in "${BUILD_ARGS[@]}"; do BUILD_CMD+=(--build-arg "$item"); done
BUILD_CMD+=("$CONTEXT")

SMOKE_CMD=(docker run --rm --network none --cap-drop ALL
    --security-opt no-new-privileges
    --entrypoint python3 "$CANDIDATE"
    /opt/mygoldmine/scripts/runner/smoke_runner.py
    --json --command "claude --version")

write_result() {
    local status="$1" returncode="$2" smoke_json="${3:-}" error="${4:-}" image_id="${5:-}"
    python3 - "$OUTPUT" "$IMAGE" "$CANDIDATE" "$status" "$returncode" "$smoke_json" "$error" "$image_id" <<'PY'
import json
import sys
from pathlib import Path

output, image, candidate, status, returncode, smoke_json, error, image_id = sys.argv[1:9]
try:
    smoke = json.loads(smoke_json) if smoke_json else None
except ValueError:
    smoke = smoke_json
payload = {
    "schema_version": 1,
    "status": status,
    "image": image,
    "candidate": candidate,
    "returncode": int(returncode),
    "smoke": smoke,
    "error": error,
    "image_id": image_id,
}
if output:
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
PY
}

if [ "$DRY_RUN" -eq 1 ]; then
    printf '[runner] build: '
    printf '%q ' "${BUILD_CMD[@]}"
    printf '\n[runner] smoke: '
    printf '%q ' "${SMOKE_CMD[@]}"
    printf '\n'
    exit 0
fi

hash docker 2>/dev/null || die "缺少 docker" 4
log "构建候选镜像: $CANDIDATE"
if ! "${BUILD_CMD[@]}"; then
    write_result "build_failed" 1 "" "镜像构建失败"
    exit 1
fi

IMAGE_ID="$(docker image inspect "$CANDIDATE" --format '{{.Id}}')" \
    || die "无法读取候选镜像编号" 5
SMOKE_JSON=""
if [ "$SMOKE" -eq 1 ]; then
    log "运行镜像冒烟检查"
    set +e
    SMOKE_JSON="$( "${SMOKE_CMD[@]}" 2>&1 )"
    SMOKE_RC=$?
    set -e
    if [ "$SMOKE_RC" -ne 0 ]; then
        printf '%s\n' "$SMOKE_JSON" >&2
        write_result "smoke_failed" "$SMOKE_RC" "$SMOKE_JSON" "运行镜像冒烟检查失败"
        exit 2
    fi
fi

docker image tag "$CANDIDATE" "$IMAGE" || die "无法更新正式镜像标签: $IMAGE" 5
FINAL_ID="$(docker image inspect "$IMAGE" --format '{{.Id}}')" || FINAL_ID="$IMAGE_ID"
docker image rm "$CANDIDATE" >/dev/null 2>&1 || true
write_result "published" 0 "$SMOKE_JSON" "" "$FINAL_ID"
log "已发布镜像: $IMAGE ($FINAL_ID)"
