# C/C++ RPC 处理函数缺失角色校验

## Details

### 漏洞成因
许多 C/C++ 服务通过自定义 RPC 协议暴露内部功能。若 RPC 处理函数（handler）仅验证消息格式，而不确认调用者身份或角色，就可能被未授权客户端直接调用敏感接口，如远程配置、固件升级、账户管理等。尤其在内网服务、嵌入式设备或分布式系统中，常见仅依赖 IP 白名单或会话 ID，缺少细粒度的函数级权限控制。

### 代码示例

**易受攻击的代码：**
```c
void rpc_handle_message(Session *sess, RpcMessage *msg) {
    switch (msg->type) {
    case RPC_UPDATE_ROLE:
        handle_update_role(sess, msg->payload); // 未检查 sess->role
        break;
    case RPC_RESET_PASSWORD:
        handle_reset_password(sess, msg->payload);
        break;
    default:
        break;
    }
}
```

**安全示例：**
```c
bool rpc_require_role(Session *sess, Role required) {
    return sess && sess->role >= required;
}

void rpc_handle_message(Session *sess, RpcMessage *msg) {
    switch (msg->type) {
    case RPC_UPDATE_ROLE:
        if (!rpc_require_role(sess, ROLE_ADMIN)) {
            log_warn("unauthorized RPC_UPDATE_ROLE");
            return;
        }
        handle_update_role(sess, msg->payload);
        break;
    // ...
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `rpc`, `handle_message`, `process_request`, `switch`, `case`, `handler_table`。

**定位步骤：**
1. 找出 RPC 分发入口函数；
2. 跳读（L2）检查敏感 `case` 语句或 handler 调用前是否有权限判断；
3. 查看 Session/Context 是否包含身份/角色信息但未使用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 会话级别的角色信息与校验函数；
- handler 表中声明所需权限；
- 统一的 ACL/RBAC 组件；
- RPC 层使用 TLS 客户端证书或签名校验，但仍需细粒度授权。

**定位技巧：**
- 逐行读（L3）敏感 RPC，如角色管理、系统配置等；
- 跨模块追踪（L4）确认 RPC 是否可被外网、合作方或脚本访问。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| RPC 框架统一注入权限检查 | **L0（快速跳过）** | 安全保障充分 |
| 仅部分 handler 校验角色 | **L2（跳读）** | 快速确认遗漏 |
| handler 完全无权限判断 | **L3（逐行读）** | 高风险 |
| RPC 对外暴露且无统一认证 | **L4（跨模块追踪）** | 必须全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 未授权客户端可调用敏感 RPC；
2. handler 未进行角色或权限校验；
3. 能复现越权（例如普通用户升级为管理员）。

#### 误报
1. RPC 仅在受信任通道，且入口统一实施授权；
2. handler 内部调用权限模块并拒绝未授权请求；
3. 函数仅提供只读、非敏感信息。

#### 代码异味
1. 权限检查散落各 handler，易漏；
2. 仅依赖 IP 白名单或硬编码 token；
3. 缺少对审计日志与失败告警的处理。

## Low risk

### 低风险评级场景

#### 1. RPC 仅供内部自动化调用
- **场景：** 服务部署在隔离网络，通过 VPN 访问；
- **评估：** 可降级但仍需监控。

#### 2. 函数影响面小
- **场景：** Handler 只读信息或触发低风险操作；
- **评估：** 标记低风险并记录。

#### 3. 已计划引入统一权限网关
- **场景：** 团队将迁移到 API Gateway/RBAC；
- **评估：** 暂列低风险，并跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 隔离网络 | 攻击面低 | 中 |
| 影响面小 | 风险有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
