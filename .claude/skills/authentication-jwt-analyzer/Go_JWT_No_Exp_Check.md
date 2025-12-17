# Go JWT 未校验过期时间 (No Exp Check)

## Details

### 代码示例

```go
// 漏洞示例：解析 JWT 但未校验 exp
token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
    return []byte(secretKey), nil
})
// 仅检查签名有效，不检查过期时间
if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
    userID := claims["user_id"]
    // 直接使用，允许过期令牌
}

// 漏洞示例：自定义声明但禁用 exp 验证
claims := jwt.MapClaims{}
token, _ := jwt.ParseWithClaims(tokenString, claims, keyFunc)
// 未设置 WithExpirationRequired() 或手动验证 exp
```

### 快速定位核心操作（L2:跳读）

**关键函数定位：**
- `jwt.Parse()` / `jwt.ParseWithClaims()` - JWT 解析入口
- `token.Claims` 访问 - 提取声明数据点
- 中间件/拦截器中的 token 验证逻辑

**快速审计路径：**
1. 搜索 `jwt.Parse` 定位解析点（L1:关键词扫描）
2. 检查是否访问 `claims["exp"]` 或使用 `VerifyExpiresAt()`（L2:跳读）
3. 确认是否设置 `jwt.WithValidMethods()` 但遗漏时间验证（L2:跳读）

### 快速定位保护机制（L3:逐行读）

**有效防护特征：**
- 使用 `jwt.NewParser(jwt.WithExpirationRequired())` 强制 exp 存在
- 调用 `claims.VerifyExpiresAt(time.Now().Unix(), true)` 显式校验
- 使用 `jwt.StandardClaims` 或 `jwt.RegisteredClaims` 且启用默认验证
- 第三方库如 `golang-jwt/jwt/v5` 默认验证行为

**审计检查点：**
1. 验证 `Parser` 配置是否包含 `WithExpirationRequired()`（L3:逐行读）
2. 确认 `token.Valid` 判断前是否已启用时间验证（L3:逐行读）
3. 自定义 Claims 结构体是否实现并调用 `Valid()` 方法（L4:跨模块追踪）

## Classify

**漏洞判定标准：**
- JWT 解析后直接使用 claims 数据进行身份认证或授权决策，且未验证 `exp` 字段
- 服务端接受已过期 token 执行敏感操作（如修改用户数据、权限提升）
- 可通过重放过期 token 绕过登录时效限制

**误报排除条件：**
- Token 仅用于无状态数据传输，不涉及身份认证（如公开 API 参数传递）
- 业务层额外实现了基于 Redis/DB 的 token 黑名单或时效管理
- 使用短期 token + refresh token 机制且过期后强制重新认证

**代码异味识别：**
- 注释显示"临时禁用过期检查用于测试"但存在于生产代码
- 混用多个 JWT 库导致验证逻辑不一致
- 过期时间设置过长（如 >7 天）降低时效性防护效果

## Low risk

**低风险场景：**
1. **仅内部服务调用**：JWT 用于内网服务间短期通信（<5 分钟），且有其他安全边界保护
2. **只读操作**：Token 仅授权查询公开数据，不涉及状态变更或敏感信息访问
3. **双因素验证兜底**：即使接受过期 token，后续敏感操作仍需二次验证（如 OTP、密码确认）
4. **有效期极短**：Token 过期时间 ≤ 60 秒，攻击窗口期极小
5. **补偿性控制**：已实现速率限制、IP 白名单、设备指纹等额外防护层，可降低过期 token 滥用风险

## 审计专业技巧

### 真实漏洞的核心特征识别

**漏洞触发的必要条件：**
1. **exp 字段完全缺失或未验证**：不仅未检查，连声明都没有定义
   - 真漏洞：`token.Claims.(jwt.MapClaims)` 直接使用，无 `VerifyExpiresAt()` 调用
   - 误报：使用了 `jwt.RegisteredClaims` 结构体且调用了标准库验证方法

2. **验证跳过存在明确代码证据**：
   ```go
   // 真漏洞标志
   parser := jwt.NewParser()  // 无 WithExpirationRequired()
   parser := jwt.NewParser(jwt.WithValidMethods("HS256"))  // 只验证方法，未验证时间

   // 误报排除
   parser := jwt.NewParser(jwt.WithExpirationRequired())  // 启用强制验证
   ```

3. **自定义 Claims 结构体的 Valid() 方法缺陷**：
   ```go
   // 真漏洞：Valid() 方法不检查 exp
   type CustomClaims struct {
       UserID string
       jwt.RegisteredClaims
   }
   func (c CustomClaims) Valid() error {
       return nil  // 空实现，忽略过期检查
   }

   // 安全：调用父类验证或手动检查
   func (c CustomClaims) Valid() error {
       return c.RegisteredClaims.Valid()  // 委托给标准实现
   }
   ```

### 误报常见模式及排除方法

**模式 1：库版本升级导致的虚假告警**
- 表现：旧代码 `jwt.Parse()` 在 `golang-jwt/jwt/v4` 不验证，升级到 `v5` 后自动验证
- 排除方法：检查 go.mod 中库版本和发布时间，确认代码修改时点早于库默认行为变更
- 案例分析：v5 版本默认启用 `WithExpirationRequired()`，许多"历史漏洞"自动修复

**模式 2：多层验证导致的遗漏检测**
- 表现：应用层未验证，但中间件/网关层已验证
  ```go
  // 应用层代码看似无验证
  claims := token.Claims.(jwt.MapClaims)

  // 但在路由注册时已添加验证中间件
  router.Use(JWTMiddleware(verifyExpiration: true))
  ```
- 排除方法：追踪 token 从 HTTP 请求到业务逻辑的完整流程，检查所有验证点

**模式 3：条件判断隐藏的验证逻辑**
- 表现：无显式 exp 检查，但通过其他条件排除过期 token
  ```go
  claims := token.Claims.(jwt.MapClaims)
  exp := int64(claims["exp"].(float64))

  // 条件判断等价于验证
  if exp > time.Now().Unix() {
      // 使用 token
  }
  ```
- 排除方法：识别任何与当前时间的时间戳比较，即使不使用标准库方法也算验证

**模式 4：业务逻辑中的二次验证**
- 表现：基础 JWT 解析无验证，但业务层有防御
  ```go
  claims := token.Claims.(jwt.MapClaims)
  userID := claims["user_id"].(string)

  // 业务层再次校验
  user := db.GetUserByID(userID)
  if user.TokenExpiredAt < time.Now() {
      return ErrTokenExpired
  }
  ```
- 排除方法：评估二次验证的可靠性和覆盖率，可能仍存在某些路径绕过风险

### 真实漏洞与误报的上下文判断

**问卷检查清单：**

1. **Token 用途判断**
   - 问：Token 是否用于身份认证或授权决策？
   - 是 → 缺少 exp 验证是高风险 | 否 → 评估为低风险

2. **过期时间设置**
   - 问：exp 值是否被设置（非 0 非空字符串）？
   - 否 → 真漏洞（业务意图存在但验证缺失）
   - 是但值为极大值（如 2100 年） → 实质漏洞

3. **访问控制作用域**
   - 问：该 token 能访问的资源/操作是否涉及用户私密数据或状态变更？
   - 是 → 按高风险处理 | 否 → 考虑降级为低风险

4. **验证点追踪**
   - 问：在 token 被真正使用的位置（而非解析位置）前是否验证过期？
   - 是 → 误报 | 否 → 真漏洞

### 审计时常见的陷阱

**陷阱 1：只检查解析代码而忽视验证配置**
- 错误做法：看到 `jwt.Parse()` 就判定为漏洞
- 正确做法：追踪 Parser 对象的创建和配置，查看完整的 NewParser() 调用链

**陷阱 2：混淆 token.Valid 与 exp 验证**
- token.Valid 仅检查签名有效性，不验证过期时间
- 必须显式检查 exp 字段或使用带 exp 验证的 Parser 配置

**陷阱 3：假设标准库默认行为**
- golang-jwt/jwt 库不同版本行为不同，需核实项目使用的具体版本
- 某些 fork 或修改版本可能有不同的默认行为

**陷阱 4：忽视时区和时间同步问题**
- exp 验证依赖服务器时钟准确，时钟偏差可导致令牌提前过期或延期有效
- 检查服务器是否启用 NTP 同步

### 实战审计流程

**Step 1：确认 Token 生命周期**
- 搜索 `jwt.Sign()` / `NewWithClaims()` 查看 exp 值如何设置
- 确认是否设置了有意义的过期时间

**Step 2：追踪验证点**
- 从 HTTP 入口（如中间件）开始，追踪 token 的验证位置
- 列出所有 `jwt.Parse*()` 的调用点和配置

**Step 3：验证逻辑分析**
- 检查每个解析点的验证配置
- 确认是否存在多个解析路径且验证不一致

**Step 4：权限评估**
- 分析该 token 能否在过期后仍执行敏感操作
- 考虑 token 重放场景的可能性

**Step 5：上下文确认**
- 查看业务文档了解 token 预期生命周期
- 检查是否有明确的业务需求说明为什么不验证过期时间