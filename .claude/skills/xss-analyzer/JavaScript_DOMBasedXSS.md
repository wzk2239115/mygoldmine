# JavaScript DOM-based XSS

## 基本信息

- **难度等级：** ★★★★☆ (中高级)
- **审计时间：** 25-45分钟（单个漏洞点）
- **先决知识：** JavaScript 事件循环、DOM API、URL 参数解析、DOMPurify 使用
- **复杂度评估：**
  - 简单场景（单点直接赋值）：15-20分钟
  - 复杂场景（多源合成、跨文件链路）：45-60分钟

## 🚀 30秒快速清单

- [ ] 代码中是否使用了 `innerHTML`、`outerHTML`、`document.write` 等危险 API？
- [ ] 这些 API 的值是否来自 URL 参数、Storage、postMessage 等外部来源？
- [ ] 在赋值前是否使用了 DOMPurify 或其他净化库进行处理？
- [ ] 是否使用了安全的替代方案（如 `textContent`）？
- [ ] 是否跨越多个文件或涉及复杂的数据流转链路？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
在前端代码中直接使用 `innerHTML`、`outerHTML`、`document.write`、`insertAdjacentHTML` 等 API 将用户可控字符串插入 DOM，会触发 DOM-based XSS。攻击者可以通过 URL 参数、WebSocket 消息、postMessage、localStorage 等渠道注入脚本片段，最终在受害者浏览器执行恶意 JavaScript。

### 代码示例

**易受攻击的代码：**
```javascript
const message = new URLSearchParams(window.location.search).get('msg');
if (message) {
  document.getElementById('banner').innerHTML = `<p>${message}</p>`;
}
```

**安全示例：**
```javascript
const message = new URLSearchParams(window.location.search).get('msg');
if (message) {
  document.getElementById('banner').textContent = message;
}
// 或使用 DOMPurify 等库对受信内容净化
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `innerHTML`, `outerHTML`, `document.write`, `insertAdjacentHTML`, `dangerouslySetInnerHTML`, `new Function`, `eval`。

**定位步骤：**
1. 全局搜索上述 API；
2. 跳读（L2）确认传入的字符串是否来自用户输入；
3. 关注 URL 参数、Hash、Storage、接口响应是否直接拼接。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `textContent`、`innerText`、`createTextNode`；
- 采用 DOMPurify、sanitize-html 等净化库；
- 框架模板自动转义（如 Vue mustache、React JSX）；
- CSP 策略限制内联脚本。

**定位技巧：**
- 逐行读（L3）确认在插入前是否净化或验证输入；
- 跨模块追踪（L4）输入来源链路，如 URL → Router → 组件渲染。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 仅使用 `textContent`/框架默认转义 | **L0（快速跳过）** | 无风险 |
| 使用 `innerHTML` 但经过可信净化 | **L2（跳读）** | 核实净化策略 |
| 直接将用户输入写入 HTML | **L3（逐行读）** | 高风险 |
| 输入链路复杂跨多模块 | **L4（跨模块追踪）** | 需完整分析 |

## 🚨 陷阱识别 - 看起来安全但有风险

### 陷阱 1：DOMPurify 配置过于宽松

**现象：**
```javascript
const userContent = getURLParameter('content');
const clean = DOMPurify.sanitize(userContent, {
  ALLOWED_TAGS: ['div', 'span', 'a', 'img'],
  ALLOWED_ATTR: ['href', 'src'],
});
document.getElementById('preview').innerHTML = clean;
```

**看起来安全，但如果：**
- 白名单中允许了 `<a>` 且允许 `href` 属性，可能被注入 `javascript:` 协议
- 白名单中允许了 `<img>` 且 `onerror` 没有被明确禁用，可能被注入事件处理器
- 配置中没有 `ALLOWED_URI_REGEXP` 限制，`href="javascript:alert(1)"` 可能通过

**定位技巧：**
1. 搜索所有 `DOMPurify.sanitize` 调用
2. 检查每个调用的第二参数（配置对象）
3. 特别关注 `ALLOWED_TAGS`、`ALLOWED_ATTR`、`ALLOWED_URI_REGEXP` 的配置

**研判方法：**
- ✅ 安全：白名单只包含 `['b', 'i', 'strong', 'em', 'u']` 这些无害标签
- ❌ 有风险：白名单包含 `<a>`、`<img>`、`<script>`、`<style>` 等，且属性配置宽松
- ❌ 有风险：使用了 `KEEP_CONTENT: true` 保留内容但可能导致二次污染

### 陷阱 2：DOMPurify 只净化一次，但后来又拼接了未净化的数据

**现象：**
```javascript
const userComment = DOMPurify.sanitize(getURLParameter('comment'), {
  ALLOWED_TAGS: ['b', 'i', 'p']
});
const userName = getURLParameter('name');  // ⚠️ 没有净化！

// 拼接后直接输出
document.getElementById('post').innerHTML =
  `<div class="comment">${userComment} - 来自 ${userName}</div>`;
```

**看起来安全，但：**
- `userComment` 已净化，但 `userName` 没有净化
- 拼接后的字符串里 `userName` 的恶意内容可以绕过
- 这是典型的"多源拼接"陷阱

**定位技巧：**
1. 搜索 `innerHTML` 或 `insertAdjacentHTML` 的赋值点
2. 检查赋值值中涉及的所有变量
3. 追踪每个变量的来源和是否被净化

**研判方法：**
- ❌ 有风险：多个变量拼接，只有部分被净化
- ✅ 安全：所有变量都被净化，或都来自常量
- ✅ 安全：拼接后再统一净化一次

### 陷阱 3：在框架中使用 innerHTML（如 jQuery）而忽视框架的自动转义

**现象：**
```javascript
// React 代码
const userText = props.searchQuery;
const html = `<div class="result">${userText}</div>`;

// 这里使用了 dangerouslySetInnerHTML 的变种
document.getElementById('results').innerHTML = html;  // ❌ 危险！

// 应该改为：
document.getElementById('results').textContent = userText;
// 或
// return <div className="result">{userText}</div>;
```

**看起来安全，但：**
- 在 React/Vue 等框架中，开发者经常混用框架语法和原生 DOM API
- 框架的自动转义在使用原生 `innerHTML` 时失效
- 字符串模板中的变量没有被转义

**定位技巧：**
1. 搜索 `innerHTML` 等原生 API 的使用
2. 检查是否在 React/Vue 等框架环境中使用
3. 验证是否可以改为框架的安全方法

**研判方法：**
- ❌ 有风险：在 React/Vue 中使用原生 `innerHTML` + 字符串模板
- ✅ 安全：使用框架的组件渲染（JSX、模板语法）
- ✅ 安全：必须使用 `innerHTML` 时，用 DOMPurify 或 `textContent`

### 陷阱 4：信任来自受控来源的数据，但未考虑数据被污染的可能

**现象：**
```javascript
// 从后端 API 获取评论
const comments = await fetch('/api/comments').then(r => r.json());

comments.forEach(comment => {
  // 假设 comment.html 是后端提前净化过的
  document.getElementById('comments').innerHTML += comment.html;
});
```

**看起来安全，但：**
- 虽然后端声称已净化，但如果后端在保存时没有净化、或在某个更新中引入了漏洞
- 前端盲目信任会导致存储型 XSS
- API 被攻击者篡改（如 MITM 攻击）也会被利用

**定位技巧：**
1. 搜索所有 `innerHTML` 赋值
2. 追踪数据来源（是否来自 API、localStorage 等）
3. 即使来自"受信源"，也要检查是否有独立的前端防护

**研判方法：**
- ❌ 有风险：无条件信任后端提供的 HTML，前端无防护
- ✅ 较安全：即使信任后端，前端也再做一次 DOMPurify
- ✅ 最安全：后端和前端都做净化

### 陷阱 5：URL 参数解析不当导致绕过

**现象：**
```javascript
// 从 URL 中提取参数
const url = new URL(window.location);
const message = url.searchParams.get('msg');

// 简单的转义尝试
const escaped = message.replace(/</g, '&lt;').replace(/>/g, '&gt;');
document.getElementById('banner').innerHTML = `<p>${escaped}</p>`;
```

**看起来安全，但：**
- 虽然转义了 `<` 和 `>`，但没有转义 `"` 和 `'`，导致属性注入
- 例如：`?msg=" onload="alert(1)` 可以绕过
- 自定义的转义往往不完整

**定位技巧：**
1. 搜索自定义的 `replace` 或正则转义
2. 检查是否转义了所有危险字符：`<`, `>`, `"`, `'`, `&`
3. 优先使用现成的库（DOMPurify）而非自定义

**研判方法：**
- ❌ 有风险：自定义转义函数，转义不完整
- ❌ 有风险：仅转义 `<>` 但忽略属性上下文的 `"'`
- ✅ 安全：使用 `textContent` 而非 `innerHTML`
- ✅ 安全：使用成熟的 DOMPurify 库

---

### 陷阱总结：审计时的快速检查清单

当发现 `innerHTML`、`insertAdjacentHTML` 等危险 API 时，快速检查：

1. **有没有净化？**
   - 无 → L3（高风险）
   - 有 → 继续检查

2. **净化库是什么？**
   - DOMPurify / sanitize-html → 可信，检查配置
   - 自定义过滤 / 简单 replace → 检查是否完整
   - 其他 → 验证该库的安全性

3. **有没有多源拼接？**
   - 是 → 检查每一个来源是否都被净化
   - 否 → 单一来源，简化判断

4. **数据来源是什么？**
   - URL 参数 / 用户输入 → 不可信，必须净化
   - 后端 API → 虽然相对可信，但建议前端也验证
   - localStorage / sessionStorage → 用户数据，需净化
   - 常量 / 框架自动转义 → 可信，无需额外防护

5. **是否跨越多个文件？**
   - 是 → L4，需要追踪完整链路
   - 否 → L2-L3，可在本文件完成分析

## Classify

### 研判标准

#### 确认漏洞
1. 存在直接使用危险 API 插入用户可控字符串；
2. 输入来自外部且未经净化或编码；
3. 能构造 payload 执行脚本。

#### 误报
1. 插入内容为常量或后台已编码；
2. 使用可信净化库过滤危险标签/属性；
3. 仅在受控后台环境展示，不可被攻击者影响。

#### 代码异味
1. 部分路径净化、部分未净化；
2. 依赖前端正则或简单替换；
3. 使用 `sanitize` 但允许危险标签。

## Low risk

### 低风险评级场景

#### 1. 输入仅供内部测试
- 受控环境中使用，外部无法访问；可暂降级。

#### 2. 只影响低价值信息
- 即使 XSS 成功也无法获取敏感数据；风险较低。

#### 3. 已计划接入统一净化实践
- 有明确时间表引入 DOMPurify/CSP 等；可暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部受控 | 攻击面小 | 中 |
| 数据低敏 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
