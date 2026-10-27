#!/usr/bin/env bash
# Phase 0: 为源码构建可复现的 Docker 环境镜像。
#
# 产物（默认 env/<project>/）：
#   Dockerfile / build.sh / run.sh / test.sh / env-manifest.json / build.log
# 镜像（默认 mygoldmine/env:<project>-<commit>）：
#   FROM mygoldmine:dev（含 Claude Code + mygoldmine skills/scripts）
#   + 目标源码（烘焙到 /opt/target）
#   + 语言运行时/依赖（按 --mode）
#
# 设计：分层检测，失败降级为 partial/blocked，不假装 ready。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[build_env] %s\n' "$*" >&2; }
die() { printf '[build_env] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: build_env.sh <源码路径> [选项]

选项:
  --project NAME       项目名（默认 basename）
  --image IMAGE        镜像名（默认 mygoldmine/env:<project>-<commit>）
  --base-image IMAGE   基础镜像（默认 mygoldmine:dev）
  --env-dir DIR        产物目录（默认 <repo>/env/<project>）
  --mode MODE          none|editable|requirements|full|auto（默认 auto）
  --network MODE       docker build 网络：default|host|none（默认 default，不传 buildkit 网络参数）
  --timeout SECONDS    构建超时（默认 3600）
  --dry-run            只检测与生成文件，不构建
  --no-build           生成文件但不构建
  --no-generate        复用已存在的 Dockerfile，只构建
  --force              覆盖已存在的生成文件
  -h, --help           显示帮助

mode 语义:
  none          不装依赖，只把源码放进镜像
  editable      Python 可编辑安装 --no-deps；Node 装依赖但 --ignore-scripts；
                Rust/Go 只 fetch/download；Java 只拉依赖
  requirements  Python 按 requirements.txt 安装
  full          完整安装/编译（可能很慢，vLLM/SGLang/verl 慎用）

退出码: 0 ready；10 partial；20 blocked；3 参数错误
EOF
}

SOURCE=""
PROJECT=""
IMAGE=""
BASE_IMAGE="${BASE_IMAGE:-mygoldmine:dev}"
ENV_DIR=""
MODE="auto"
NETWORK="default"
BUILD_TIMEOUT="${BUILD_TIMEOUT:-3600}"
DRY_RUN=0
NO_BUILD=0
NO_GENERATE=0
FORCE=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数" 3; PROJECT="$2"; shift ;;
        --image) [ "$#" -ge 2 ] || die "--image 需要参数" 3; IMAGE="$2"; shift ;;
        --base-image) [ "$#" -ge 2 ] || die "--base-image 需要参数" 3; BASE_IMAGE="$2"; shift ;;
        --env-dir) [ "$#" -ge 2 ] || die "--env-dir 需要参数" 3; ENV_DIR="$2"; shift ;;
        --mode) [ "$#" -ge 2 ] || die "--mode 需要参数" 3; MODE="$2"; shift ;;
        --network) [ "$#" -ge 2 ] || die "--network 需要参数" 3; NETWORK="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; BUILD_TIMEOUT="$2"; shift ;;
        --dry-run) DRY_RUN=1 ;;
        --no-build) NO_BUILD=1 ;;
        --no-generate) NO_GENERATE=1 ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        --) shift; [ "$#" -ge 1 ] || die "缺少源码路径" 3; SOURCE="$1"; shift; break ;;
        -*) usage >&2; die "未知参数: $1" 3 ;;
        *) [ -z "$SOURCE" ] || die "只能指定一个源码路径" 3; SOURCE="$1" ;;
    esac
    shift
done

[ -n "$SOURCE" ] || { usage >&2; die "缺少源码路径" 3; }
SOURCE="$(realpath -e "$SOURCE" 2>/dev/null)" || die "源码路径不存在" 3
[ -d "$SOURCE" ] || die "不是目录: $SOURCE" 3
case "$MODE" in none|editable|requirements|full|auto) ;; *) die "mode 非法: $MODE" 3 ;; esac
case "$NETWORK" in default|host|none) ;; *) die "network 非法: $NETWORK" 3 ;; esac
[[ "$BUILD_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "timeout 必须是正整数" 3

if [ -z "$PROJECT" ]; then
    PROJECT="$(basename "${SOURCE%/}")"
fi
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"
COMMIT="$(git -C "$SOURCE" rev-parse --short HEAD 2>/dev/null || echo nogit)"
[ -z "$ENV_DIR" ] && ENV_DIR="$REPO_ROOT/env/$PROJECT"
[ -z "$IMAGE" ] && IMAGE="mygoldmine/env:${PROJECT}-${COMMIT}"
ENV_DIR="$(realpath -m "$ENV_DIR")"
mkdir -p "$ENV_DIR"
BUILD_LOG="$ENV_DIR/build.log"

_find_manifest() {
    local name="$1" filtered="$2"
    local -a prune=()
    if [ "$filtered" = "1" ]; then
        prune=(
            -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*'
            -not -path '*/vendor/*' -not -path '*/third_party/*' -not -path '*/3rdparty/*'
            -not -path '*/examples/*' -not -path '*/example/*' -not -path '*/tests/*'
            -not -path '*/test/*' -not -path '*/e2e_test/*' -not -path '*/benchmarks/*'
            -not -path '*/benchmark/*' -not -path '*/docs/*' -not -path '*/sdk/*'
            -not -path '*/sdk-*/*' -not -path '*/scripts/*' -not -path '*/tools/*'
            -not -path '*/dev/*' -not -path '*/ci/*' -not -path '*/.github/*'
            -not -path '*/.gitlab/*' -not -path '*/.devcontainer/*'
        )
    else
        prune=(-not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*')
    fi
    find "$SOURCE" -maxdepth 3 -type f -name "$name" "${prune[@]}" -printf '%d %p\n' 2>/dev/null \
        | sort -n -k1,1 | head -1 | cut -d' ' -f2-
}

manifest_path() {
    local name="$1" out
    out="$(_find_manifest "$name" 1)"
    [ -n "$out" ] && printf '%s\n' "$out"
}

rel_dir() {
    local d="$1"
    if [ "$d" = "$SOURCE" ]; then printf '.\n'; else printf '%s\n' "${d#"$SOURCE"/}"; fi
}

first_manifest() {
    local name p best="" best_depth=999
    local i=0
    for name in "$@"; do
        p="$(manifest_path "$name")"
        if [ -n "$p" ]; then
            local depth
            depth=$(printf '%s' "${p#"$SOURCE"/}" | awk -F/ '{print NF}')
            if [ "$depth" -lt "$best_depth" ]; then
                best="$p"; best_depth="$depth"
            fi
        fi
        i=$((i+1))
    done
    [ -n "$best" ] && printf '%s\n' "$best"
}

PY_MANIFEST="$(first_manifest pyproject.toml requirements.txt setup.py setup.cfg || true)"
NODE_MANIFEST="$(manifest_path package.json)"
RUST_MANIFEST="$(manifest_path Cargo.toml)"
GO_MANIFEST="$(manifest_path go.mod)"
JAVA_MANIFEST="$(first_manifest pom.xml build.gradle build.gradle.kts || true)"
CMAKE_MANIFEST="$(manifest_path CMakeLists.txt)"
PY_REQ="$(manifest_path requirements.txt)"

if [ -n "$PY_MANIFEST" ]; then PY_DIR="$(dirname "$PY_MANIFEST")"; PY_REL="$(rel_dir "$PY_DIR")"; fi
if [ -n "$PY_REQ" ]; then PY_REQ_DIR="$(dirname "$PY_REQ")"; PY_REQ_REL="$(rel_dir "$PY_REQ_DIR")"; fi
if [ -n "$NODE_MANIFEST" ]; then NODE_DIR="$(dirname "$NODE_MANIFEST")"; NODE_REL="$(rel_dir "$NODE_DIR")"; fi
if [ -n "$RUST_MANIFEST" ]; then RUST_DIR="$(dirname "$RUST_MANIFEST")"; RUST_REL="$(rel_dir "$RUST_DIR")"; fi
if [ -n "$GO_MANIFEST" ]; then GO_DIR="$(dirname "$GO_MANIFEST")"; GO_REL="$(rel_dir "$GO_DIR")"; fi
if [ -n "$JAVA_MANIFEST" ]; then JAVA_DIR="$(dirname "$JAVA_MANIFEST")"; JAVA_REL="$(rel_dir "$JAVA_DIR")"; fi
if [ -n "$CMAKE_MANIFEST" ]; then CMAKE_DIR="$(dirname "$CMAKE_MANIFEST")"; CMAKE_REL="$(rel_dir "$CMAKE_DIR")"; fi

detect_langs() {
    local langs=()
    [ -n "$PY_MANIFEST" ] && langs+=(python)
    [ -n "$NODE_MANIFEST" ] && langs+=(node)
    [ -n "$RUST_MANIFEST" ] && langs+=(rust)
    [ -n "$GO_MANIFEST" ] && langs+=(go)
    [ -n "$JAVA_MANIFEST" ] && langs+=(java)
    [ -n "$CMAKE_MANIFEST" ] && langs+=(native)
    if [ "${#langs[@]}" -gt 0 ]; then
        printf '%s\n' "${langs[@]}"
    fi
}

mapfile -t LANGS < <(detect_langs)
[ "${#LANGS[@]}" -gt 0 ] || LANGS=(generic)

has_lang() { [ "${#LANGS[@]}" -gt 0 ] && printf '%s\n' "${LANGS[@]}" | grep -qx "$1"; }

SYS_PKGS=()
TOOLCHAIN_CMDS=()
INSTALL_CMDS=()
INSTALL_LANGS=()
LIMITATIONS=()
PARTIAL_REASONS=()

add_sys() { for p in "$@"; do [[ " ${SYS_PKGS[*]} " == *" $p "* ]] || SYS_PKGS+=("$p"); done; }
add_install() { INSTALL_LANGS+=("$1"); INSTALL_CMDS+=("$2"); }
add_limit() { LIMITATIONS+=("$1"); }
add_partial() { PARTIAL_REASONS+=("$1"); }

py_prefix() { if [ -n "${PY_REL:-}" ] && [ "$PY_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$PY_REL"; fi; }
req_prefix() { if [ -n "${PY_REQ_REL:-}" ] && [ "$PY_REQ_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$PY_REQ_REL"; fi; }
node_prefix() { if [ -n "${NODE_REL:-}" ] && [ "$NODE_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$NODE_REL"; fi; }
rust_prefix() { if [ -n "${RUST_REL:-}" ] && [ "$RUST_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$RUST_REL"; fi; }
go_prefix() { if [ -n "${GO_REL:-}" ] && [ "$GO_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$GO_REL"; fi; }
java_prefix() { if [ -n "${JAVA_REL:-}" ] && [ "$JAVA_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$JAVA_REL"; fi; }
cmake_prefix() { if [ -n "${CMAKE_REL:-}" ] && [ "$CMAKE_REL" != "." ]; then printf "cd '/opt/target/%s' && " "$CMAKE_REL"; fi; }

if has_lang python; then
    local_py="$(py_prefix)"
    case "$MODE" in
        none) ;;
        requirements)
            if [ -n "$PY_REQ" ]; then
                local_req="$(req_prefix)"
                add_install python "${local_req}python3 -m pip install --no-cache-dir -r requirements.txt"
            else
                add_install python "${local_py}python3 -m pip install --no-cache-dir -e ."
            fi ;;
        full)
            if [ -f "$PY_DIR/pyproject.toml" ] || [ -f "$PY_DIR/setup.py" ]; then
                add_install python "${local_py}python3 -m pip install --no-cache-dir -e ."
            elif [ -n "$PY_REQ" ]; then
                local_req="$(req_prefix)"
                add_install python "${local_req}python3 -m pip install --no-cache-dir -r requirements.txt"
            fi ;;
        editable|auto)
            if [ -f "$PY_DIR/pyproject.toml" ] || [ -f "$PY_DIR/setup.py" ]; then
                add_install python "${local_py}python3 -m pip install --no-cache-dir -e . --no-deps"
                add_partial "Python 只做 editable --no-deps，运行时依赖未完整安装"
            elif [ -n "$PY_REQ" ]; then
                local_req="$(req_prefix)"
                add_install python "${local_req}python3 -m pip install --no-cache-dir --no-deps -r requirements.txt"
                add_partial "Python requirements 以 --no-deps 安装"
            fi ;;
    esac
fi

if has_lang node; then
    local_node="$(node_prefix)"
    case "$MODE" in
        none) ;;
        full)
            if [ -f "$NODE_DIR/pnpm-lock.yaml" ]; then
                add_install node "${local_node}npm install -g pnpm && pnpm install --frozen-lockfile"
            elif [ -f "$NODE_DIR/yarn.lock" ]; then
                add_install node "${local_node}npm install -g yarn && yarn install --frozen-lockfile"
            elif [ -f "$NODE_DIR/package-lock.json" ]; then
                add_install node "${local_node}npm ci"
            else
                add_install node "${local_node}npm install"
            fi ;;
        editable|auto|requirements)
            if [ -f "$NODE_DIR/pnpm-lock.yaml" ]; then
                add_install node "${local_node}npm install -g pnpm && pnpm install --frozen-lockfile --ignore-scripts"
            elif [ -f "$NODE_DIR/yarn.lock" ]; then
                add_install node "${local_node}npm install -g yarn && yarn install --frozen-lockfile --ignore-scripts"
            elif [ -f "$NODE_DIR/package-lock.json" ]; then
                add_install node "${local_node}npm ci --ignore-scripts"
            else
                add_install node "${local_node}npm install --ignore-scripts"
            fi
            add_partial "Node 安装跳过 lifecycle scripts（--ignore-scripts）" ;;
    esac
fi

if has_lang rust; then
    local_rust="$(rust_prefix)"
    add_sys curl ca-certificates build-essential pkg-config
    TOOLCHAIN_CMDS+=("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal")
    case "$MODE" in
        none) ;;
        full) add_install rust "${local_rust}(cargo build --locked || cargo build)" ;;
        *) add_install rust "${local_rust}(cargo fetch --locked || cargo fetch)"
           add_partial "Rust 只 fetch 依赖，未完整编译" ;;
    esac
fi

if has_lang go; then
    local_go="$(go_prefix)"
    add_sys golang-go
    case "$MODE" in
        none) ;;
        full) add_install go "${local_go}go build ./..." ;;
        *) add_install go "${local_go}go mod download"; add_partial "Go 只下载依赖，未完整编译" ;;
    esac
fi

if has_lang java; then
    local_java="$(java_prefix)"
    add_sys default-jdk
    if [ -f "$JAVA_DIR/pom.xml" ]; then
        add_sys maven
        case "$MODE" in
            none) ;;
            full) add_install java "${local_java}mvn -q -DskipTests package" ;;
            *) add_install java "${local_java}mvn -q -DskipTests dependency:go-offline"; add_partial "Java 只拉依赖，未打包" ;;
        esac
    fi
fi

if has_lang native; then
    local_cmake="$(cmake_prefix)"
    add_sys build-essential cmake
    case "$MODE" in
        none) ;;
        full) add_install native "${local_cmake}cmake -S . -B build && cmake --build build -j2" ;;
        *) add_partial "native 项目只准备工具链，未编译" ;;
    esac
fi

add_limit "默认不启用 GPU；GPU/CUDA 路径无法验证（需要 --gpus all 的专用环境）"
add_limit "未提供外部依赖服务（数据库、Ray 集群、对象存储等）"
[ "$MODE" = "auto" ] && add_limit "auto 模式为静态/导入级环境，不代表可完整启动服务"

gen_dockerfile() {
    local df="$ENV_DIR/Dockerfile"
    {
        echo "# generated by scripts/env/build_env.sh"
        echo "# project=$PROJECT commit=$COMMIT source=$SOURCE"
        echo "FROM $BASE_IMAGE"
        echo "USER root"
        echo "ENV DEBIAN_FRONTEND=noninteractive"
        if has_lang rust; then
            echo "ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo"
        fi
        if [ "${#SYS_PKGS[@]}" -gt 0 ]; then
            echo "RUN apt-get update \\"
            echo " && apt-get install -y --no-install-recommends ${SYS_PKGS[*]} \\"
            echo " && rm -rf /var/lib/apt/lists/*"
        fi
        for tc in "${TOOLCHAIN_CMDS[@]}"; do
            echo "RUN $tc"
        done
        if has_lang rust; then
            echo "ENV PATH=/opt/cargo/bin:\$PATH"
        fi
        echo "COPY --chown=miner:miner . /opt/target"
        echo "WORKDIR /opt/target"
        if [ "${#INSTALL_CMDS[@]}" -gt 0 ]; then
            local first=1
            printf 'RUN '
            for cmd in "${INSTALL_CMDS[@]}"; do
                [ "$first" -eq 1 ] || printf ' && \\\n    '
                printf '%s' "$cmd"
                first=0
            done
            echo
        fi
        echo "RUN chown -R miner:miner /opt/target /opt/cargo /opt/rustup 2>/dev/null || chown -R miner:miner /opt/target"
        echo "USER miner"
        echo "ENV MYGOLDMINE_PROJECT=$PROJECT \\"
        echo "    MYGOLDMINE_COMMIT=$COMMIT \\"
        echo "    MYGOLDMINE_TARGET=/opt/target \\"
        echo "    MYGOLDMINE_MODE=$MODE"
        echo "LABEL mygoldmine.project=$PROJECT \\"
        echo "      mygoldmine.commit=$COMMIT \\"
        echo "      mygoldmine.mode=$MODE \\"
        echo "      mygoldmine.source=$SOURCE"
        echo "WORKDIR /opt/target"
    } > "$df"
}

gen_helpers() {
    cat > "$ENV_DIR/build.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
NET_ARG=()
    [ "${NETWORK}" != "default" ] && NET_ARG=(--network "$NETWORK")
    docker build "${NET_ARG[@]}" -f "$ENV_DIR/Dockerfile" -t "$IMAGE" "$SOURCE"
EOF
    cat > "$ENV_DIR/run.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
docker run --rm -it --network "\${NETWORK:-none}" \\
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \\
  --memory 8g --cpus 4 \\
  --mount type=bind,src="$SOURCE",dst=/source-ro,readonly \\
  --entrypoint /bin/bash "$IMAGE" "\$@"
EOF
    local test_cmd=""
    has_lang python && test_cmd="python3 -m pytest -q"
    has_lang node && test_cmd="npm test -- --runInBand"
    has_lang rust && test_cmd="cargo test --locked"
    has_lang go && test_cmd="go test ./..."
    [ -n "$test_cmd" ] || test_cmd="echo 'no test command detected'"
    cat > "$ENV_DIR/test.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
docker run --rm --network "\${NETWORK:-none}" \\
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \\
  --memory 8g --cpus 4 --workdir /opt/target \\
  --entrypoint /bin/bash "$IMAGE" -lc $(printf '%q' "$test_cmd")
EOF
    chmod +x "$ENV_DIR/build.sh" "$ENV_DIR/run.sh" "$ENV_DIR/test.sh"
}

write_manifest() {
    local status="$1" image_id="$2" build_rc="$3"
    local langs_json install_json limits_json partial_json sys_json
    langs_json="$(printf '%s\n' "${LANGS[@]}" | jq -R . | jq -s 'map(select(length>0))')"
    install_json="$(jq -n --argjson cmds "$(printf '%s\n' "${INSTALL_CMDS[@]:-}" | jq -R . | jq -s 'map(select(length>0))')" --argjson langs "$(printf '%s\n' "${INSTALL_LANGS[@]:-}" | jq -R . | jq -s 'map(select(length>0))')" '$cmds as $c | $langs as $l | [range(0; ($c|length)) | {lang:$l[.], cmd:$c[.]}]')"
    limits_json="$(printf '%s\n' "${LIMITATIONS[@]:-}" | jq -R . | jq -s 'map(select(length>0))')"
    partial_json="$(printf '%s\n' "${PARTIAL_REASONS[@]:-}" | jq -R . | jq -s 'map(select(length>0))')"
    sys_json="$(printf '%s\n' "${SYS_PKGS[@]:-}" | jq -R . | jq -s 'map(select(length>0))')"
    jq -n \
        --arg schema_version "1" \
        --arg project "$PROJECT" \
        --arg source "$SOURCE" \
        --arg commit "$COMMIT" \
        --arg image "$IMAGE" \
        --arg base_image "$BASE_IMAGE" \
        --arg mode "$MODE" \
        --arg status "$status" \
        --arg build_log "$BUILD_LOG" \
        --arg built_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg image_id "$image_id" \
        --argjson build_rc "$build_rc" \
        --argjson languages "$langs_json" \
        --argjson system_packages "$sys_json" \
        --argjson install_commands "$install_json" \
        --argjson limitations "$limits_json" \
        --argjson partial_reasons "$partial_json" \
        --arg workdir "/opt/target" \
        --arg run_cmd "$ENV_DIR/run.sh" \
        --arg test_cmd "$ENV_DIR/test.sh" \
        '{
            schema_version: $schema_version,
            project: $project,
            source: $source,
            commit: $commit,
            image: $image,
            base_image: $base_image,
            mode: $mode,
            env_status: $status,
            built_at: $built_at,
            image_id: $image_id,
            build_exit_code: $build_rc,
            build_log: $build_log,
            detected: {languages: $languages, system_packages: $system_packages},
            install_commands: $install_commands,
            limitations: $limitations,
            partial_reasons: $partial_reasons,
            workdir: $workdir,
            run_script: $run_cmd,
            test_script: $test_cmd
        }' > "$ENV_DIR/env-manifest.json"
}

if [ "$NO_GENERATE" -eq 0 ]; then
    if [ -f "$ENV_DIR/Dockerfile" ] && [ "$FORCE" -eq 0 ]; then
        log "复用已存在 Dockerfile（--force 可覆盖）: $ENV_DIR/Dockerfile"
    else
        gen_dockerfile
    fi
    gen_helpers
fi

log "project=$PROJECT commit=$COMMIT"
log "languages=${LANGS[*]}"
log "mode=$MODE status=pending image=$IMAGE"
[ "${#PARTIAL_REASONS[@]}" -gt 0 ] && log "partial: ${PARTIAL_REASONS[*]}"

if [ "$DRY_RUN" -eq 1 ] || [ "$NO_BUILD" -eq 1 ]; then
    write_manifest "planned" "" 0
    echo "=== build_env plan ==="
    jq . "$ENV_DIR/env-manifest.json"
    echo "Dockerfile: $ENV_DIR/Dockerfile"
    exit 0
fi

if ! docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
    die "基础镜像不存在: $BASE_IMAGE" 20
fi

log "开始构建（超时 ${BUILD_TIMEOUT}s，网络 $NETWORK）..."
: > "$BUILD_LOG"
set +e
NET_ARG=()
if [ "$NETWORK" != "default" ]; then NET_ARG=(--network "$NETWORK"); fi
timeout --signal=TERM --kill-after=30 "$BUILD_TIMEOUT" \
    docker build "${NET_ARG[@]}" -f "$ENV_DIR/Dockerfile" -t "$IMAGE" "$SOURCE" \
    >> "$BUILD_LOG" 2>&1
BUILD_RC=$?
set -e

IMAGE_ID="$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || true)"
if [ "$BUILD_RC" -ne 0 ]; then
    log "构建失败 rc=$BUILD_RC，日志: $BUILD_LOG"
    write_manifest "blocked" "$IMAGE_ID" "$BUILD_RC"
    tail -n 30 "$BUILD_LOG" >&2 || true
    exit 20
fi

STATUS="ready"
[ "${#PARTIAL_REASONS[@]}" -gt 0 ] && STATUS="partial"
write_manifest "$STATUS" "$IMAGE_ID" "$BUILD_RC"
log "构建完成 status=$STATUS image=$IMAGE"
echo "=== env manifest ==="
jq . "$ENV_DIR/env-manifest.json"
if [ "$STATUS" = "partial" ]; then exit 10; fi
exit 0
