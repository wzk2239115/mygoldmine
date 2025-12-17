# CSP 通配符指令漏洞（C/C++）

## Details

### 漏洞成因
CSP（Content Security Policy）通过限制资源加载来防止 XSS 攻击。使用通配符（`*`）或过度宽松的指令（如 `'unsafe-inline'`、`'unsafe-eval'`）会完全削弱 CSP 防护机制，使攻击者能够注入并执行任意脚本。

C/C++ 构建的 HTTP 服务在设置 CSP 响应头时，若未严格限制源地址，将导致防护形同虚设。常见失效场景包括：
- 使用 `script-src *` 允许任意域名脚本加载
- 使用 `script-src 'unsafe-inline'` 允许内联脚本执行
- 使用 `style-src *` 或 `style-src 'unsafe-inline'` 导致样式注入
- 使用 `img-src *` 或 `media-src *` 可被滥用进行数据窃取

### 核心定位（L1: 关键词扫描）
在 HTTP 响应头处理代码中快速定位核心操作：

**扫描目标函数或类**：
- `addHeader()`、`setHeader()`、`SetHeader()`、`append_header()` 等响应头设置接口
- 中间件类或请求处理器中包含 "Content-Security-Policy" 字符串的位置
- Nginx 配置文件中的 `add_header` 指令、Apache 的 `Header set` 指令
- HTTP 服务初始化代码中关于安全头的配置块

**快速扫描关键词**：
- `Content-Security-Policy`
- `script-src`、`style-src`、`img-src`、`media-src`、`connect-src`、`default-src`
- `*` 出现在引号内的值
- `'unsafe-inline'`、`'unsafe-eval'`、`'unsafe-hashes'`

### 保护机制验证（L2: 跳读）
跳读相关代码段，快速判断 CSP 防护强度：

**核心检查点**：
1. CSP 指令值是否为硬编码的 `*` 或 `'unsafe-inline'`
   - 若是，直接判定为漏洞
   - 若为动态生成，需进入 L3 逐行读

2. 指令值是否包含具体域名白名单
   - `script-src 'self' https://cdn.example.com` → 安全
   - `script-src https:` → 中等（协议限制）
   - `script-src *` 或 `script-src 'unsafe-inline'` → 漏洞

3. 不同页面/路由是否应用不同的 CSP 策略
   - 检查是否存在条件逻辑（if/switch/map）根据请求路径应用不同头
   - 检查是否所有路由都应用了 CSP，或存在防护缺口

4. CSP 指令间的依赖关系
   - `default-src *` 会导致所有子指令继承 `*`
   - 即使 `script-src` 明确指定，`default-src` 为 `*` 仍可能被利用

5. CSP 应用的条件
   - 检查 CSP 头是否被正确添加到响应中
   - 确认不存在条件缺失导致部分请求无 CSP 保护

## Classify

### 漏洞判定准则

**确认为漏洞的条件：**

1. **通配符指令**：CSP 指令明确使用 `*` 通配符
   - `script-src *` - 直接漏洞，允许任意脚本执行
   - `style-src *` - 允许样式注入
   - `default-src *` - 导致所有指令继承通配符

2. **不安全指令组合**：
   - `script-src 'unsafe-inline'` 或 `script-src 'unsafe-eval'` - 允许内联/动态脚本
   - `style-src 'unsafe-inline'` - 允许样式注入
   - 多指令宽松组合形成绕过（如：`script-src 'self'` 但 `frame-src *`）

3. **覆盖失效**：
   - 全局 CSP 为严格策略，但特定路由被覆盖为宽松策略
   - `default-src` 为 `*`，即使 `script-src` 明确指定也继承通配符

4. **防护缺口**：
   - CSP 仅在某些条件下应用，其他请求路径暴露于风险
   - CSP 头被条件删除或不应用于特定内容类型

5. **配置注入**：
   - CSP 使用用户输入或不可信数据构造（如 query 参数拼接）

**误报情况：**

1. **完全禁用 CSP**
   - 不存在 CSP 头设置，属于缺失漏洞而非通配符漏洞
   - 此漏洞仅针对 CSP 存在但过于宽松的情况

2. **协议级限制**
   - `script-src https:` - 限制仅允许 HTTPS，虽宽泛但比 `*` 风险显著低
   - 可评为低风险而非高危漏洞

3. **合理的兼容性方案**
   - 为支持特定浏览器或第三方库，使用 nonce 或 hash 替代 `'unsafe-inline'`
   - CSP report-only 模式下的宽松策略用于监控，不影响实际执行

4. **环境隔离**
   - 内部开发服务器确实需要宽松 CSP，但生产环境使用了严格策略
   - 需确认不存在配置误写导致生产应用了开发配置

**代码异味：**

1. 存在 `TODO` 或 `FIXME` 注释关于 CSP 配置或安全头
2. CSP 配置在多个位置重复定义，策略不一致
3. CSP 指令依赖环境变量，但未对其进行验证或白名单检查
4. 使用字符串拼接或格式化函数动态构造 CSP 值，存在注入风险
5. CSP 配置与代码逻辑强耦合，难以审计和维护

## Low risk

### 低风险评级场景

1. **协议级限制而非通配符**
   - `script-src https:` 或 `style-src https:` 限制 HTTPS 源
   - 相比 `*` 明显限制了攻击面，但仍允许任意 HTTPS 域名
   - 如果站点本身不涉及敏感操作，可接受

2. **受信任域名白名单**
   - `script-src 'self' https://cdn.trusted.com https://analytics.company.com`
   - 使用具体、可审计的域名列表，即使列表较长也比通配符安全
   - 确保列表中所有域名确实受信

3. **nonce/hash 机制替代 unsafe-inline**
   - `script-src 'nonce-random123'` 或 `script-src 'sha256-hash123'`
   - 允许特定的内联脚本，而非全部内联脚本
   - 属于合理的 CSP 实现方案

4. **数据 URI 仅用于非脚本资源**
   - `img-src data:` 或 `font-src data:` 允许内嵌资源
   - 相对 `script-src data:` 风险显著低，因不执行代码
   - 虽宽松但与通配符漏洞程度不同

5. **第三方脚本的必要妥协**
   - 某些不可避免的第三方脚本（Google Analytics、支付网关）
   - 使用特定第三方域名而非 `'unsafe-inline'` 或 `*`
   - 通过 subresource integrity 或其他验证增强防护

6. **非脚本资源的宽松策略**
   - `media-src *` 或 `img-src *` 虽宽松，但攻击面有限
   - 无法执行代码，相比 `script-src *` 风险等级应降低
   - 需评估是否存在其他利用向量（如通过 img 标签进行数据泄露）

7. **内容编辑器等特殊场景**
   - 富文本编辑器、WYSIWYG 编辑页面可能需要 `'unsafe-inline'`
   - 但应仅限于特定路由或功能，结合严格的输入验证与输出转义
   - 在 CSP report-only 模式下运行以监控违规情况

8. **兼容性临时方案**
   - 为支持老版本浏览器，可能使用相对宽松的 CSP
   - 需评估实际用户基数与安全风险的平衡
   - 应有明确的迁移计划和时间表

