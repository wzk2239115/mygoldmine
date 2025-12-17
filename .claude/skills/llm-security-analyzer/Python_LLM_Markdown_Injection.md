# **Python LLM Markdown Injection**

当应用将 LLM 输出渲染为 Markdown，且未对 Markdown 内容进行适当的清理或验证时，攻击者可以通过注入恶意 Markdown 语法（如 JavaScript、链接、脚本标签等），实现 XSS 或其他攻击。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索 Markdown 库：`markdown.markdown()`、`mistune.html()`、`markdown_it`
- 查找 HTML 渲染：`pypandoc.convert_text()`、`rst_to_html()`
- 搜索 LLM 输出直接传递给 Markdown 解析器
- 定位 Markdown 转换配置：`extensions=[]`、`safe_mode=`
- 查找前端 Markdown 渲染库的调用：Flask `render_template()`、Django 模板

**核心操作保护机制（L2: 跳读）**
- 检查 Markdown 库的安全配置选项
- 查看是否使用了白名单机制限制允许的 HTML 标签
- 验证是否使用了 `bleach` 库清理 HTML 输出
- 检查是否禁用了危险的 Markdown 扩展（如 tables、footnotes）
- 查看是否对生成的 HTML 进行了额外的过滤

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪 LLM 输出到 Markdown 库的传递
- 检查 Markdown 库的初始化和配置
- 审查生成的 HTML 是否进行了转义
- 查看是否有自定义的 Markdown 扩展
- 检查 CSS、JavaScript 注入的可能性（如 style 标签）

**数据流追踪（L4: 跨模块追踪）**
- 追踪 LLM 输出的处理链：生成 → 存储 → Markdown 转换 → 渲染
- 检查是否有中间步骤进行了修改或清理
- 验证前后端是否都进行了处理

## Classify

**确认为漏洞的特征：**
1. LLM 输出直接传递给 Markdown 解析库，无任何清理
2. Markdown 库启用了不安全的扩展（如 raw HTML）
3. 生成的 HTML 未经 `bleach` 或类似白名单工具清理
4. 允许 HTML 标签（`<script>`、`<iframe>`、`<img onerror>`）直接通过
5. Markdown 允许内嵌 HTML 且无限制

**误报场景：**
1. Markdown 库配置为仅允许基本格式（粗体、斜体、链接），禁用 HTML
2. 生成的 HTML 使用 `bleach.clean()` 进行了严格白名单清理
3. 前端框架（React、Vue）自动转义了 Markdown 渲染结果
4. LLM 输出内容被严格限制（如仅允许特定格式）
5. 应用使用了专门为安全设计的 Markdown 库

**代码异味（需要深入审查）**
1. 自定义 Markdown 扩展
2. 条件性地启用/禁用某些功能
3. 多层嵌套的 Markdown 处理
4. 使用了已知有漏洞的 Markdown 库版本

## Low risk

**评级为低风险的场景：**
1. Markdown 解析器配置为禁用所有 HTML，仅允许基本格式
2. 生成的 HTML 使用 `bleach.clean()` 严格白名单清理
3. 前端使用 React、Vue 等现代框架，自动转义所有输出
4. LLM 输出内容来自系统提示，完全由应用控制
5. 应用明确使用了安全的 Markdown 渲染库配置
