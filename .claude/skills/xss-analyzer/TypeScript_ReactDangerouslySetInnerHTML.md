# TypeScript｜React dangerouslySetInnerHTML XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-40分钟（单个漏洞点）
- **先决知识：** React JSX 语法、HTML 编码、DOMPurify 使用
- **复杂度评估：**
  - 简单场景（单点净化）：15-20分钟
  - 复杂场景（多源数据拼接）：40-60分钟

## 🚀 30秒快速清单

- [ ] 代码中是否存在 `dangerouslySetInnerHTML` 的使用？
- [ ] `__html` 的值是否来自用户输入或外部数据？
- [ ] 在赋值前是否经过 DOMPurify 或其他可信净化库的处理？
- [ ] 如果使用了净化库，配置的白名单是否过于宽松（是否允许事件属性）？
- [ ] 是否跨越多个文件或多个数据源的拼接？

**判断：** 如果超过 2 个问题打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
React 默认对 JSX 变量进行编码。但若使用 `dangerouslySetInnerHTML`、`createPortal` 等 API 将未净化的字符串插入 DOM，就会绕过 React 的自动转义，导致 XSS。常见于渲染富文本、CMS 内容、Markdown 转 HTML 时直接信任用户输入。

### 代码示例

**易受攻击的代码：**
```tsx
function Preview({ content }: { content: string }) {
  return <div dangerouslySetInnerHTML={{ __html: content }} />; // content 可控
}
```

**安全示例：**
```tsx
import DOMPurify from 'dompurify';

function Preview({ content }: { content: string }) {
  const sanitized = DOMPurify.sanitize(content, { ALLOWED_TAGS: ['b', 'i', 'p'] });
  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}

// 或直接渲染文本：
// return <div>{content}</div>;
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `dangerouslySetInnerHTML`, `createPortal`, `__html`, `setInnerHTML`, `renderToStaticMarkup`。

**定位步骤：**
1. 搜索 `dangerouslySetInnerHTML` 的使用点；
2. 跳读（L2）确认 `__html` 值的来源；
3. 检查是否使用 DOMPurify/自定义净化。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- DOMPurify、sanitize-html、marked + dompurify 等净化；
- 限定白名单标签/属性；
- 后端富文本过滤；
- CSP 防止内联脚本执行。

**定位技巧：**
- 逐行读（L3）确保净化发生在 `__html` 赋值前；
- 跨模块追踪（L4）富文本数据从后端到前端渲染的链路。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 未使用 `dangerouslySetInnerHTML` 或已严格净化 | **L0（快速跳过）** | 风险低 |
| 部分组件净化不足 | **L2（跳读）** | 核实净化策略 |
| 直接输出用户输入 | **L3（逐行读）** | 高风险 |
| 富文本来自多源且流程复杂 | **L4（跨模块追踪）** | 需完整分析 |

## 🚨 陷阱识别 - React 特定的风险场景

### 陷阱 1：字符串拼接后再使用 dangerouslySetInnerHTML

**现象：**
```tsx
function CommentPreview({ userComment, userName }) {
  const html = `<div class="comment">
    <strong>${userName}</strong>
    <p>${userComment}</p>
  </div>`;

  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
```

**看起来安全，但：**
- 虽然使用了 `dangerouslySetInnerHTML`，开发者可能认为这是"显式的"危险声明
- 但字符串模板 `${}` 中的变量 `userName` 和 `userComment` 完全没有转义
- 如果这些值来自用户输入，XSS 就会执行

**定位技巧：**
1. 搜索 `dangerouslySetInnerHTML`
2. 查看 `__html` 的值是否使用了字符串模板
3. 检查模板中的变量是否被净化

**研判方法：**
- ❌ 有风险：`${userInput}` 直接在字符串模板中，无净化
- ✅ 安全：`DOMPurify.sanitize(userInput)` 后再拼接
- ✅ 安全：不用 `dangerouslySetInnerHTML`，直接渲染组件

### 陷阱 2：createPortal 中的 HTML 未净化

**现象：**
```tsx
function Modal({ content }) {
  return ReactDOM.createPortal(
    <div dangerouslySetInnerHTML={{ __html: content }} />,
    document.getElementById('modal-root')
  );
}
```

**看起来安全，但：**
- 开发者可能认为 `createPortal` 有特殊的安全性
- 实际上 `createPortal` 只是改变了 DOM 树的位置，没有任何净化作用
- `dangerouslySetInnerHTML` 仍然是危险的

**定位技巧：**
1. 搜索 `createPortal` 的使用
2. 检查其中是否有 `dangerouslySetInnerHTML`
3. 验证 HTML 内容是否被净化

**研判方法：**
- ❌ 有风险：`createPortal` 中使用 `dangerouslySetInnerHTML` 且无净化
- ✅ 安全：即使在 `createPortal` 中，也要净化 HTML 内容

### 陷阱 3：在条件渲染中混用安全和不安全的方式

**现象：**
```tsx
function RichTextRenderer({ content, isMarkdown }) {
  if (isMarkdown) {
    // 使用 markdown-to-html 库
    const html = markdownToHtml(content);
    return <div dangerouslySetInnerHTML={{ __html: html }} />;
  } else {
    // 直接输出
    return <div>{content}</div>;
  }
}
```

**看起来安全，但：**
- Markdown 库可能没有净化 HTML，或净化不完整
- 如果攻击者知道 `isMarkdown=true` 时有不同的处理，可能利用 Markdown 语法注入 XSS
- 例如：`` ``` <img src=x onerror="alert(1)"> ``` ``

**定位技巧：**
1. 搜索条件渲染中的 `dangerouslySetInnerHTML`
2. 检查不同分支使用的库和方法
3. 验证所有可能的输入途径

**研判方法：**
- ❌ 有风险：依赖外部库（markdown、richtext 编辑器）但未验证其安全性
- ✅ 安全：使用的库已知安全，或输出后再用 DOMPurify 净化
- ✅ 最安全：所有富文本都统一经过一个净化流程

### 陷阱 4：从 props 或 state 中直接使用未验证的内容

**现象：**
```tsx
function BlogPost({ postData }) {
  // postData.html 来自后端 API
  return (
    <div>
      <h1>{postData.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: postData.html }} />
    </div>
  );
}
```

**看起来安全，但：**
- 假设 `postData.html` 是后端提前格式化好的 HTML
- 但如果后端在保存时没有净化，或 API 被篡改，前端会被攻击
- 前端对数据的来源完全无感知

**定位技巧：**
1. 搜索 `dangerouslySetInnerHTML` 中使用的变量
2. 追踪这些变量的来源（从 props、state、API 等）
3. 检查是否有独立的前端验证/净化

**研判方法：**
- ❌ 有风险：无条件信任来自 API 的 HTML，前端无净化
- ✅ 较安全：虽然信任后端，但前端也再做一次 DOMPurify
- ✅ 最安全：定义清晰的数据协议，后端返回结构化数据而非 HTML

### 陷阱 5：DOMPurify 配置不当导致的 XSS

**现象：**
```tsx
import DOMPurify from 'dompurify';

function RichTextPreview({ content }) {
  const sanitized = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: ['p', 'div', 'span', 'a', 'img', 'br'],
    ALLOWED_ATTR: ['href', 'src', 'class']
  });

  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
```

**看起来安全，但：**
- 白名单中包含了 `<a>` 和 `href`，但没有限制 `javascript:` 协议
- 白名单中包含了 `<img>` 和 `src`，但没有禁用 `onerror` 事件
- 实际上 DOMPurify 默认会禁用事件，但配置中明确允许 `class` 属性可能导致 CSS 注入

**定位技巧：**
1. 搜索 `DOMPurify.sanitize` 的所有调用
2. 检查每个调用的配置参数
3. 特别关注 `ALLOWED_TAGS` 和 `ALLOWED_ATTR` 的组合

**研判方法：**
- ✅ 最安全：白名单只包含无害标签 `['b', 'i', 'strong', 'em', 'u', 'p', 'br']`
- ✅ 较安全：白名单包含 `<a>` 时，指定 `ALLOWED_URI_REGEXP` 限制协议
- ❌ 有风险：未限制 URI 协议，允许 `javascript:` 等危险协议
- ❌ 有风险：过度宽松的属性白名单，如允许 `style` 导致 CSS 注入

---

### 陷阱总结：React 审计快速检查

看到 `dangerouslySetInnerHTML` 时，立即检查：

1. **`__html` 的值来自哪里？**
   - 常量 → L0（无风险）
   - 经过 DOMPurify → 检查配置
   - 其他 → L3+（需要完整分析）

2. **是否有字符串拼接？**
   - 有且包含用户输入 → L3+（高风险）
   - 无，仅传入单一变量 → 继续检查该变量

3. **DOMPurify 配置是否合理？**
   - 仅允许基础格式标签 → ✅ 安全
   - 允许链接或图片但无协议限制 → ❌ 有风险
   - 自定义过滤而非 DOMPurify → 需要验证

4. **数据来源是否经过验证？**
   - 来自用户输入 → 必须净化
   - 来自后端 API → 建议也净化
   - 来自常量或框架处理 → 可信

5. **有没有更安全的替代方案？**
   - 不需要 HTML → 用 `{content}` 直接渲染
   - 需要格式但可用 Markdown → 用可信的 Markdown 库
   - 需要富文本 → 考虑使用富文本编辑器的防护机制

## Classify

### 研判标准

#### 确认漏洞
1. `dangerouslySetInnerHTML` 使用用户可控字符串；
2. 缺少净化或编码；
3. 可以注入脚本执行。

#### 误报
1. 字符串为常量或经过可信后端过滤；
2. 仅用于受控后台预览；
3. 内容经过 DOMPurify 严格配置，明确白名单。

#### 代码异味
1. 使用 `dangerouslySetInnerHTML` 但无注释说明来源；
2. 自定义“过滤”仅移除 `<script>` 标签；
3. 若干组件重复实现净化逻辑，缺少统一保障。

## Low risk

### 低风险评级场景

#### 1. 富文本仅面向内部管理员
- 攻击面小，可暂列低风险。

#### 2. 内容属性严格受限，且启用 CSP
- 虽仍建议净化，但影响有限。

#### 3. 即将接入统一净化中间层
- 明确排期，暂降级并跟踪执行。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员受控 | 攻击面小 | 中 |
| CSP + 内容受限 | 风险较低 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
