# JavaScript URL 参数反射型 XSS

## 基本信息

- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 10-20分钟（单个漏洞点）
- **先决知识：** URL 参数解析、JavaScript DOM 操作、HTML 编码基础
- **复杂度评估：**
  - 简单场景（直接参数输出）：10-15分钟
  - 复杂场景（多个参数、嵌套操作）：20-30分钟

## 🚀 30秒快速清单

- [ ] 代码是否使用 `URLSearchParams` 或 `location.search` 获取 URL 参数？
- [ ] 获取的参数值是否直接写入 DOM（如 `innerHTML`、`textContent`）？
- [ ] 是否进行了 HTML 编码或使用了 `textContent` 等安全方法？
- [ ] 是否存在对参数的验证或白名单检查？
- [ ] 错误页面或提示信息是否也对 URL 参数进行了安全处理？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L2+ 深度分析

## Details

### 漏洞成因
前端脚本从 `location.search`、`location.hash`、`document.referrer` 或 `window.name` 读取数据，并直接写入页面。若未对这些数据进行编码或净化，攻击者可构造带恶意脚本的链接，诱导用户打开，从而在浏览器中执行任意 JavaScript。

### 代码示例

**易受攻击的代码：**
```javascript
const keyword = new URLSearchParams(location.search).get('q');
if (keyword) {
  document.querySelector('#result-title').innerHTML = `搜索结果：${keyword}`;
}
```

**安全示例：**
```javascript
const keyword = new URLSearchParams(location.search).get('q');
if (keyword) {
  const sanitized = DOMPurify.sanitize(keyword, { ALLOWED_TAGS: [] });
  document.querySelector('#result-title').textContent = `搜索结果：${sanitized}`;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `location.search`, `location.hash`, `document.referrer`, `window.name`, `decodeURIComponent`, `URLSearchParams`。

**定位步骤：**
1. 搜索读取 URL 或 referrer 的代码；
2. 跳读（L2）检查是否直接写入 DOM 或 HTML；
3. 注意通过自定义路由（如 hash 路由）构造的动态内容。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `textContent`/`innerText`，避免 HTML 注入；
- 对输入进行白名单校验或长度限制；
- 使用 DOMPurify 等净化库；
- 引入 CSP、Referrer-Policy 限制来源。

**定位技巧：**
- 逐行读（L3）确认是否有正则过滤或错误的替换（如 `replace('<', '')`）；
- 跨模块追踪（L4）链接由后台模板生成，是否可能插入恶意字符。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 仅使用安全 API/净化后再输出 | **L0（快速跳过）** | 风险低 |
| 部分页面直接输出 URL 参数 | **L2（跳读）** | 核实场景 |
| 广泛使用 `innerHTML` 拼接参数 | **L3（逐行读）** | 高风险 |
| 参数经多层传递再输出 | **L4（跨模块追踪）** | 需完整数据流 |

## Classify

### 研判标准

#### 确认漏洞
1. URL/Referrer 数据直接写入 DOM/HTML；
2. 缺少净化或编码；
3. 能构造链接执行脚本。

#### 误报
1. 输出到文本节点或经过可靠净化；
2. 参数仅用于逻辑不影响渲染；
3. 页面不对外暴露，且访问需强认证。

#### 代码异味
1. 手工替换 `<`、`>` 等字符但覆盖不全；
2. 使用 `escape`/`unescape` 等过时函数；
3. 将参数拼进内联事件或脚本块。

## Low risk

### 低风险评级场景

#### 1. 页面仅面向内部测试
- 访问受控，可暂列低风险。

#### 2. 显示内容经过截断且仅含字母数字
- 虽仍建议转义，但风险较低。

#### 3. 正在接入统一净化库
- 有明确计划引入 DOMPurify；暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部页面 | 攻击面小 | 中 |
| 字符集受限 | 难以构造 payload | 低 |
| 改造计划明确 | 可暂缓 | 低 |
