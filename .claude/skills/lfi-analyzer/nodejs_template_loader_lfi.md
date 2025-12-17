# Node.js 模板加载器 LFI 审计指南

## 漏洞成因
模板引擎（EJS/Pug/Handlebars等）加载器接受用户可控路径参数，未充分校验和规范化路径，导致通过`../`等相对路径遍历包含任意文件。

---

## Details

### 代码示例

```javascript
// 危险：用户输入直接拼接模板路径
app.get('/render', (req, res) => {
  const tmpl = req.query.template; // 用户可控
  res.render(tmpl);  // EJS: 可读取任意.ejs或其他文件
});

// 危险：动态路径拼接
const templatePath = path.join(__dirname, 'views', userInput);
ejs.renderFile(templatePath, data);

// 危险：Pug/Jade
app.set('views', './views');
res.render(req.query.view); // ../../etc/passwd

// 危险：Handlebars
const template = fs.readFileSync(userControlledPath, 'utf8');
Handlebars.compile(template)(data);
```

### 快速定位核心操作 **(L2-L3)**
**关键API模式：**
- `res.render()`、`res.renderFile()` 
- `ejs.render()`, `ejs.renderFile()`
- `pug.renderFile()`, `pug.compileFile()`
- `handlebars.compile()` + `fs.readFile*()`
- `nunjucks.render()`, `mustache.render()`

**审计流程：**
1. **L1**: 关键词扫描 - 搜索 `render`、`renderFile`、`compileFile`、`template`
2. **L2**: 跳读 - 追溯第一参数来源，标记用户可控点（`req.query/body/params`、HTTP头、数据库字段）
3. **L3**: 逐行读 - 检查路径参数是否未经处理直接传入，关注动态拼接逻辑

**危险信号：**
- 路径参数直接来源于 `req.*` 且无白名单校验
- 使用 `path.join()` 但未限制基准目录
- 动态字符串拼接模板路径

### 快速定位保护机制 **(L2-L4)**

**有效防御（L0-快速跳过）：**
```javascript
// 严格白名单映射
const allowedTemplates = { 'home': 'home.ejs', 'profile': 'profile.ejs' };
res.render(allowedTemplates[userInput]); 

// 强制文件扩展名 + 基准目录限制
const safePath = path.join(templateDir, path.basename(userInput) + '.ejs');
if (!safePath.startsWith(path.resolve(templateDir))) throw Error;
```

**需深入检查（L3-L4）：**
- **正则黑名单** `(L3)` - 检查是否覆盖 `..%2f`、URL编码、Unicode绕过：
  ```javascript
  if (input.includes('..')) return; // 不足：未考虑编码绕过
  ```
  
- **path.normalize/resolve** `(L3)` - 验证是否配合路径前缀检查：
  ```javascript
  const normalized = path.normalize(input); // 单独使用仍可被绕过
  // 需结合：if (!normalized.startsWith(baseDir)) reject;
  ```

- **自定义校验函数** `(L4)` - 跨模块追踪函数实现，确认：
  - 是否检查规范化后的绝对路径
  - 是否强制限制在模板目录内
  - 是否处理符号链接（`fs.realpath`）

**无效防御（L1-升级审计）：**
- 仅检查文件扩展名：`if (!path.endsWith('.ejs'))` 
- 简单字符串替换：`input.replace('..', '')`
- 仅依赖模板引擎默认配置（多数引擎不限制路径）

---

## Classify

### 确认漏洞
- 用户输入可控路径参数 **且** 无白名单/路径规范化校验
- 路径校验可被编码/双写绕过
- 基准目录限制存在TOCTOU竞态或符号链接绕过

### 误报判定
- 路径参数完全硬编码或来自服务端配置文件（非用户可控）
- 存在严格白名单枚举且无可变参数拼接
- 路径规范化后强制前缀检查（需验证实现正确性）

### 代码异味
- 路径依赖数据库字段但无二次校验（需确认数据库写入点是否可控）
- 使用 `path.normalize` 但未配合前缀检查
- 间接可控（如通过session/cookie，需评估这些值的可控性）

---

## Low Risk

### 低风险场景
1. **受限文件类型**：模板引擎强制扩展名且目标文件必须是有效模板语法（读取敏感文件会导致解析报错而不返回内容）
2. **有限暴露面**：
   - 仅管理员角色可访问该功能
   - 需要高权限认证且审计日志完善
3. **路径命名空间隔离**：Docker/容器环境下敏感文件不在同一文件系统
4. **文件内容过滤**：响应处理中存在内容脱敏（如仅返回渲染后HTML不暴露原始文件）

### 仍需标记
即使低风险也应报告，因为：
- 权限提升可能升级为高风险
- 容器配置变更可能暴露敏感文件
- 可能与其他漏洞链式利用（如结合SSRF/XXE）