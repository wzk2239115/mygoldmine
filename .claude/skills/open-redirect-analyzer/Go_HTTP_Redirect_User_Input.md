## Go HTTP 重定向用户输入审计指南

---

### Details

#### 漏洞触发点

Go 标准库提供了 `http.Redirect()` 函数用于 HTTP 重定向，其函数签名为：
```go
func Redirect(w http.ResponseWriter, r *http.Request, url string, code int)
```

**核心风险**：该函数直接使用传入的 `url` 参数写入 `Location` 响应头，不对 URL 有效性和目标域名进行任何验证。攻击者可通过控制重定向目标参数，将用户引导至恶意网站进行钓鱼、凭证窃取或恶意软件分发。

---

#### 快速定位核心操作 **[L1: 关键词扫描]**

在 Go 项目中快速定位重定向代码：

**重定向函数及其变体**
- `http.Redirect(w, r, url, code)` - 标准库直接重定向
- `w.Header().Set("Location", url)` - 手动设置 Location 响应头
- `w.Header().Add("Location", url)` - 追加 Location 响应头
- `http.StatusFound`、`http.StatusMovedPermanently`、`http.StatusTemporaryRedirect` 等状态码作为第四参数

**搜索关键词**：
- `http.Redirect`
- `"Location"`（注意引号，区分注释）
- `StatusFound`、`StatusMovedPermanently`、`StatusTemporaryRedirect`
- `w.Header().Set`、`w.Header().Add` 跟随 Location 字段

**典型危险代码模式**
```go
// 直接从请求参数获取重定向 URL
redirectURL := r.URL.Query().Get("redirect_to")
http.Redirect(w, r, redirectURL, http.StatusFound)

// 从表单参数获取
url := r.FormValue("url")
http.Redirect(w, r, url, http.StatusMovedPermanently)

// 手动设置 Location 头
nextURL := r.URL.Query().Get("next")
w.Header().Set("Location", nextURL)
w.WriteHeader(http.StatusFound)
```

---

#### 快速定位保护机制 **[L2-L4: 跳读/逐行读/跨模块追踪]**

**第一阶段**（L2：跳读）：查看重定向语句周围 3-5 行代码
- 检查是否有 `url.Parse()` 验证
- 检查是否调用了白名单检查函数
- 检查是否有 `strings.HasPrefix()` 或 `strings.Contains()` 等字符串验证

**第二阶段**（L3：逐行读）：完整阅读重定向相关函数
- 检查重定向参数的来源（Query、Form、Body、Header）
- 识别参数是否经过任何转换或验证
- 检查是否使用了 `net/url` 包中的 URL 解析和验证

**第三阶段**（L4：跨模块追踪）：追踪参数来源到最终使用
- 参数在传递给 `http.Redirect()` 前是否经过验证函数
- 验证函数是否正确实现了白名单或域名检查
- 检查是否存在绕过白名单的边界情况（编码、协议相对 URL 等）

**关键防护方案的检查清单**

| 防护机制 | 检查要点 | 审计等级 |
|---------|---------|---------|
| **白名单验证** | 重定向目标是否精确匹配预定义列表 | L2 |
| **URL 解析** | 是否使用 `url.Parse()` 并检查 URL 结构 | L2 |
| **协议限制** | 是否验证 `u.Scheme` 仅为 http/https | L3 |
| **域名检查** | 是否验证 `u.Host` 属于可信域名 | L3 |
| **路径限制** | 是否仅允许相对路径重定向 | L2 |
| **编码处理** | 参数是否会被自动编码/解码 | L3 |
| **完整链路追踪** | 重定向参数从入口到使用的完整流程 | L4 |

**安全代码示例（用于对比）**
```go
// 正确的实现方式
func safeRedirect(w http.ResponseWriter, r *http.Request) {
    redirectURL := r.URL.Query().Get("redirect_to")

    // 白名单验证
    allowedHosts := []string{"example.com", "trusted.example.com"}
    u, err := url.Parse(redirectURL)
    if err != nil {
        http.Error(w, "Invalid URL", http.StatusBadRequest)
        return
    }

    // 检查协议和域名
    if u.Scheme != "http" && u.Scheme != "https" {
        http.Error(w, "Invalid scheme", http.StatusBadRequest)
        return
    }

    allowed := false
    for _, host := range allowedHosts {
        if u.Host == host {
            allowed = true
            break
        }
    }

    if !allowed {
        http.Error(w, "Redirect not allowed", http.StatusBadRequest)
        return
    }

    http.Redirect(w, r, redirectURL, http.StatusFound)
}
```

---

### Classify

#### 如何研判漏洞/误报/代码异味

**确认为真实漏洞（High/Critical）**

1. **确定参数可控性**：重定向 URL 直接来自用户输入（Query、Form、JSON 等），未经过转换或加密
2. **无有效防护**：
   - 不存在 URL 白名单验证
   - 不存在协议和域名检查
   - 仅有黑名单过滤（可被绕过）
3. **完整利用链**：用户可重定向到任意外部网站（通过 http://attacker.com、//attacker.com 等形式）
4. **实际威胁**：应用场景涉及身份验证、支付、权限变更等关键功能

**判定为误报（False Positive）**

满足以下任何一条：
1. **严格白名单**：重定向目标必须精确匹配白名单中的预定义 URL，不支持用户自定义参数
2. **相对路径限制**：应用仅支持相对路径（如 `/dashboard`），不允许绝对 URL 或协议前缀
3. **完整 URL 验证**：通过 `url.Parse()` 解析后，严格验证了协议（仅 http/https）和域名（本域或可信域名列表）
4. **防御深度**：即使成功重定向，目标网站本身也具有防御能力（不会泄露敏感信息）

**代码异味（Code Smell）**

- 存在注释提示"TODO: add URL validation"但未实现
- 存在错误实现的验证函数（如只检查前缀、不检查协议等）
- 使用黑名单方式过滤"malicious"等字符串
- 多个重定向点，部分有保护，部分没有（不一致的防护）

---

### Low risk

#### 以下情况应给予低风险评级

1. **完整的精确白名单**
   - 重定向目标被限制在明确定义的 URL 列表中
   - 使用精确字符串匹配（例如 `u.String() == whitelist[i]`）
   - 不允许用户参数化或自定义重定向目标

2. **相对路径隔离**
   - 应用明确检查重定向目标是否为相对路径
   - 检查方式：`!strings.HasPrefix(url, "http://") && !strings.HasPrefix(url, "https://") && !strings.HasPrefix(url, "//")`
   - 相对路径自动解析为本应用域名下的路径

3. **严格的协议和域名验证**
   - 使用 `url.Parse()` 解析重定向 URL
   - 验证 `u.Scheme` 仅为 "http" 或 "https"
   - 验证 `u.Host` 属于本域或预定义的可信域名列表（如公司自有的多个域名）
   - 不接受 IP 地址、IPv6 地址或特殊格式的重定向

4. **上下文特定的低风险场景**
   - 重定向用于内部系统之间的跳转（如微服务间调用），用户无法直接控制参数
   - 重定向目标是从数据库中查询的（且数据库中的 URL 由管理员维护）
   - 重定向仅用于错误提示页面或日志页面等无关键信息的场景

5. **多层防御**
   - 即使应用本身未严格验证，但由于部署在防火墙、WAF 或 API 网关后，恶意重定向被阻止
   - 检查企业环保策略文档中的防护说明

---
