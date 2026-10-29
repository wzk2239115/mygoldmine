#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CCUI_DIR="$REPO_ROOT/third_party/claudecodeui"
CC_HOME="${CCUI_HOME:-$REPO_ROOT/runs/ccui-home}"
PORT="${CCUI_PORT:-3001}"
HOST="${CCUI_HOST:-127.0.0.1}"
DO_IMPORT=1
INCLUDE_SMOKE=0
REBUILD=0
PLATFORM=1

while [ "$#" -gt 0 ]; do
    case "$1" in
        --port) [ "$#" -ge 2 ] || exit 2; PORT="$2"; shift ;;
        --host) [ "$#" -ge 2 ] || exit 2; HOST="$2"; shift ;;
        --home) [ "$#" -ge 2 ] || exit 2; CC_HOME="$2"; shift ;;
        --no-import) DO_IMPORT=0 ;;
        --include-smoke) INCLUDE_SMOKE=1 ;;
        --rebuild) REBUILD=1 ;;
        --no-platform) PLATFORM=0 ;;
        -h|--help)
            cat <<'EOF'
用法: scripts/ccui/start.sh [选项]

  --port PORT       CloudCLI 端口（默认 3001 或 CCUI_PORT）
  --host HOST       绑定地址（默认 127.0.0.1 或 CCUI_HOST）
  --home DIR        合成 HOME（默认 runs/ccui-home）
  --no-import       不重新导入 mygoldmine runs
  --include-smoke   也导入 smoke* 测试 run
  --rebuild         强制重建 CloudCLI 前后端
  --no-platform     关闭平台模式（回到常规注册/登录流程）
  -h, --help        显示帮助

默认平台模式（VITE_IS_PLATFORM=true）：跳过登录，所有请求自动以本地
seed 用户身份执行。首次启动会自动注册随机口令的 seed 用户，凭据写在
runs/ccui-home/ccui-credentials.json。服务只绑定本机回环地址。
EOF
            exit 0
            ;;
        *) echo "未知参数: $1" >&2; exit 2 ;;
    esac
    shift
done

[ -d "$CCUI_DIR" ] || { echo "missing submodule: $CCUI_DIR" >&2; exit 2; }
command -v node >/dev/null 2>&1 || { echo "node not found" >&2; exit 2; }
command -v npm >/dev/null 2>&1 || { echo "npm not found" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 2; }

node -e 'const major=Number(process.versions.node.split(".")[0]); if (major < 22) { console.error(`node >=22 required, got ${process.version}`); process.exit(1); }'

if [ ! -d "$CCUI_DIR/node_modules" ]; then
    echo "[ccui] installing dependencies (first run, may take several minutes)…"
    (cd "$CCUI_DIR" && ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm install --no-audit --no-fund)
fi

if [ "$REBUILD" = "1" ] || [ ! -f "$CCUI_DIR/dist-server/server/index.js" ]; then
    echo "[ccui] building CloudCLI…"
    if [ "$PLATFORM" = "1" ]; then
        (cd "$CCUI_DIR" && VITE_IS_PLATFORM=true npm run build:server && \
         VITE_IS_PLATFORM=true npx vite build --config "$REPO_ROOT/scripts/ccui/vite.config.ccui.mjs")
    else
        (cd "$CCUI_DIR" && npm run build)
    fi
fi

mkdir -p "$CC_HOME/.claude/projects" "$CC_HOME/.cloudcli"

if [ "$DO_IMPORT" = "1" ]; then
    echo "[ccui] importing mygoldmine runs into $CC_HOME/.claude"
    import_args=(
        --runs "$REPO_ROOT/runs"
        --home "$CC_HOME"
    )
    if [ "$INCLUDE_SMOKE" = "1" ]; then
        import_args+=(--include-smoke)
    fi
    python3 "$REPO_ROOT/scripts/ccui/import_runs.py" "${import_args[@]}"
fi

echo
echo "[ccui] CloudCLI: http://$HOST:$PORT"
echo "[ccui] run home: $CC_HOME"
if [ "$PLATFORM" = "1" ]; then
    echo "[ccui] platform mode: no login required (local-only)."
fi
echo "[ccui] Ctrl+C to stop."
echo

run_server() {
    if [ "$PLATFORM" = "1" ]; then
        env HOME="$CC_HOME" SERVER_PORT="$PORT" HOST="$HOST" VITE_IS_PLATFORM=true \
            node "$CCUI_DIR/dist-server/server/index.js" &
    else
        env HOME="$CC_HOME" SERVER_PORT="$PORT" HOST="$HOST" \
            node "$CCUI_DIR/dist-server/server/index.js" &
    fi
    SERVER_PID=$!
}

seed_platform_user() {
    local base="http://$HOST:$PORT"
    local tries=0
    until curl -sf -m 2 "$base/health" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "$tries" -ge 30 ]; then
            echo "[ccui] server did not become healthy; skipping seed" >&2
            return 0
        fi
        sleep 0.5
    done

    local needs_setup
    needs_setup=$(curl -sf -m 3 "$base/api/auth/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("needsSetup"))' 2>/dev/null || echo "")
    if [ "$needs_setup" = "True" ]; then
        local pass
        pass=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
        if curl -sf -m 5 -H 'Content-Type: application/json' \
            -d "{\"username\":\"mygoldmine\",\"password\":\"$pass\"}" \
            "$base/api/auth/register" > /dev/null 2>&1; then
            umask 077
            printf '{"username":"mygoldmine","password":"%s"}\n' "$pass" \
                > "$CC_HOME/ccui-credentials.json"
            echo "[ccui] seeded local user 'mygoldmine' (credentials: $CC_HOME/ccui-credentials.json)"
        else
            echo "[ccui] seed register failed; continuing (user may already exist)" >&2
        fi
    fi

    curl -sf -m 5 -X POST "$base/api/user/complete-onboarding" > /dev/null 2>&1 || true
}

trap 'kill "$SERVER_PID" 2>/dev/null' INT TERM
run_server
if [ "$PLATFORM" = "1" ]; then
    seed_platform_user
fi
wait "$SERVER_PID"
