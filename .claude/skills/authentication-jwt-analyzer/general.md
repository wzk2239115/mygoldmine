# 通用漏洞场景（所有项目必审）

拿到任何使用 JWT 的项目，无论使用何种编程语言，以下安全问题都必须进行审计。这些问题源于 JWT 协议本身的特性和密钥管理机制，与具体语言实现无关。

## JWT 密钥管理漏洞

### JWKS（JSON Web Key Set）不安全使用

#### JWKS URI 验证不足

JWKS URI 用于动态获取 JWT 签名密钥，若验证不当会导致密钥被篡改或替换：

- 未验证 JWKS 端点的 HTTPS、证书或签名，导致中间人攻击，详见：[jwt_jwks_uri_validation.md](jwt_jwks_uri_validation.md)
- JWKS 端点 URL 可被用户控制，导致加载恶意密钥，详见：[jwt_jwks_uri_injection.md](jwt_jwks_uri_injection.md)
- JWKS 缓存过期时间过长，导致密钥轮换延迟，详见：[jwt_jwks_cache_expiry.md](jwt_jwks_cache_expiry.md)

#### JWKS Key ID (kid) 注入

JWT header 中的 `kid` 参数用于指定密钥，若验证不当会导致密钥冒充：

- SQL injection：`kid` 直接用于数据库查询，详见：[jwt_kid_sql_injection.md](jwt_kid_sql_injection.md)
- 目录遍历：`kid` 用于文件路径构造，详见：[jwt_kid_path_traversal.md](jwt_kid_path_traversal.md)
- 任意 kid 值接受：接受任意 kid 而未验证其有效性，详见：[jwt_kid_validation_bypass.md](jwt_kid_validation_bypass.md)

### jku（JWK Set URL）参数攻击

#### jku 指向恶意 URL

JWT header 中的 `jku` 参数指定密钥集的 URL，攻击者可指向恶意密钥服务：

- 未验证 jku 来源导致加载恶意公钥，详见：[jwt_jku_parameter.md](jwt_jku_parameter.md)
- jku 重定向导致加载意外密钥，详见：[jwt_jku_redirect.md](jwt_jku_redirect.md)
- jku URL 可被用户控制，导致 SSRF 或恶意密钥注入，详见：[jwt_jku_injection.md](jwt_jku_injection.md)

### 密钥轮换（Key Rotation）漏洞

#### 未实现密钥轮换

应用仅使用单一密钥，密钥泄露后无法快速响应：

- 静态密钥从未更新，详见：[jwt_static_key_no_rotation.md](jwt_static_key_no_rotation.md)

#### 密钥轮换不完整

新密钥添加后旧密钥未立即失效，导致旧密钥继续可用：

- 宽限期过长（旧密钥保留过久），详见：[jwt_key_rotation_grace_period.md](jwt_key_rotation_grace_period.md)
- 旧密钥永不过期，详见：[jwt_deprecated_key_still_valid.md](jwt_deprecated_key_still_valid.md)

#### 密钥存储不安全

密钥对象在内存或文件中暴露，导致泄露：

- 密钥硬编码在源代码中，详见：[jwt_hardcoded_key_exposure.md](jwt_hardcoded_key_exposure.md)
- 配置文件中明文存储密钥，详见：[jwt_config_file_exposure.md](jwt_config_file_exposure.md)
- Java KeyStore 密码弱或未保护，详见：[jwt_keystore_weak_password.md](jwt_keystore_weak_password.md)

## JWT 声明验证绕过

### exp（过期时间）验证缺失

JWT 中的 exp 声明指定令牌过期时间，若验证不当过期令牌仍可被接受：

- 未校验 exp 声明，详见：[jwt_exp_not_checked.md](jwt_exp_not_checked.md)
- exp 校验逻辑缺陷（如整数溢出），详见：[jwt_exp_validation_bypass.md](jwt_exp_validation_bypass.md)

### iss（签发者）验证缺失

iss 声明指定令牌签发机构，未验证可接受来自任意发行者的令牌：

- 接受任意 iss 值，详见：[jwt_iss_not_validated.md](jwt_iss_not_validated.md)

### aud（受众）验证缺失

aud 声明指定令牌适用的应用，未验证导致令牌被冒用：

- 未校验 aud 声明，详见：[jwt_aud_not_checked.md](jwt_aud_not_checked.md)
- aud 值不精确，导致令牌跨应用滥用，详见：[jwt_aud_not_precise.md](jwt_aud_not_precise.md)

---

## JWT 安全审计专业技巧

### 核心审计思路

#### 1. 认证流程全链路追踪

不要仅看单一的 JWT 验证函数，需要追踪完整的令牌生命周期：

- 令牌在何处生成（签发端点、使用的密钥）
- 令牌如何存储和传输（Header、Cookie、LocalStorage）
- 令牌如何被验证（验证库、自定义逻辑）
- 令牌在何处被使用（权限检查、数据访问）

这样才能发现链路中的薄弱环节。比如密钥本身安全，但加载密钥的 JWKS 端点验证不足，仍是严重漏洞。

#### 2. 密钥管理细节检查

- 检查 JWKS 端点是否可由用户控制（参数注入、jku/kid 可控）
- 验证密钥轮换策略是否完整（旧密钥失效时间、宽限期是否合理）
- 确认密钥存储位置（环境变量、配置文件、HSM 等）是否符合安全规范

#### 3. 声明验证完整性检查

遍历所有标准声明（exp、iss、aud、nbf、jti）并检查：

- 是否显式验证（不要假设框架自动验证）
- 验证逻辑是否有缺陷（如整数溢出、时间戳精度问题）
- 自定义声明是否被验证（这是高危盲点）

---

## 真实漏洞与误报的区分经验

### 常见误报情况

#### 误报1：「密钥硬编码」但实际为示例代码

- **误报表现**：在文档、示例项目或 README 中发现硬编码密钥
- **真实判断方法**：检查是否为实际生产密钥还是 dummy 值。如果代码注释明确说明这是示例，或密钥明显为 `test123`、`secret` 等虚拟值，则为误报
- **实际漏洞特征**：生产环境代码（src/ 目录，而非 docs/ 或 examples/）中硬编码真实密钥，无任何警告注释

#### 误报2：「缺少 exp 验证」但实际使用了验证库

- **误报表现**：代码中找不到显式的 `exp` 检查
- **真实判断方法**：检查是否使用了标准 JWT 库（如 PyJWT、jsonwebtoken、jose）。大多数流行库默认验证 exp，除非显式传入 `verify_exp=False` 或 `verify: false` 选项
- **审计技巧**：搜索配置参数如 `verify_exp`、`ignoreExpiration`、`verify` 等，确认是否禁用了验证
- **实际漏洞特征**：显式禁用 exp 验证，或使用手写 JWT 解析逻辑而未验证 exp

#### 误报3：「JWKS 端点不使用 HTTPS」但实际为内网环境

- **误报表现**：JWKS URL 使用 HTTP
- **真实判断方法**：确认该应用是否运行在完全内网环境、Docker 容器网络或 Kubernetes 集群内。内网通信通常不需要 HTTPS
- **实际漏洞特征**：互联网暴露的应用或跨越不信任网络的通信使用 HTTP 获取 JWKS

#### 误报4：「kid 参数可控」但实际有白名单验证

- **误报表现**：kid 参数来自 JWT header，看起来由攻击者控制
- **真实判断方法**：检查获取密钥后是否有白名单验证。如果 kid 只能是预定义的几个值，则不存在注入风险
- **实际漏洞特征**：kid 直接用于数据库查询或文件路径构造，无白名单限制

### 常见真实漏洞特征

#### 特征1：密钥轮换策略缺陷

- 代码中旧密钥永不失效：`validKeys = currentKey`（只保留当前密钥）
- 或验证时接受所有历史密钥：`validKeys = [oldKey1, oldKey2, currentKey]` 无失效时间
- **审计建议**：确认密钥是否有明确的失效日期和通知机制

#### 特征2：自定义声明缺少验证

- 在 payload 中添加自定义声明如 `{"user_id": 123, "is_admin": true}`
- 但验证时仅检查签名，不验证 `is_admin` 的有效性
- 攻击者可能在客户端生成有效的 JWT（如果知道密钥）但修改这些声明
- **审计建议**：追踪自定义声明的生成位置和使用位置，确保被验证

#### 特征3：时间验证精度问题

- 使用秒级时间戳而被 token 使用毫秒级时间戳，导致 exp 验证失效
- 或在比较时使用了 `<=` 而不是 `<`，导致已过期的 token 仍被接受 1 秒
- **审计建议**：检查时间戳的生成和比较逻辑，确保精度一致

#### 特征4：JWKS 缓存不合理

- 缓存永不过期或过期时间过长（如 1 周）
- 导致密钥轮换后旧密钥仍被使用很久
- **审计建议**：检查缓存失效策略，推荐值为 5 分钟到 1 小时

---

## 审计检查清单

- [ ] 找到令牌签发端点，检查使用的密钥是否从安全位置加载
- [ ] 验证 JWKS 端点的 HTTPS、证书和签名验证
- [ ] 检查是否显式验证 exp、iss、aud、nbf 等标准声明
- [ ] 确认自定义声明的验证逻辑
- [ ] 检查密钥轮换策略和旧密钥失效时间
- [ ] 审计 kid 和 jku 参数的来源，检查是否可被注入
- [ ] 验证时间验证逻辑的精度和边界处理
- [ ] 如使用第三方 JWKS，检查其可靠性和更新频率
