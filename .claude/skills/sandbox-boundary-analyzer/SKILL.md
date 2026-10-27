---
name: sandbox-boundary-analyzer
description: |
  Agent/容器沙箱边界审阅技能（agentic）。检查审批、权限模式、sandbox、路径约束、
  容器隔离与宿主挂载，判断是否存在默认可达的逃逸/越权。
---

# Sandbox Boundary Analyzer

> 知识/审阅流程，不含检测脚本。重点是“默认是否开启隔离”和“是否有可控输入到达边界”。

## 输入

- 源码与配置：agent settings、approval policy、sandbox 实现、Docker/k8s、路径解析
- `knowledge/projects/<project>.md`、`knowledge/project-types/agent-harness.md`

## 审阅步骤

1. **审批/权限**：
   - `bypassPermissions`、`dangerously-skip-permissions`、`approval_policy=never`、
     `auto_approve`、`allow_prefix`、`allowed_tools`。
   - 默认是“逐条确认”还是“自动执行”？
2. **沙箱**：
   - sandbox 默认开启/关闭？实现是 seccomp/landlock/namespace/bubblewrap 还是仅路径检查？
   - 网络、文件系统、进程、环境变量限制是否完整？
3. **路径约束**：
   - `os.path.join`/`Path.resolve` 后是否校验必须位于受信根？
   - symlink、`..`、大小写、URL 解码能否绕过？
4. **容器隔离**：
   - `privileged`、`docker.sock`、`hostPath`、`hostNetwork`、`CAP_SYS_ADMIN`、
     `seccomp=unconfined`、`apparmor=unconfined`。
5. **控制面**：
   - 本地 app-server/exec-server 是否绑定回环？是否需要 token？是否允许同用户任意进程调用？
6. **可达性**：默认配置是否关闭隔离？需要用户显式危险选项？

## 输出

写清：边界、可控输入、绕过条件、默认是否可达、`file:line`、证据、修复建议。
没有完整绕过链的只写 hypothesis。

## 误报排除

- 沙箱/审批默认开启，只有文档示例关闭 → 不算默认漏洞。
- 只绑定回环 + 同用户信任 → 说明威胁模型，降级。
- 危险选项需要显式 `--dangerously`/确认 → `opt-in`。
- 路径检查存在 realpath + 前缀校验 + symlink 拒绝 → 需要具体绕过证据。

## 验证

- 只做配置级/benign marker 验证，不写武器化逃逸。
- 用环境镜像检查实际 sandbox/approval 配置与默认值。
- 路径验证只读容器内测试文件，不访问宿主敏感路径。
