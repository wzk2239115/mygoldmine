# Python CSP 通配符来源漏洞审计指南

## Details

### 代码示例与审计定位

**易受攻击的模式：**

```python
# 示例1: Flask 中 CSP 头硬编码通配符
@app.after_request
def set_csp_header(response):
    response.headers['Content-Security-Policy'] = "script-src 'self' *"
    return response

# 示例2: Django 中配置通配符来源
SECURE_CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "script-src": ["'self'", "https://"],  # 过于宽松的协议前缀
        "style-src": ["*"],                     # 任意样式来源
        "img-src": ["*"],                       # 通配符来源
    }
}

# 示例3: 使用变量动态构造 CSP 头（未验证）
def build_csp_policy(trusted_domains):
    domains = "*".join(trusted_domains) if trusted_domains else "*"
    return f"script-src {domains}"

# 示例4: 环境配置中的通配符
CSP_HEADER = os.getenv('CSP_POLICY', 'script-src *; style-src *')
```

**快速定位核心操作** [L1: 关键词扫描]
- 扫描关键词：`script-src`、`style-src`、`img-src`、`font-src`、`connect-src`、`frame-src`、`object-src`
- 扫描通配符模式：`*`、`https://`（无域名）、`http://`（无域名）、`https://*.`（过于宽泛的子域）
- 扫描位置：
  - `Content-Security-Policy` 响应头
  - `Content-Security-Policy-Report-Only` 报告头
  - 配置文件中的 `CSP`、`SECURE_CONTENT_SECURITY_POLICY` 相关配置
  - 环境变量中的 `CSP_*` 前缀变量

**快速定位保护机制** [L2: 跳读]
- 检查 CSP 策略是否显式列出具体域名（如 `script-src https://cdn.example.com`）
- 检查是否使用了 CSP Level 3 新特性（`nonce-` 或 `hash-` 方案）而非通配符
- 检查域名限制的粒度：
  - ✓ `script-src https://cdn.example.com` (具体域)
  - ✓ `script-src https://*.example.com` (子域限制)
  - ✗ `script-src https://` (协议级通配符)
  - ✗ `script-src *` (完全通配符)
- 追踪 CSP 头生成的完整流程，确认是否存在动态构造且未经白名单验证的情况

---

## Classify

### 漏洞判定标准

**确定为漏洞的条件：**

1. **脚本执行相关指令** (`script-src`, `default-src` 包含脚本) 允许通配符源
   - 允许任意 HTTPS 源 (`https://`) 或 HTTP 源 (`http://`)
   - 包含完全通配符 (`*`)
   - 这类漏洞直接绕过 XSS 防护，风险等级最高

2. **非脚本指令但启用不安全配置** (`style-src`, `img-src`, `font-src` 等)
   - 允许通配符源且同时启用了 `style-src 'unsafe-inline'` 或 `default-src * 'unsafe-inline'`
   - 这类组合可能导致样式注入和内容伪造

3. **动态生成的 CSP 策略未进行来源白名单验证**
   - 从用户输入、查询参数、配置文件等动态构造的 CSP 头未经过严格的域名白名单检查
   - 比如 `request.args.get('domain')` 直接拼接到 CSP 头中

### 误报判定标准

**以下情况可能为误报：**

1. 仅在开发环境或测试环境中使用通配符 (需确认当前代码分支为生产环境)
2. 使用了 `Content-Security-Policy-Report-Only` 头进行监测，非强制执行
3. 通配符仅用于非敏感指令且与其他防护机制联动（见 Low risk 部分）

### 代码异味判定标准

**认定为代码异味的情况：**

- CSP 头配置清晰但存在调整空间（如可细化的子域限制）
- 使用了已弃用的 CSP 指令组合
- 缺乏 CSP 监测日志和违反上报机制

---

## Low risk

### 低风险场景

**可考虑低风险评级的情况：**

1. **纯静态资源的指令使用通配符**
   - `img-src *`、`font-src *`、`media-src *` 等仅用于不可执行资源的指令
   - 前提条件：脚本相关指令 (`script-src`, `default-src`) 必须明确限制，不允许包含通配符
   - 风险分析：攻击者无法通过这类指令执行脚本，防护重点已覆盖

2. **仅在 Content-Security-Policy-Report-Only 中使用通配符**
   - 报告模式下策略不被浏览器强制执行，仅用于监测和日志收集
   - 前提条件：生产环境必须配置严格的 `Content-Security-Policy` 强制头
   - 风险分析：浏览器不会阻止任何资源加载，但提供了违反监测的能力

3. **与其他同层防护机制联动的通配符使用**
   - 例如：`frame-src *` 配合 X-Frame-Options: DENY 头
   - 例如：`object-src *` 配合 X-Content-Type-Options: nosniff 头
   - 前提条件：必须确认多层防护机制均已生效且无绕过可能
   - 风险分析：多层防护可降低单点通配符的实际风险

4. **明确的 nonce 或 hash 机制覆盖**
   - 脚本使用严格的 nonce 或 hash 机制，通配符仅作为降级方案
   - 前提条件：nonce 生成必须使用密码学安全随机数，且每次请求更新
   - 风险分析：有效的 nonce 机制可有效限制脚本执行范围，降低通配符风险

5. **高度受限的部署场景**
   - 应用仅在内网或特定受信网络中部署（需代码注释明确说明）
   - 前提条件：内网隔离已验证，无公网暴露风险
   - 风险分析：内网场景下通配符的实际威胁降低

**重要提示：** 即使在低风险场景中，通配符的使用也应该在代码注释中明确说明业务原因和风险权衡，便于后续维护和审计。
