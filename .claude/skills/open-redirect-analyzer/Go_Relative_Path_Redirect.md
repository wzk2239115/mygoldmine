# Go 相对路径重定向漏洞

相对路径重定向漏洞指应用接收用户可控的路径参数进行重定向时，虽然尝试通过相对路径限制来防止外部域名重定向，但由于验证不足，攻击者可利用路径遍历、协议相对URL、双斜杠等技巧绕过限制，实现跨域重定向。此类漏洞常见于那些仅检查URL前缀而未充分验证的代码中。

## Details

### 代码示例

```go
// 漏洞代码：虽限制相对路径，但验证不足
func RedirectHandler(w http.ResponseWriter, r *http.Request) {
    path := r.URL.Query().Get("path")

    // 不安全的验证方式
    // 1. 仅检查前缀 - 可被 //evil.com 绕过
    if !strings.HasPrefix(path, "/") {
        path = "/" + path
    }
    http.Redirect(w, r, path, http.StatusFound)

    // 2. 使用 url.Parse 但未严格检查协议 - 可被 //evil.com 绕过
    if parsed, err := url.Parse(path); err == nil && parsed.Scheme == "" {
        http.Redirect(w, r, path, http.StatusFound)
    }

    // 3. 仅检查域名但未处理特殊序列
    if !strings.Contains(path, "://") {
        http.Redirect(w, r, path, http.StatusFound)
    }
}

// 攻击示例
// GET /redirect?path=//evil.com/phishing
// GET /redirect?path=/\\evil.com
// GET /redirect?path=/../../../evil.com
// GET /redirect?path=/..%2f..%2fevil.com (URL编码绕过)
```

**快速定位到核心操作的技巧** `(L1:关键词扫描)`
- 搜索关键词：`http.Redirect()`、`w.Header().Set("Location")`、`url.Query().Get()`、`r.FormValue()`
- 重点关注：从查询参数、表单参数或其他用户输入直接进入重定向函数的代码路径，特别是那些注释中提及"相对路径"或"内部重定向"的地方
- 表现特征：重定向目标与用户可控输入在同一表达式中，且可能存在前缀检查或简单的字符串验证

**快速定位到保护机制的技巧** `(L2:跳读)`
- 检查 `http.Redirect()` 或 `w.Header().Set("Location")` 调用前的验证逻辑
- 识别验证方式的强度：
  - **弱验证模式**：仅 `strings.HasPrefix(path, "/")`、`!strings.Contains(path, "://")`、前缀检查等简单方式
  - **强验证模式**：使用 `url.Parse()` 完整解析，检查 `parsed.Scheme` 和 `parsed.Host`，必须确认为空
  - **路径格式检查**：是否使用正则表达式限制路径格式（如禁止 `//`、`../` 等特殊序列）
  - **编码处理**：是否进行了 URL 解码后再验证，或在验证后使用解码结果
- 查看是否存在通用的验证函数或中间件层的统一处理
- 重点关注验证逻辑中是否考虑了：反斜杠 `\`、双斜杠 `//`、路径遍历 `../`、URL编码绕过 `%2f` 等

## Classify

从漏洞成因分类标准：

**真实漏洞的判断依据**
- 应用尝试通过相对路径检查来防止外部重定向，但验证方式可被绕过：
  - 仅检查前缀 `strings.HasPrefix(path, "/")` 而未处理 `//evil.com` 的协议相对URL
  - 使用 `!strings.Contains(path, "://")` 而未防止 `//` 绕过
  - 使用 `url.Parse()` 解析但未严格要求 `Scheme` 和 `Host` 同时为空
  - 路径验证中未考虑 URL 编码绕过（`%2f`、`%2e` 等）或反斜杠绕过（`\` 在某些浏览器中表现如 `/`）
  - 验证通过后使用了原始输入而非验证结果
- 通过 PoC 验证：访问 `/redirect?path=//evil.com` 观察是否成功重定向至外部域名

**误报的特征**
- 重定向URL完全硬编码或从服务端配置生成，不受用户输入影响
- 虽接收路径参数但通过严格的URL解析与检查：必须验证 `url.Parse(path).Scheme == ""` 且 `url.Parse(path).Host == ""`
- 实现了路径白名单机制，用户输入只能匹配预定义的路径集合（如 `/dashboard`、`/profile` 等）
- 强制将用户输入转换为相对路径：`http.Redirect(w, r, "/"+filepath.Base(path), ...)` 确保不包含目录分隔符

**代码异味的表现**
- 存在路径验证逻辑，但验证方式过于简单（如仅前缀检查），虽未直接构成漏洞但规范性不足
- 有多个重定向点，部分进行了相对路径验证，部分完全未验证
- 使用了自定义的验证函数，但其实现方式明显存在规避空间（未全面考虑各种绕过技巧）
- 存在注释说明验证意图，但代码实现未能完全对应该意图

## Low risk

低风险情况的评级标准：

**完整的URL解析与严格检查**
- 代码使用 `url.Parse()` 对用户输入进行完整解析
- 验证 `parsedURL.Scheme` 必须为空字符串（不允许 `http`、`https`、`javascript` 等）
- 验证 `parsedURL.Host` 必须为空字符串（确保不包含域名）
- 两个条件同时满足才允许重定向，例如：`if parsedURL.Scheme != "" || parsedURL.Host != "" { http.Redirect(w, r, "/", ...) }`

**路径格式的严格限制**
- 使用正则表达式限制路径格式，如 `^/[a-zA-Z0-9/_-]+$`，禁止 `..`、`//`、反斜杠等特殊序列
- 在验证前进行 URL 编码规范化（如使用 `url.QueryEscape()` 后再对比）
- 使用 `filepath.Clean()` 消除路径中的 `..` 和冗余的 `/`，但需注意 `filepath.Clean()` 在 Windows 上的行为差异

**相对路径的强制约束**
- 代码明确拒绝任何包含协议相对URL特征的输入：`if strings.HasPrefix(path, "//") { reject }`
- 使用预定义的安全路径前缀与用户输入拼接：`safePrefix := "/app"; finalPath := safePrefix + sanitizedPath`
- 确保最终的重定向URL在编码和语义上都是相对的

**防御性的空值与异常处理**
- 用户输入为空时默认重定向至首页或安全页面，存在显式的非空检查
- 对 `url.Parse()` 的错误返回值进行处理，解析失败时拒绝重定向
- 设置 Content-Security-Policy 相关响应头来限制重定向目标（虽然这是防御深度，不是主要防护）

**跨模块验证一致性**
- 所有涉及重定向的代码点都调用同一个验证函数，确保逻辑一致
- 验证函数有明确的文档说明其检查内容，便于维护和审计
- 使用常见的 Go 重定向安全库（如社区验证过的轻量级URL验证库）而非自行实现
