# Rust｜命令路由缺少角色校验

## Details

### 漏洞成因
Rust 服务可能使用 HashMap 或匹配语句根据命令名称路由到不同处理函数（例如 CLI、WebSocket、gRPC 自定义命令）。若路由层未校验当前用户角色，仅依据命令名称执行 handler，普通用户即可触发管理员命令。该模式与 C/C++ 类似，在 Rust 中常见于 `HashMap<&'static str, Handler>`、`match command`。

### 代码示例

**易受攻击示例：**
```rust
lazy_static! {
    static ref COMMANDS: HashMap<&'static str, CommandHandler> = {
        let mut m = HashMap::new();
        m.insert("restart", restart_service);
        m.insert("get_status", get_status);
        m
    };
}

fn dispatch_command(ctx: &Context, cmd: &str, payload: &Value) {
    if let Some(handler) = COMMANDS.get(cmd) {
        handler(ctx, payload); // 未校验 ctx.user.role
    }
}
```

**安全示例：**
```rust
struct CommandEntry {
    required_role: Role,
    handler: CommandHandler,
}

fn dispatch_command(ctx: &Context, cmd: &str, payload: &Value) {
    if let Some(entry) = COMMANDS.get(cmd) {
        if !ctx.user.has_role(entry.required_role) {
            log::warn!("unauthorized command {}", cmd);
            return;
        }
        (entry.handler)(ctx, payload);
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `HashMap`, `command`, `dispatch`, `match cmd`, `CommandHandler`, `router`。

**定位步骤：**
1. 检查命令注册表与路由函数；
2. 跳读（L2）确认调用前是否校验权限；
3. 查看 `Context` / `Session` 是否有角色信息。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 命令结构包含 `required_role`；
- 调度前调用策略模块；
- 管理命令与普通命令不同通道；
- 使用特权令牌或签名。

**定位技巧：**
- 逐行读（L3）敏感命令的 handler；
- 跨模块追踪（L4）命令是否可通过 Web/API 触发。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Command 注册即带权限 | **L0（快速跳过）** | 风险低 |
| 部分命令缺权限 | **L2（跳读）** | 需确认 |
| 命令无任何校验 | **L3（逐行读）** | 高风险 |
| 命令可从外部触发 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 命令路由缺少角色判断；
2. 普通用户可执行特权命令；
3. 行为影响系统状态或配置。

#### 误报
1. 路由仅供内部服务使用，并有额外认证；
2. 命令仅查询公开状态；
3. Handler 自行拒绝未授权调用并证明不可绕过。

#### 代码异味
1. 命令表中混杂管理员和普通命令；
2. 依赖命令前缀区分权限；
3. 缺少审计日志。

## Low risk

### 低风险评级场景

#### 1. 命令仅返回诊断信息
- **评估：** 可标低风险。

#### 2. 运行在受控环境
- **评估：** 攻击面有限。

#### 3. 即将迁移至统一权限路由
- **评估：** 暂降级，跟踪实施。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 诊断用途 | 影响有限 | 低 |
| 受控环境 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
