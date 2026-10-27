---
name: config-trust-scanner
description: |
  配置信任审阅技能（agentic）。检查 Docker/compose/k8s/MCP/agent 配置中的危险默认值、
  项目级配置自动生效、命令执行、明文凭据与权限削弱。
---

# Config Trust Scanner

> 知识/审阅流程，不含检测脚本。由 `infra-analyst` 读取配置并写成 finding。

## 输入

- 配置文件：`Dockerfile`、`docker-compose*.yml`、`helm/`、`k8s/`、`.mcp.json`、
  `.codex/config.toml`、`.claude/settings.json`、`AGENTS.md`、`CLAUDE.md`
- 项目知识卡：`knowledge/projects/<project>.md`

## 审阅步骤

1. **项目级配置是否自动生效**：
   - `.mcp.json` 的 `command/args/env` 是否直接执行？
   - `.codex/config.toml` 的 `mcp_servers`、`approval_policy`、`sandbox` 是否无确认加载？
   - 首次打开仓库是否弹确认？是否有 denylist？
2. **命令执行**：
   - `command`/`args`、`sh -c`、`curl | sh`、`git hooks`、`fsmonitor`、clean/process filter。
3. **权限/隔离**：
   - `USER root`、`privileged`、`docker.sock`、`hostNetwork`、`hostPath`、`CAP_SYS_ADMIN`、
     `seccomp=unconfined`、`runAsUser: 0`。
4. **凭据**：
   - Dockerfile `ENV/ARG`、compose `environment`、manifest 中明文 key/token。
5. **危险默认**：
   - `allow_origins=["*"]`、`verify=False`、`DEBUG=True`、`trust_remote_code=True`、
     `bypassPermissions`、`approval_policy=never`、`sandbox: false`。
6. **可达性**：默认生效？需要用户确认？只在 dev/示例中？

## 输出

canonical finding + 配置证据（文件、行、片段）。对“配置示例”与“产品默认”分开标注。

## 误报排除

- 危险选项只在 `--dangerously-*`/显式确认后生效 → `opt-in`。
- 示例/测试/CI 中的配置不算产品默认行为。
- 密钥位置只报告，不写原文；已轮换/占位符不算泄露。
- 反向代理/平台已提供隔离 → 需要证据，不能直接算容器逃逸。

## 验证

- 用环境镜像检查实际生效配置（`docker inspect`/启动日志/`--help`）。
- 不执行不可信构建脚本；只在隔离容器内做配置级验证。
