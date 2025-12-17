# Java 自定义 Filter 中 CSP 规则定义不当

## Details

### 漏洞本质
自定义 CSP Filter 在定义内容安全策略时，采用过宽松的指令值（如通配符、unsafe-inline、unsafe-eval）或白名单过度允许，导致 CSP 防护形同虚设。关键风险在于虽然实现了 CSP 响应头的设置，但规则强度不足以有效阻止 XSS 攻击。

### 核心代码模式

**通常出现的形式：**
```java
// 模式1：使用通配符
response.setHeader("Content-Security-Policy", "default-src *; script-src * 'unsafe-inline'");

// 模式2：script-src 过于宽松
filter.setCSPHeader("script-src 'self' http: https:; style-src 'self' 'unsafe-inline'");

// 模式3：白名单包含不受信任的域
String cspPolicy = "script-src 'self' *.example.com; connect-src *";
response.addHeader("Content-Security-Policy", cspPolicy);

// 模式4：使用 unsafe-eval 允许动态脚本执行
response.setHeader("Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-eval'");

// 模式5：多级域名通配符
response.setHeader("Content-Security-Policy", "script-src *.com; img-src *");
```

**定位核心操作的技巧 [L1: 关键词扫描]**
- 搜索 `setHeader("Content-Security-Policy"` 和 `addHeader("Content-Security-Policy"`
- 查找 CSP 相关的 Filter 类，关键词：`CSPFilter`、`SecurityFilter`、`HeaderFilter`
- 扫描 `default-src *`、`script-src *`、`'unsafe-inline'`、`'unsafe-eval'`
- 检查 Filter 的 `doFilter()` 方法实现
- 查找白名单配置：`*.domain`、`http:` 无协议限制、`*` 通配符

**定位保护机制的技巧 [L2: 跳读]**
- 审查 CSP 策略的完整性（检查是否覆盖 script-src、style-src、img-src 等关键指令）
- 跳读 Filter 初始化部分，识别 CSP 策略是否从外部配置注入（可能支持更新）
- 检查是否存在 nonce 或 hash 机制（`script-src 'nonce-xxx'` 或 `'sha256-xxx'`）
- 验证是否使用了 report-uri 或 report-to（可能有日志记录）
- 查找是否存在 Frame-Options、X-Content-Type-Options 等补充防护

### 漏洞分类示例

**高危 CSP 配置：**
```java
// 直接使用通配符，所有资源均可任意源加载
response.setHeader("Content-Security-Policy", "default-src *");

// 允许内联脚本和动态脚本执行，等同于无防护
response.setHeader("Content-Security-Policy",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'");

// 白名单配置过宽，包含不受信任的域
filter.setCSP("script-src 'self' https: *.com");
```

**中危 CSP 配置：**
```java
// 使用单层通配符且仅限特定指令
response.setHeader("Content-Security-Policy", "script-src *");

// 包含 unsafe-inline 但未包含 unsafe-eval
response.setHeader("Content-Security-Policy",
    "script-src 'self' 'unsafe-inline'");

// 白名单包含二级域名通配符
filter.setCSP("script-src 'self' *.example.com");
```

## Classify

### 漏洞研判标准

**确认为真实漏洞的条件：**
1. **指令使用通配符** - `default-src *` 或 `script-src *` 等任何指令使用 `*` 作为源值
2. **包含 unsafe-inline + unsafe-eval** - 两者同时出现在 script-src 中
3. **过度宽松的协议声明** - `http:` 或 `https:` 作为独立值（允许所有 HTTP/HTTPS 源）
4. **不受信任的域白名单** - 添加公共域名（如 `*.com`、`*.app`、CDN 二级域名等）
5. **缺少 nonce/hash 机制** - 仅使用 `'self'` 和通配符，无动态脚本防护

**可能为误报的情况：**
- 仅在开发/测试环境使用宽松策略（但代码应通过配置区分）
- 与第三方库/广告服务联动，故意使用较宽松的 script-src（应有文档说明）
- 报告中不涉及 script-src 的限制，仅关于 img-src 或 style-src

**代码异味（需进一步审查）：**
- CSP 策略硬编码在 Filter 中，无法动态配置或更新
- 存在多个 CSP Header 设置点，可能存在覆盖或冲突
- Filter 链中的顺序不确定，可能被其他 Filter 覆盖

## Low risk

### 评级为低风险的情况

1. **仅限样式表和图片资源的宽松配置**
   - `style-src *` 和 `img-src *` 虽然宽松，但不直接导致 XSS
   - 需要结合其他漏洞（如图片上传、CSS 注入）才能造成实质伤害

2. **使用了 nonce 或 hash 机制的脚本**
   - 即使 `script-src *` 存在，若所有脚本标签都带有正确的 nonce 值
   - 示例：`<script nonce="random-value">...</script>` 配合 `script-src 'nonce-random-value'`
   - 此时通配符实际上被 nonce 约束，风险降低

3. **仅 unsafe-inline 未含 unsafe-eval**
   - `script-src 'self' 'unsafe-inline'`（无 eval）
   - 风险主要来自 DOM-based XSS，但需要已存在的 XSS 漏洞作为前提

4. **限定在特定协议 + 受信任的子域**
   - `script-src 'self' https://cdn.example.com`（example.com 为应用本身的域）
   - `script-src 'self' https://trusted-vendor.com`（审核过的第三方厂商）

5. **使用了 report-uri，具备监控机制**
   - 虽然 CSP 本身宽松，但设置了 violation 上报
   - 可能通过日志发现 XSS 尝试

6. **动态环境中的暂时性配置**
   - API 网关或 Load Balancer 级别的 CSP 设置（而非应用级别）
   - 如果是为了兼容多个后端服务的临时方案，风险评估降低
