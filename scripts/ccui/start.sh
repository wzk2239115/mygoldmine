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

while [ "$#" -gt 0 ]; do
    case "$1" in
        --port) [ "$#" -ge 2 ] || exit 2; PORT="$2"; shift ;;
        --host) [ "$#" -ge 2 ] || exit 2; HOST="$2"; shift ;;
        --home) [ "$#" -ge 2 ] || exit 2; CC_HOME="$2"; shift ;;
        --no-import) DO_IMPORT=0 ;;
        --include-smoke) INCLUDE_SMOKE=1 ;;
        --rebuild) REBUILD=1 ;;
        -h|--help)
            cat <<'EOF'
用法: scripts/ccui/start.sh [选项]

  --port PORT       CloudCLI 端口（默认 3001 或 CCUI_PORT）
  --host HOST       绑定地址（默认 127.0.0.1 或 CCUI_HOST）
  --home DIR        合成 HOME（默认 runs/ccui-home）
  --no-import       不重新导入 mygoldmine runs
  --include-smoke   也导入 smoke* 测试 run
  --rebuild         强制重建 CloudCLI 前后端
  -h, --help        显示帮助

首次运行需要先 npm install 并 npm run build，耗时较长。
首次打开 UI 需要在浏览器里设置本地用户名/密码。
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
    (cd "$CCUI_DIR" && npm run build)
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
echo "[ccui] first run: open the URL and create a local username/password."
echo "[ccui] Ctrl+C to stop."
echo

exec env HOME="$CC_HOME" SERVER_PORT="$PORT" HOST="$HOST" \
    node "$CCUI_DIR/dist-server/server/index.js"
