# C/C++ CSP unsafe-inline 策略配置

## 漏洞成因

C/C++ 应用通过HTTP响应头配置CSP（内容安全策略）时，若设置了`unsafe-inline`指令，则允许页面内的内联脚本和样式执行，绕过了CSP的核心防护机制。这在Web服务器、桌面应用Web组件（如Electron）和嵌入式Web界面中均可能出现。

## Details

**核心操作代码示例：**

HTTP响应头CSP设置中包含 `script-src 'unsafe-inline'` 或 `style-src 'unsafe-inline'` 指令。

常见代码位置：
- C中：通过 `sprintf/snprintf` 构造HTTP响应头
- C++中：通过字符串拼接或HTTP库（如curl、beast）设置响应头
- 示例：`"Content-Security-Policy: script-src 'self' 'unsafe-inline'"`

**核心操作快速定位技巧** **[L1: 关键词扫描]**

搜索关键词：`unsafe-inline`、`unsafe-eval`、`Content-Security-Policy`、`"script-src"`、`"style-src"`

在HTTP响应构造代码中扫描这些关键词，确定CSP策略的设置位置。

**保护机制快速定位技巧** **[L2: 跳读]**

查找代码中是否存在：
1. **Nonce/Hash机制**：脚本标签中使用动态生成的 `nonce` 属性或内联脚本的SHA256哈希
2. **强制策略**：CSP头中显式使用 `script-src 'nonce-xxx'` 或 `script-src 'sha256-xxx'`
3. **strict-dynamic**：新型CSP指令，用于支持受信任脚本动态加载子脚本

示例对比：
```
// 脆弱：
Content-Security-Policy: script-src 'self' 'unsafe-inline'

// 受保护：
Content-Security-Policy: script-src 'self' 'nonce-a1b2c3d4'
```

## Classify

**研判为真实漏洞的条件：**

1. **存在unsafe-inline** - CSP头明确包含 `'unsafe-inline'` 关键词
2. **无对抗机制** - 不存在nonce或hash验证机制来限制哪些脚本可执行
3. **用户可控内容** - 页面存在用户可控的内容注入点（GET/POST参数、数据库字段等）且该内容在页面中以内联脚本或样式形式呈现
4. **XSS依赖性** - unsafe-inline的存在降低了XSS利用难度

**研判为误报的条件：**

1. **脚本完全不可控** - 所有脚本均由应用硬编码，无任何外部或用户输入
2. **存在严格的输入验证** - 用户输入经过严格的内容安全策略验证（如CSP框架层面的约束）
3. **上下文隔离** - 内联脚本运行在沙箱或隔离的上下文中（如iframe with sandbox属性）

**研判为代码异味的条件：**

1. **存在unsafe-eval** - 虽未直接导致漏洞但增加了攻击面
2. **过度宽松的script-src** - 如 `script-src *` 或 `script-src data:`
3. **无版本控制的第三方脚本** - 允许执行CDN上的脚本但无完整性检查

## Low risk

**以下情况应评级为低风险：**

1. **纯后端API应用** - C/C++应用仅提供JSON API，无HTML响应，CSP配置无实际意义
2. **完全服务端渲染** - 所有页面内容由服务端生成，前端无动态脚本生成逻辑
3. **CSP仅用于style-src** - `script-src` 已严格限制，仅 `style-src` 包含 `'unsafe-inline'`（CSS注入风险可控）
4. **明确的用途声明** - unsafe-inline是为支持特定框架的合理需求，且已通过其他层面防护XSS（如WAF、模板自动转义）
5. **内网应用** - 应用仅在内网运行，外部攻击面有限
