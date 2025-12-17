# Node.js 模板引擎远程 RFI

## 漏洞成因
模板引擎（EJS、Handlebars、Pug 等）允许用户控制远程模板 URL，动态加载远程模板文件，若 URL 验证缺失则导致代码执行。

---

## Details

### 代码示例

```javascript
// 危险示例 1: EJS 动态加载远程模板
const ejs = require('ejs');
const templateUrl = req.query.template;
ejs.render(fs.readFileSync(templateUrl), {});

// 危险示例 2: Handlebars 远程模板
const Handlebars = require('handlebars');
const url = req.body.template_url;
fetch(url).then(r => r.text()).then(template => {
    const compiled = Handlebars.compile(template);
    res.send(compiled(data));
});

// 危险示例 3: Pug 动态路径
const pug = require('pug');
const templatePath = req.query.page;
const html = pug.renderFile(templatePath, {});

// 危险示例 4: 自定义模板加载器
const template = await loadTemplateFromUrl(req.query.url);
const result = renderTemplate(template, context);
```

### 快速定位核心操作 (L2: 跳读)
- **模板引擎**：`ejs`、`handlebars`、`pug`、`nunjucks`、`express`（view engine）
- **关键函数**：
  - EJS: `ejs.render()`, `ejs.renderFile()`
  - Handlebars: `Handlebars.compile()`
  - Pug: `pug.renderFile()`, `pug.compile()`
- **HTTP 加载**：`fs.readFileSync(url)`, `fetch().text()`, `require('url').urlopen()`
- **用户输入来源**：`req.query`, `req.body`, `req.params`

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - `const templates = {page1: './views/page1.ejs', ...}; if (templates[req.query.page])`
  - 预定义的合法模板列表
- **路径限制**：
  - `path.resolve()` 解析路径后验证在 views 目录内
  - `if (!templatePath.startsWith('./views/'))`
- **URL 验证**：
  - `if (!url.startsWith('https://trusted.com/'))`
  - `new URL(url).hostname === 'trusted-domain.com'`
- **扩展名检查**：
  - `if (!templateUrl.endsWith('.ejs'))`
- **内容大小限制**：
  - 限制下载大小防止 DoS

---

## Classify

### 漏洞
- 用户可控的模板路径或 URL
- 无白名单或白名单可绕过（路径遍历、编码等）
- 直接加载并渲染用户可控的模板
- 模板中支持代码执行（如 EJS 的 `<% %>` 标签）

### 误报
- 模板路径完全来自配置文件或硬编码白名单
- 用户输入仅作为模板变量值，非模板内容本身
- 模板引擎配置禁用了代码执行功能
- 模板存储在受保护的目录，无外网访问

### 代码异味
- 模板路径部分可控但有验证（需检查验证逻辑）
- 使用弱验证如 `indexOf('.ejs') !== -1`（可被绕过）
- 模板加载逻辑跨多个文件难以追踪

---

## Low risk

- **硬编码模板选择**：用户输入仅选择预定义的模板键名，模板路径由代码映射
- **严格路径限制**：模板仅能从特定目录加载，且路径遍历被完全阻止
- **URL 白名单 + 协议限制**：仅允许 HTTPS 且仅限特定信任域名
- **完整性验证**：模板下载后验证签名或哈希
- **模板禁用代码执行**：配置模板引擎禁止危险标签（如 EJS `scriptletPattern = null`）
- **只读静态模板**：所有模板预装包内或数据库存储，无动态加载

---

## 审计重点

1. 定位所有模板加载点（render、renderFile 等）
2. 追踪模板路径/URL 的参数来源
3. 验证白名单是否完整且难以绕过
4. 检查模板引擎配置是否允许代码执行
5. 测试路径遍历和 URL 绕过向量
6. 检查是否存在间接加载路径（配置文件、环境变量等）
