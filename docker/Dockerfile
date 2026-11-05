# mygoldmine 审计容器（T07）
#
# 设计依据：docs/docker-claude-mining.md 第 3 节
# - 单容器，非 root 运行
# - 预装 python3 / jq / git / ripgrep / tree-sitter / Claude Code CLI
# - 不安装 Docker CLI，默认不挂载 /var/run/docker.sock
# - 目标源码运行时只读挂载到 /target，可写副本在 /workspace/repo
#
# 构建：
#   docker build -f docker/Dockerfile \
#     --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" \
#     -t mygoldmine:dev .
#
# 若 Docker daemon 配置的代理是 127.0.0.1（构建容器无法访问宿主回环），
# 追加 --network host，例如：
#   docker build --network host -f docker/Dockerfile -t mygoldmine:dev .

FROM node:22-bookworm-slim AS claude-node

FROM python:3.12-slim

ARG UID=1000
ARG GID=1000
ARG CLAUDE_CODE_VERSION=2.1.318

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NODE_OPTIONS=--max-old-space-size=2048

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        ripgrep \
        tini \
    && rm -rf /var/lib/apt/lists/*

# 新版 Claude Code 要求 Node.js 22 或更高版本。
COPY --from=claude-node /usr/local/bin/node /usr/local/bin/node
COPY --from=claude-node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# 审计运行镜像依赖集中在 runner/requirements.txt。
# 目标项目依赖由第 0 阶段环境构建负责，不能写进这里。
COPY runner/requirements.txt /tmp/runner-requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/runner-requirements.txt

# Claude Code CLI，版本固定，可用 --build-arg CLAUDE_CODE_VERSION 覆盖
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force \
    && claude --version

# 非 root 用户：默认 UID/GID 1000，构建期可覆盖
RUN groupadd --gid "${GID}" miner 2>/dev/null || true \
    && useradd --uid "${UID}" --gid "${GID}" --create-home --shell /bin/bash miner 2>/dev/null || true

WORKDIR /opt/mygoldmine

# 审计骨架：skills/agents/hooks 与脚本。目标源码不进入镜像。
COPY .claude /opt/mygoldmine/.claude
COPY scripts /opt/mygoldmine/scripts
COPY audit_rsi /opt/mygoldmine/audit_rsi
COPY knowledge /opt/mygoldmine/knowledge
COPY docs /opt/mygoldmine/docs
COPY README.md TODOLIST.md /opt/mygoldmine/
COPY runner /opt/mygoldmine/runner

# 构建期直接验收运行依赖；缺包时不要产出一个看似可用的镜像。
RUN python3 /opt/mygoldmine/scripts/runner/smoke_runner.py --command "claude --version"

RUN mkdir -p /workspace/repo /runs /target \
    && chmod +x /opt/mygoldmine/scripts/mine/entrypoint.sh \
    && chown -R miner:miner /opt/mygoldmine /workspace /runs /home/miner

ENV HOME=/home/miner \
    MYGOLDMINE_HOME=/opt/mygoldmine \
    TARGET_DIR=/target \
    WORK_DIR=/workspace/repo \
    TIMEOUT=21600 \
    MODEL=deepseek/deepseek-v4.1-flash \
    ANTHROPIC_BASE_URL=https://api.360.cn \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    AGENT=security-orchestrator

USER miner

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/mygoldmine/scripts/mine/entrypoint.sh"]
