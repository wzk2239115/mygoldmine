# Rust JWT Insecure Decoding

## 漏洞成因
使用 jsonwebtoken crate 时配置 Validation 结构体不当，通过 `insecure_disable_signature_validation()`、`validate_exp = false` 等方式禁用签名验证或关键声明校验，导致伪造、过期、未授权的 token 均可通过验证。

---

## Details

### 代码示例

**jsonwebtoken crate 典型漏洞模式：**

```rust
use jsonwebtoken::{decode, decode_header, Validation, DecodingKey, Algorithm};

// 漏洞1：完全禁用签名验证
let mut validation = Validation::default();
validation.insecure_disable_signature_validation();
let token_data = decode::<Claims>(&token, &DecodingKey::from_secret(&[]), &validation);

// 漏洞2：禁用exp校验
let mut validation = Validation::new(Algorithm::HS256);
validation.validate_exp = false;
let token_data = decode::<Claims>(&token, &key, &validation);

// 漏洞3：禁用多个声明校验
let mut validation = Validation::new(Algorithm::HS256);
validation.validate_exp = false;
validation.validate_nbf = false;
validation.aud = None;  // 不校验audience
let token_data = decode::<Claims>(&token, &key, &validation);

// 漏洞4：使用危险的DecodingKey
let validation = Validation::default();
let token_data = decode::<Claims>(&token, &DecodingKey::from_secret(&[]), &validation);

// 漏洞5：仅解码header不验证
let header = decode_header(&token)?;
let parts: Vec<&str> = token.split('.').collect();
let payload = base64::decode(parts[1])?;  // 手动解码不验证
```

**危险的Validation配置组合：**

```rust
// 签名验证被禁用，其他校验无意义
let mut validation = Validation::new(Algorithm::HS256);
validation.insecure_disable_signature_validation();
validation.validate_exp = true;  // 签名都不验证，这个也失效

// 允许任意算法（算法混淆攻击）
let mut validation = Validation::default();
validation.algorithms = vec![Algorithm::HS256, Algorithm::HS384, Algorithm::HS512, Algorithm::RS256];
```

### 快速定位核心操作技巧 **[L1-L2]**

**L1 关键词扫描：**
- 搜索 `decode::<` 或 `jsonwebtoken::decode`
- 定位 `Validation::` 构造点
- 检索 `insecure_disable_signature_validation`
- 搜索 `validate_exp`、`validate_nbf`、`aud`、`iss` 字段赋值

**L2 跳读确认：**
- 检查 `Validation` 结构体初始化方式（`default()` / `new(algo)` / 自定义配置）
- 确认是否调用 `insecure_disable_signature_validation()`
- 检查 `validate_*` 布尔字段是否被设为 `false`
- 确认 `aud`/`iss`/`sub` 是否为 `None`（表示不校验）
- 检查 `algorithms` 向量是否包含过多算法类型

### 快速定位保护机制技巧 **[L2-L4]**

**L2 跳读检查：**
- 确认 `Validation` 使用 `new(Algorithm::XXX)` 而非 `default()`（`new` 会校验算法）
- 检查是否设置 `set_audience(&["expected_aud"])`
- 确认是否设置 `iss = Some(HashSet::from(["expected_issuer"]))`
- 检查 `validate_exp` 和 `validate_nbf` 是否保持默认 `true`

**L3 逐行验证：**
- 检查 `decode()` 调用后是否有 `.map_err()` 或 `?` 进行错误传播（确保验证失败会中断）
- 确认 `DecodingKey` 来源是否安全（非空密钥、从配置/环境变量读取）
- 验证是否在 `decode()` 后手动二次校验 claims（`claims.exp > current_time`）
- 检查是否使用自定义 `Deserialize` 实现进行额外验证

**L4 跨模块追踪：**
- 追踪 `Validation` 配置来源：是否从全局常量、配置模块、构建器模式创建
- 追踪密钥管理：`DecodingKey` 是否从安全存储（环境变量、密钥管理服务）加载
- 检查中间件/拦截器层：Actix/Rocket/Axum 中的认证中间件是否统一配置 Validation
- 确认错误处理：`decode()` 返回的 `Result` 是否被正确处理（拒绝无效token）

**保护性代码特征：**

```rust
// 正确示例：默认启用所有验证
let validation = Validation::new(Algorithm::HS256);
let token_data = decode::<Claims>(&token, &decoding_key, &validation)?;

// 显式声明校验
let mut validation = Validation::new(Algorithm::HS256);
validation.set_audience(&["myapp"]);
validation.set_issuer(&["auth-service"]);
validation.validate_exp = true;  // 显式确认（默认已是true）
let token_data = decode::<Claims>(&token, &decoding_key, &validation)?;

// 严格的密钥加载
let secret = env::var("JWT_SECRET").expect("JWT_SECRET must be set");
let decoding_key = DecodingKey::from_secret(secret.as_bytes());
```

---

## Classify

### 漏洞判定标准

1. **确认漏洞**：
   - 调用 `insecure_disable_signature_validation()` 直接定性为高危漏洞
   - `validate_exp = false` 且 token 用于身份认证/授权，属于高危
   - `DecodingKey::from_secret(&[])` 使用空密钥，等同于禁用签名验证

2. **场景区分**：
   - 解码后的 claims 用于数据库查询条件、权限判断、会话恢复 → 高危
   - 仅用于日志记录、统计分析且不影响授权决策 → 低危或误报

3. **上下文关联**：
   - 若 `decode()` 后立即进行手动校验（检查 exp、匹配白名单），可降级为代码异味
   - 若在测试模块（`#[cfg(test)]`）或 examples/ 目录中，可能为误报

### 误报识别

1. **测试/演示代码**：
   - 位于 `tests/`、`examples/`、`benches/` 目录
   - 带有 `#[cfg(test)]` 或 `#[cfg(debug_assertions)]` 条件编译
   - 文件名或函数名包含 `_test`、`_example`、`mock_`

2. **非认证场景**：
   - 明确注释说明仅用于解析公开数据（如解析第三方 API 返回的 JWT 以获取元数据）
   - decode 后不使用 claims 进行权限决策，仅提取非敏感信息

3. **多阶段验证**：
   - 先用宽松配置解码获取 claims，再通过数据库查询验证 token 有效性（如黑名单/白名单机制）
   - 后续有严格的业务层校验逻辑补偿

### 代码异味特征

1. **部分禁用**：
   - 仅禁用 `validate_nbf` 但保留 exp 校验，且业务确实不使用 "not before" 时间
   - 不校验 aud/iss 但通过其他方式（如检查 sub 字段）确认来源

2. **冗余验证**：
   - 禁用库级 exp 校验但实现了等效的手动时间检查
   - 使用自定义 Deserialize trait 实现验证逻辑（不推荐但可用）

3. **算法过度宽松**：
   - `algorithms` 向量包含多种算法但实际只使用一种（增加攻击面）

---

## Low Risk

### 低风险评级条件

1. **非核心身份场景**：
   - token 仅用于前端状态同步、日志追踪、性能指标收集等非授权决策
   - 解码数据不影响敏感操作（如仅展示用户昵称、头像 URL）

2. **内网隔离环境**：
   - 仅在完全可信的内部微服务间传递，且攻击者无法访问 token 生成/传输链路
   - 通过 mTLS、VPN 等机制确保网络层隔离

3. **短生命周期 + 严格上下文**：
   - exp 禁用但 token 有效期极短（< 30秒）且结合其他强验证机制（如 IP 白名单、请求签名）
   - 使用一次性 nonce 或 jti（JWT ID）防止重放

4. **显式业务需求**：
   - 架构设计明确要求支持过期 token 的特殊场景（如长期离线设备同步）
   - 有完善的业务层防护和审计日志

5. **过渡期方案**：
   - 为兼容遗留系统临时禁用校验，且已有明确的修复 roadmap
   - 实施了补偿性控制（如 WAF 规则、额外的中间件校验）

### 注意事项

1. **Rust 编译期安全局限**：即使 Rust 保证内存安全，配置不当仍会导致逻辑漏洞
2. **升级风险**：jsonwebtoken crate 版本升级可能改变默认行为，需回归测试
3. **文档警告**：官方文档明确标注 `insecure_disable_signature_validation()` 为危险 API，使用需充分评估
4. **审计标注**：即使满足低风险条件，仍需在报告中标注为"技术债务"，防止未来场景变化导致风险升级
