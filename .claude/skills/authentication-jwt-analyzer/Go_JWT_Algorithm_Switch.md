# Go JWT 算法切换漏洞

## 漏洞成因
使用 jwt-go、golang-jwt 等库时，未正确验证 JWT Header 中的 `alg` 字段，允许客户端控制签名算法，导致算法降级攻击（如 HS256→none、RS256→HS256）。

## Details

### 代码示例
```go
// 易受攻击的代码
token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
    // 未验证算法类型，直接返回密钥
    return secretKey, nil
})

// 或使用 ParseWithClaims
token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
    return []byte(secret), nil
})
```

### 快速定位核心操作（L2:跳读）
**关键函数：** `jwt.Parse`、`jwt.ParseWithClaims`、`jwt.ParseWithoutValidation`
- 直接跳转到 JWT 解析入口
- 检查 `KeyFunc` 回调函数内部是否存在算法验证
- 重点关注 `token.Method` 和 `token.Header["alg"]` 是否被检查

### 快速定位保护机制（L3:逐行读）
**防御模式识别：**
- 在 `KeyFunc` 中是否有 `token.Method.Alg() != "RS256"` 等显式算法检查
- 是否使用 `jwt.NewParser(jwt.WithValidMethods([]string{"RS256"}))` 白名单配置
- 是否断言 `token.Method` 为特定类型（如 `*jwt.SigningMethodRSA`）

**审计路径：**
1. 搜索所有 JWT 解析函数调用点
2. 逐行检查 KeyFunc 实现，确认算法类型断言
3. 若算法验证在其他函数中，需跨模块追踪（升级为 L4）

## Classify

### 漏洞判定
**确认为漏洞：** KeyFunc 完全未验证 `token.Method`，或仅检查算法名称字符串但可被绕过（如空字符串判断缺陷）

**误报场景：**
- 已在 KeyFunc 中使用类型断言验证算法（如 `_, ok := token.Method.(*jwt.SigningMethodRSA)`）
- 使用最新版本库的 `WithValidMethods` 选项显式限制算法
- Token 来源完全可信（内部生成且不经过网络传输）

**代码异味：**
- 算法验证存在但逻辑冗余或不清晰
- 使用已弃用的 API（如 `jwt-go` v3）但存在防御

## Low Risk

### 低风险评级条件
- JWT 仅用于非敏感场景（如临时 session token，失效时间极短 <5min）
- 应用架构中存在多层验证（JWT 仅作为第一道检查，后续有数据库权限二次验证）
- 攻击面受限：Token 生成与验证在同一内部服务，无外部输入
- 已有 WAF/API Gateway 层面对 `alg:none` 等异常 Token 进行拦截

## 审计专业技巧

### 1. 算法降级攻击识别（HS256→RS256）

#### 真实漏洞特征
- **RS256 私钥泄露**：调用方在 KeyFunc 接受公钥后，攻击者通过改为 HS256 + 公钥作为密钥签名，绕过签名验证
  ```go
  // 易受攻击：未验证 alg 类型
  token, _ := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
      // 攻击者修改 Header 为 HS256，用公钥签名
      return publicKeyBytes, nil  // 公钥被当作 HMAC 密钥
  })
  ```

- **关键判断点**：KeyFunc 是否返回的密钥在 HS256 + RS256 下都可被验证

#### 防御对比
```go
// 正确的防御方式 - 算法类型断言
token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
    // 必须先检查算法类型，再返回对应密钥
    if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
        return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
    }
    return publicKey, nil
})

// 或使用 jwt-go v4.0+ 的白名单模式
parser := jwt.NewParser(jwt.WithValidMethods([]string{"RS256"}))
token, err := parser.ParseWithClaims(tokenString, &Claims{}, keyFunc)
```

### 2. 真实漏洞 vs 误报的关键区分

#### 误报场景一：已正确使用类型断言
```go
// 这不是漏洞 - 已进行算法验证
token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
    // ✓ 明确检查算法类型
    rsaMethod, ok := token.Method.(*jwt.SigningMethodRSA)
    if !ok {
        return nil, errors.New("invalid signing method")
    }
    return publicKey, nil
})
```

#### 误报场景二：在外层进行了检查
```go
// 外层已验证，内层 KeyFunc 本身不存在漏洞
func ValidateToken(tokenString string) (*Claims, error) {
    // ✓ 在调用前验证算法
    unverified, _ := jwt.ParseWithoutValidation(tokenString)
    if unverified.Method.Alg() != "RS256" {
        return nil, errors.New("invalid algorithm")
    }

    return jwt.ParseWithClaims(tokenString, &Claims{}, keyFunc)
}
```

#### 真实漏洞场景：RS256 上下文中混用 HS256
```go
// ✗ 真实漏洞 - 没有算法检查
func keyFunc(token *jwt.Token) (interface{}, error) {
    return publicKey, nil  // 公钥直接返回，无类型检查
}

// 攻击者可以：
// 1. 用公钥作为 HMAC 密钥签名
// 2. 修改 Header 中 alg 为 HS256
// 3. 解析时 KeyFunc 返回同一公钥，验证成功
```

### 3. 审计检查清单

| 检查项目 | 真实漏洞表现 | 正常防御表现 |
|---------|-----------|-----------|
| 算法类型检查 | `token.Method` 未被检查或为 interface{} | 类型断言为具体类型（RSA/ECDSA/HMAC） |
| 算法白名单 | KeyFunc 无白名单机制 | `WithValidMethods` 或显式判断 `alg` |
| 密钥返回逻辑 | 对所有算法返回同一密钥 | 根据算法类型返回不同密钥 |
| 库版本 | jwt-go v3（已停维）| golang-jwt v4.0+（活跃维护） |
| 解析配置 | 使用 `jwt.Parse` 默认参数 | 使用 `jwt.NewParser` 显式配置 |

### 4. 审计工程化方法

#### 第一步：快速过滤（低代价）
```bash
# 搜索所有 JWT 解析点
grep -r "jwt.Parse\|jwt.ParseWithClaims" --include="*.go"

# 搜索已知防御模式
grep -r "WithValidMethods\|SigningMethodRSA" --include="*.go"
```

#### 第二步：上下文分析（中代价）
- 对于每个 Parse 调用，追踪 KeyFunc 实现
- 检查 KeyFunc 是否存在分支逻辑（if-else 判断 alg）
- 若无分支，直接返回密钥 → **可能是漏洞**

#### 第三步：确认漏洞可利用性（高代价）
- 获取应用使用的公钥/密钥
- 构造混杂算法的 Token（RS256 上下文改为 HS256）
- 尝试验证：若成功 → **确认漏洞**

### 5. 实战经验

#### 高频误报原因
1. **跨文件检查不彻底**：KeyFunc 看似无检查，但在调用处有宏观验证
2. **旧版本库的新理解**：jwt-go v3 虽无 WithValidMethods，但代码中手工实现了算法限制
3. **配置层防御**：中间件或全局拦截器拒绝非预期算法的 Token

#### 高确信度的真实漏洞特征
- KeyFunc 无任何分支逻辑，直接返回 `publicKey` 或 `secretKey`
- 跨文件检查也找不到算法验证逻辑
- 库为 jwt-go v3（已知无 WithValidMethods）且无手工算法检查
- 测试：用公钥签名 HS256 Token，能被成功验证