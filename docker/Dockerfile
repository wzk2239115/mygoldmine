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

FROM python:3.12-slim

ARG UID=1000
ARG GID=1000
ARG CLAUDE_CODE_VERSION=2.1.138

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
        nodejs \
        npm \
        tini \
    && rm -rf /var/lib/apt/lists/*

# tree-sitter 用于多语言结构化分析；language-pack 覆盖主流语言
RUN python3 -m pip install --no-cache-dir \
        tree-sitter \
        tree-sitter-language-pack

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
COPY docs /opt/mygoldmine/docs
COPY README.md TODOLIST.md /opt/mygoldmine/

RUN mkdir -p /workspace/repo /runs /target \
    && chmod +x /opt/mygoldmine/scripts/mine/entrypoint.sh \
    && chown -R miner:miner /opt/mygoldmine /workspace /runs /home/miner

ENV HOME=/home/miner \
    MYGOLDMINE_HOME=/opt/mygoldmine \
    TARGET_DIR=/target \
    WORK_DIR=/workspace/repo \
    TIMEOUT=21600 \
    MODEL=360-proxy/deepseek/deepseek-v4.1-flash \
    AGENT=security-orchestrator

USER miner

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/mygoldmine/scripts/mine/entrypoint.sh"]
