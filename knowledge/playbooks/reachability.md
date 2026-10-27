# Playbook：可达性与严重度

## reachability

- `default`：默认配置、默认启动参数即可到达。
- `opt-in`：需要用户显式开启危险选项（`--dangerously-*`、`bypassPermissions`）。
- `dev-only`：只在 dev/RL/调试模式启用。
- `requires-config`：需要特定配置/数据集/模型/插件。
- `unknown`：无法确定，必须降级并写明。

## severity 校准

- Critical：默认可达 + 未授权 + RCE/沙箱逃逸/大规模凭据泄露。
- High：默认可达 + 未授权 + 敏感数据/权限提升/条件 RCE；或 opt-in 但影响极大。
- Medium：需要配置/本地访问/有限影响；供应链卫生；DoS（非默认无界）。
- Low：信息性、需要高权限、仅文档/示例。

## 规则

1. 默认不可达的 RCE 不要标 Critical；标 `opt-in`/`dev-only` + High。
2. 同一 root cause 只保留最高 severity，其余写 aliases。
3. 认证缺失但只绑定回环 → 降级，并说明威胁模型。
4. 供应链卫生（未 pin 版本、`curl | sh`）通常 Medium/Low，不与 RCE 同级。
5. 无法验证的条目 `verification.status=unverified`，最终报告必须区分。
