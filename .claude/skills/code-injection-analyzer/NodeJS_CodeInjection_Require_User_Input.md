# Node.js require() 动态加载用户可控模块注入

## 漏洞成因

Node.js 的 `require()` 或 `import()` 函数根据用户输入动态加载模块，攻击者可强制加载任意模块（npm 包、本地恶意文件、遍历目录）在应用上下文中执行任意代码，或访问敏感的本地文件（如 `process.env`、`.env` 文件内容等）。当结合路径遍历、包冒充、node_modules 污染等技术时，威力尤其强大。

---

## Details

### 代码示例

```javascript
// 危险模式1：直接使用用户输入作为模块名
const express = require('express');
const app = express();

app.get('/load', (req, res) => {
    const moduleName = req.query.module;
    const module = require(moduleName);  // 危险：moduleName完全可控
    res.json({ result: module.execute() });
});

// 危险模式2：使用用户输入的路径拼接
app.post('/plugin', (req, res) => {
    const pluginName = req.body.name;
    const plugin = require('./plugins/' + pluginName);  // 危险：可能被 ../ 遍历
    plugin.init();
    res.send('Plugin loaded');
});

// 危险模式3：动态 import()
app.get('/async-load', async (req, res) => {
    const modulePath = req.query.path;
    const module = await import(modulePath);  // 危险：动态导入
    res.json({ loaded: true });
});

// 危险模式4：基于用户输入的条件加载
const customModule = req.query.type === 'advanced'
    ? require('./handlers/' + req.query.handler)  // 危险
    : require('./default');

// 危险模式5：从 npm 加载任意第三方包
const userPackage = req.body.package;
const lib = require(userPackage);  // 危险：加载任意 npm 包
lib.process(data);
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `require(` 且参数非字符串常量或配置常量的使用
- 搜索 `import(` 表达式（动态导入）
- 搜索字符串拼接或模板字符串用于路径构造：`'./path/' + variable`、`` `./path/${variable}` ``
- 搜索 `require.resolve()`、`Module.load()`、`module.require()`
- 搜索与用户参数相关的变量在 require/import 中的使用

**L2 跳读**：
- 定位 require/import 调用，确认其第一个参数（模块名/路径）来源
- 检查参数来自 HTTP 请求：`req.query`、`req.params`、`req.body`、`req.headers`、`req.cookies`
- 检查是否存在字符串拼接、模板字符串、或路径操作（`path.join()`、`path.resolve()`）
- 追踪参数经过的所有中间变量和赋值
- 检查参数是否被 URL 解码、Base64 解码等处理

**L3 逐行读**：
- 确认用户输入的确切来源（HTTP 请求的哪个部分、是否来自数据库或外部源）
- 检查该参数被传入 require/import 之前是否修改过
- 检查是否使用了相对路径（`./`、`../`）或绝对路径（`/`）
- 追踪参数在代码中的所有赋值和修改
- 确认加载后的模块是否被直接执行或调用

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 require/import 前是否有条件判断：`if`、`switch`、`includes`、`startsWith`、`matches`
- 搜索黑名单关键词：`../`、`/etc`、`root`、`.env`、`process`、`child_process`
- 检查是否有白名单：`allowedModules`、`PERMITTED_PACKAGES`、`validModules`
- 检查是否验证文件扩展名：`.js`、`.json` 等

**L3 逐行读**：
- 分析白名单实现：精确匹配还是前缀/后缀匹配？可否被绕过？
- 分析黑名单实现：是否全面？可否使用大小写、URL 编码、Unicode 等绕过？
- 检查验证逻辑：白名单在哪一步执行？是否在模块加载前？
- 检查是否使用 `path.basename()`、`path.normalize()` 等规范化路径
- 检查是否限制了可加载的模块来源（npm 包 vs 本地文件）

**L4 跨模块追踪**：
- 追踪自定义验证函数：`validateModuleName()`、`isAllowedModule()`、`sanitizePath()` 等的具体实现
- 检查是否有全局中间件或 Hook 对所有 require/import 进行拦截验证
- 查找 `require.extensions` 自定义扩展处理
- 追踪环境变量配置：`NODE_PATH`、`NODE_MODULES` 等是否被用户控制
- 检查 `package.json` 中的 `main` 字段是否可被篡改
- 查找是否使用了沙箱或虚拟机（`vm` 模块、`node-vm2` 等）来隔离动态代码执行

---

## Classify

### 漏洞判定

- **直接使用用户输入作为模块名** → **确认漏洞**
  - 示例：`require(req.query.module)`、`await import(userInput)`

- **使用用户输入拼接的路径，可被 `../` 路径遍历攻击** → **确认漏洞**
  - 示例：`require('./plugins/' + req.body.plugin)` 可被 `../../malicious` 绕过

- **从用户输入的 npm 包名加载第三方模块，无版本锁定** → **确认漏洞**
  - 示例：`require(userProvidedPackageName)` 可加载恶意的 npm 包

- **白名单验证不完整或可被绕过**（如大小写敏感、URL 编码、Unicode）→ **确认漏洞**
  - 示例：`allowedModules.includes(moduleName)` 但未规范化，可使用 `Module` vs `module` 绕过

- **在沙箱之外动态加载代码** → **确认漏洞**
  - 示例：虽然使用了 `vm` 模块，但 require/import 在主线程执行

### 误报判定

- **模块名完全来自硬编码常量、不可变配置文件** → **误报**
  - 示例：`require('./plugins/' + CONST_PLUGIN_LIST[index])`

- **严格的白名单，且白名单本身不可被用户篡改** → **误报**
  - 示例：`const ALLOWED = ['auth', 'db']; if (!ALLOWED.includes(name)) throw Error(); require('./plugins/' + name)`

- **使用了严格的路径规范化和验证** → **误报**
  - 示例：`const safe = path.basename(userInput); if (!safe.match(/^[a-z0-9_]+\.js$/)) throw Error(); require('./plugins/' + safe)`

- **模块加载被限制在 npm packages，且版本锁定在 lock 文件中** → **误报**
  - 示例：仅加载已发布的 npm 包，版本完全由 `package-lock.json` 控制

### 代码异味

- **黑名单过滤**（而非白名单）检查 `../` 或 `.env` → **需进一步测试**
  - 可能被绕过（如 `..\\`、`%2e%2e%2f`、`..%252f`）

- **使用 `String.startsWith()`、`includes()` 进行验证** → **需检查完整性**
  - 示例：`if (name.includes('..')) return;` 仅检查当前变量，未检查拼接后的完整路径

- **验证在多个分支中存在遗漏** → **潜在风险**
  - 示例：某些代码路径跳过了验证直接 require

- **路径验证后又进行了解码、转义反转等操作** → **需追踪完整数据流**
  - 示例：先验证后 URI 解码

- **仅在前端进行验证，后端未验证** → **确认可直接绕过**

### 审计等级

- **L1**：关键词扫描，快速定位所有 require/import 调用
- **L2**：跳读确认参数来源、拼接操作
- **L3**：逐行读取数据流和验证逻辑
- **L4**：跨模块追踪自定义验证、中间件、Hook 实现

---

## Low risk

### 低风险场景

- **严格的模块名白名单**：仅允许加载预定义的模块名列表（如 `['auth', 'db', 'utils']`），且白名单在代码中硬编码
- **完整的路径规范化和验证**：使用 `path.resolve()` + `startsWith()` 或正则表达式精确限制，例如验证结果路径必须在 `./plugins/` 目录内
- **仅加载 npm 包**：不加载本地相对路径文件，仅从 npm registry 的已发布包中加载（版本锁定）
- **执行环境隔离**：即使加载成功，通过 Node.js `vm` 模块在沙箱中执行，且沙箱仅暴露必要的 API
- **仅加载特定文件类型**：严格验证文件扩展名为 `.json`（不执行代码），通过 `JSON.parse()` 加载
- **权限隔离**：功能仅限管理员或特定角色访问，且权限验证无提升漏洞
- **完整的审计日志**：所有动态加载操作被记录，包含用户身份、加载模块名、时间戳，支持实时告警
- **依赖版本自动更新检测**：使用 `npm audit` 或类似工具检测已加载模块是否存在已知漏洞

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- 虽然当前实现相对安全，但动态代码加载本身属于高风险操作，建议通过静态配置或插件系统（如 Plugin API）替代
- 应定期审查白名单内容和权限配置，确保无权限提升漏洞
- 应建立完整的测试覆盖，确保绕过场景（如 URL 编码、Unicode 变体）被充分检验
