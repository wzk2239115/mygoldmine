# Go OAuth 回调处理中 redirect_uri 未验证漏洞

OAuth 授权流程中，授权服务器应严格验证 `redirect_uri` 参数，确保其与预先注册的重定向URI完全一致。当应用在处理 OAuth 回调时未进行有效验证，攻击者可利用此漏洞伪造授权码或访问令牌，将用户重定向至恶意网站进行钓鱼、凭证窃取或恶意内容注入。

## Details

### 代码示例

```go
// 漏洞代码：OAuth授权端点未验证redirect_uri
func AuthorizeHandler(w http.ResponseWriter, r *http.Request) {
    clientID := r.URL.Query().Get("client_id")
    redirectURI := r.URL.Query().Get("redirect_uri")
    scope := r.URL.Query().Get("scope")

    // 仅检查client_id是否存在，未验证redirect_uri
    if client, exists := registeredClients[clientID]; exists {
        // 生成授权码，不验证redirect_uri是否与注册时一致
        authCode := generateAuthCode()

        // 直接使用用户提供的redirect_uri
        redirectURL := fmt.Sprintf("%s?code=%s&state=%s",
            redirectURI, authCode, r.URL.Query().Get("state"))
        http.Redirect(w, r, redirectURL, http.StatusFound)
        return
    }

    http.Error(w, "Invalid client_id", http.StatusBadRequest)
}

// 危险的令牌端点
func TokenHandler(w http.ResponseWriter, r *http.Request) {
    clientID := r.FormValue("client_id")
    code := r.FormValue("code")
    redirectURI := r.FormValue("redirect_uri")

    // 虽然验证了code，但未检查redirect_uri是否与授权时一致
    if validateAuthCode(code, clientID) {
        token := generateAccessToken(clientID)
        // 返回访问令牌，攻击者用伪造的redirect_uri获得授权码后可兑换令牌
        json.NewEncoder(w).Encode(map[string]string{
            "access_token": token,
            "token_type":   "Bearer",
        })
        return
    }
}

// 调用示例
// 正常流程：GET /authorize?client_id=app1&redirect_uri=https://app.example.com/callback&state=xyz
// 攻击流程：GET /authorize?client_id=app1&redirect_uri=https://attacker.com/steal&state=xyz
```

**快速定位到核心操作的技巧** `(L1:关键词扫描)`
- 搜索关键词：`redirect_uri`、`r.URL.Query().Get()`、`r.FormValue()`、`http.Redirect()`
- 定位OAuth授权端点：查找处理 `/authorize`、`/oauth/authorize`、`/oauth2/authorize` 的处理函数
- 定位令牌交换端点：查找处理 `/token`、`/oauth/token`、`/oauth2/token` 的处理函数
- 识别关键模式：`redirect_uri` 参数的接收、使用和重定向操作在代码中的相邻位置
- 追踪数据流：从Query参数到http.Redirect调用之间是否存在验证步骤

**快速定位到保护机制的技巧** `(L2:跳读)`
- 检查授权端点中 `redirect_uri` 前的验证调用：
  - 查找 `registeredURIs[clientID]` 或类似的白名单查表操作
  - 搜索 `strings.HasPrefix(redirectURI, expected)` 或 `redirectURI == expected` 的比对语句
  - 识别 `url.Parse()` 的使用及其结果对 Host/Path 的检查
- 检查令牌端点中的 `redirect_uri` 一致性验证：
  - 查找将授权请求中的 `redirect_uri` 与令牌请求中的 `redirect_uri` 进行比对的代码
  - 确认验证前未使用原始的用户输入参数
  - 跳读验证函数逻辑，关注是否正确处理URL解析、编码和子域名匹配
- 检查是否存在授权码与redirect_uri的绑定机制：
  - 查找授权码生成时是否记录了对应的redirect_uri
  - 验证令牌兑换时是否强制要求redirect_uri匹配

## Classify

### ✅ 确认漏洞

**漏洞的判断依据**
- 授权端点完全不验证 `redirect_uri`，直接使用查询参数进行重定向，或仅检查client_id存在性
- 授权端点验证存在但存在绕过：
  - 仅检查 URL 前缀（如 `strings.HasPrefix(redirectURI, allowedDomain)`），未防止 `https://allowed.com.attacker.com` 的子域绕过
  - 使用 `strings.Contains()` 进行域名检查而非完整的 `url.Parse()` + `Host` 字段验证
  - 未考虑URL编码绕过（如 `%2e%2e` 表示 `..`）
  - 允许协议相对URL（`//attacker.com`），而预注册时使用完整URL
- 令牌端点未验证 `redirect_uri` 与授权请求时的 `redirect_uri` 一致性
- 授权码与redirect_uri无绑定关系，攻击者可用任意 redirect_uri 兑换授权码生成的令牌
- 验证函数存在但在生成授权码或令牌前仍使用原始未验证输入

**具体攻击场景**
- 授权码拦截：攻击者诱导用户访问 `/authorize?client_id=app&redirect_uri=attacker.com`，授权码直接泄露到attacker.com
- 令牌兑换：授权码本身无法被直接利用，但若令牌端点未验证redirect_uri一致性，攻击者可用自己的redirect_uri兑换
- 凭证收集：用户在attacker.com重定向页面输入凭证认为进行二次验证，实际是钓鱼页面

### ⚠️ 代码异味

- OAuth流程中存在redirect_uri验证逻辑，但仅对特定端点验证，其他端点缺失
- 验证函数存在但与业务逻辑的关联不清晰，维护者难以理解保护机制
- 使用过时的验证方式（如简单字符串前缀匹配），虽未成为漏洞但不符合OAuth规范最佳实践
- 存在多个授权流程分支，部分验证完整，部分验证不完整
- 授权码生成时未将redirect_uri信息记录，令牌端点无法进行一致性检查

### ❌ 误报

- `redirect_uri` 完全硬编码于服务端配置中，不从用户输入接收
- 授权端点在生成授权码前对 `redirect_uri` 进行了完整的白名单验证，验证失败时拒绝请求
- 令牌端点在兑换令牌前严格验证了 `redirect_uri` 与授权请求时的值完全一致，使用了 `==` 精确比较而非模式匹配
- 使用成熟的OAuth库（如 `golang.org/x/oauth2` 的服务端实现），库已内置redirect_uri验证

## Low risk

低风险情况的评级标准：

**完整的redirect_uri白名单验证**
- 代码在授权端点明确检查 `redirect_uri` 是否在预注册的白名单中，例如：
  ```go
  allowedURIs := registeredClients[clientID].RedirectURIs
  if !contains(allowedURIs, redirectURI) {
      http.Error(w, "Invalid redirect_uri", http.StatusBadRequest)
      return
  }
  ```
- 使用URL解析进行精确比较：`url.Parse()` 解析后比对 `Host` 和 `Path`，而非简单字符串前缀匹配
- 子域名处理正确（白名单中明确列举所有允许的重定向URI，不使用通配符）

**授权码与redirect_uri的强制绑定**
- 授权码生成时必须记录对应的 `redirect_uri` 和 `client_id`，例如：
  ```go
  authCodes[code] = AuthCodeData{
      ClientID:    clientID,
      RedirectURI: redirectURI,
      ExpiresAt:   time.Now().Add(10 * time.Minute),
  }
  ```
- 令牌端点兑换时强制验证 `redirect_uri` 与授权时一致：
  ```go
  codeData := authCodes[code]
  if codeData.RedirectURI != redirectURI {
      http.Error(w, "Redirect URI mismatch", http.StatusBadRequest)
      return
  }
  ```

**规范的OAuth流程实现**
- 授权端点生成授权码后，重定向时使用预注册的verified redirect_uri而非用户输入
- 令牌端点要求 `redirect_uri` 参数，并与授权请求时的值进行逐字符比较
- 授权码具有短期有效期（通常10分钟），且仅可使用一次

**框架级安全特性**
- 使用成熟的Go OAuth库或框架（如 `ory/hydra`、`oauth2-proxy`），已包含经过验证的redirect_uri检查逻辑
- 在中间件或统一的验证层实现redirect_uri检查，所有OAuth端点均通过此层处理
- 验证函数包含详细代码注释，明确说明RFC 6749规范要求和实现细节
