# Rust Builder/配置批量赋值漏洞

## Details

### 漏洞成因
Rust 项目中常使用 Builder 模式（`derive_builder`, 手写 Builder）、配置加载（`config` crate, `serde_yaml`, `toml`）以及插件系统，为结构体提供链式赋值或从配置文件批量填充。如果 Builder/配置未限制可写字段，攻击者可通过 CLI 参数、环境变量、配置文件、HTTP API 等方式修改敏感字段（如 `admin_enabled`, `remote_shell`, `rate_limit`, `tenant`, `feature_flags`），导致安全策略被绕过。

### 代码示例

**易受攻击的代码：**
```rust
#[derive(Default)]
pub struct AppConfig {
    pub database_url: String,
    pub admin_enabled: bool,
    pub rate_limit: u32,
}

impl AppConfig {
    pub fn apply(&mut self, input: serde_yaml::Value) {
        if let Some(obj) = input.as_mapping() {
            for (key, value) in obj {
                let key = key.as_str().unwrap();
                match key {
                    "database_url" => self.database_url = value.as_str().unwrap().to_string(),
                    "admin_enabled" => self.admin_enabled = value.as_bool().unwrap_or(false),
                    "rate_limit" => self.rate_limit = value.as_u64().unwrap_or(0) as u32,
                    _ => {} // 未拒绝未知字段
                }
            }
        }
    }
}
```

**另一个不安全示例（Builder 模式）：**
```rust
#[derive(Deserialize, Builder)]
#[builder(setter(into))]
pub struct UserUpdate {
    pub email: String,
    pub display_name: Option<String>,
    pub is_admin: Option<bool>; // builder 自动生成 setter
}

pub async fn update_user(payload: UserUpdate) {
    let update = UserUpdateBuilder::from(payload).build().unwrap();
    repository.save_update(update).await; // is_admin 可被覆盖
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `derive_builder`, `Builder`, `builder.set_`, `build()`
- 配置加载：`config::Config`, `serde_yaml`, `toml::from_str`
- `apply_config`, `merge`, `update_from`, `override`
- 结构体字段：`admin`, `enable`, `tenant`, `feature`

**定位步骤：**
1. 搜索 Builder 定义或配置加载函数。
2. 检查是否有敏感字段在 Builder/配置中暴露。
3. 跳读（L2）确认是否对输入字段进行白名单过滤或权限校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** 限制配置/Builder 仅接受特定字段。
- **敏感字段只读：** 不在配置/Builder 中暴露敏感字段。
- **签名/权限校验：** 配置来源受签名或权限控制。
- **默认安全值：** 即使被覆盖也保持安全（需要验证）。
- **环境隔离：** 区分生产/开发配置，避免外部输入修改。

**定位技巧：**
- 检查 Builder 是否为所有字段生成 setter（`#[builder(setter(strip_option))]` 等）。
- 确认配置文件是否支持 include/merge，避免引入未知字段。
- 对 CLI/HTTP 接口触发的配置更新，确认权限和字段控制。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 配置白名单 + 签名校验 | **L0（快速跳过）** | 风险低 |
| Builder 暴露有限字段 | **L2（跳读）** | 检查敏感字段是否被拒绝 |
| Builder/配置直接接受外部输入 | **L3（逐行读）** | 高风险 |
| 多模块共享配置/插件系统 | **L4（跨模块追踪）** | 需分析全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **Builder/配置加载** 接受不可信输入。
2. **敏感字段可被设置或覆盖**。
3. **导致安全策略、权限或资源限制被绕过**。

#### 误报
可视为误报的情况：
1. Builder/配置仅在受控内部使用，输入受信且有校验。
2. 敏感字段未暴露或在应用前被重写。
3. 配置文件需要签名/加密且不可由攻击者修改。

#### 代码异味
需关注的风险：
1. 依赖黑名单过滤敏感字段。
2. 使用 `merge`/`override` 等深度合并，易遗漏。
3. 配置源可被外部更新（REST API、MQ 消息）但无权限控制。
4. 缺乏审计日志，无法追踪配置变更。

## Low risk

### 低风险评级场景

#### 1. 内部工具配置
- **场景：** 配置仅由受信工程师管理，通过版本控制部署。
- **风险评估：** 攻击面有限，但需防误配置。

#### 2. 签名/加密配置
- **场景：** 配置文件需签名或加密，未签名则拒绝。
- **风险评估：** 风险较低，但需确保校验不可绕过。

#### 3. 运行时隔离
- **场景：** 调整配置后仍处于最小权限容器/沙箱。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计日志
- **场景：** 对配置/Builder 调用记录日志与告警。
- **风险评估：** 有助于监测，仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部受控来源 | 攻击面有限 | 中 |
| 签名/白名单 | 技术防护完善 | 低 |
| 沙箱隔离 | 限制影响 | 中 |
| 审计监控 | 及时发现异常 | 高（持续改进）|

