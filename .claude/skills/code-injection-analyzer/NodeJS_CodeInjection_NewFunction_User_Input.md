# Node.js new Function() 代码注入

**漏洞成因**：使用 `new Function()` 构造函数根据用户输入动态创建和执行函数代码，`new Function()` 与 `eval()` 具有等价的代码执行能力，但在函数体参数级别接受用户输入时更易被忽视。攻击者可通过注入任意 JavaScript 代码来执行恶意操作，常见于规则引擎、动态计算器、配置处理、代码生成等场景。

---

## Details

**代码示例**：
```javascript
// 危险：函数体直接包含用户输入
const userCode = req.query.code;
const func = new Function(userCode);
func();

// 危险：动态拼接函数体
const userLogic = req.body.filter;
const filterFunc = new Function(`return (${userLogic})`);
const result = filterFunc();

// 危险：参数与函数体混合用户输入
const varName = req.query.var;
const value = req.query.value;
const fn = new Function(varName, `return ${value}`);
fn();

// 危险：循环中动态创建函数
for (let rule of userRules) {
  const validator = new Function(`return ${rule}`);
  validators.push(validator);
}

// 虚假安全：仅过滤部分关键字（易绕过）
const sanitized = userCode.replace(/import|require/g, '');
const func = new Function(sanitized);  // 仍可执行恶意代码

// 虚假安全：使用 Function.toString() 校验（无法真正防护）
if (userCode.includes('process') || userCode.includes('require')) {
  throw new Error('not allowed');
}
const func = new Function(userCode);  // 可通过编码、字符拆分等绕过
```

**快速定位核心操作**（L1-L2）：
- 关键词：`new Function(`、`Function(` 直接调用（非 new）、`.constructor('...')`
- 查看 Function 构造函数的参数来源（最后一个参数是函数体，前面是参数列表）
- 检查函数体或参数是否包含用户输入、字符串拼接、模板字符串
- 追踪用户输入来源：`req.query`、`req.body`、`req.params`、数据库、文件、缓存
- 关键词组合：`Function` + 动态字符串拼接（`+`、`` ` ``、`.concat()`）

**快速定位保护机制**（L2-L3）：
- 是否存在白名单验证：仅允许的操作符、变量、函数列表
- 是否使用 AST 解析（如 `esprima`、`acorn`）代替直接执行
- 是否使用 WebWorkers 或 Sandbox 隔离执行（如 `vm` 模块）
- 是否对输入进行了类型检查和长度限制（易绕过）
- 是否检查禁止关键字（如 `process`、`require`、`global`、`eval`）— 需检查编码、Unicode 等绕过方式
- 是否使用正则表达式过滤（易被 Unicode、多字节编码等绕过）

**审计等级**：**L2-L4**
- **L2**：跳读含有 `new Function` 的代码块，快速确认参数来源
- **L3**：逐行读取 Function 构造参数的构造方式，检查所有防护机制
- **L4**：跨模块追踪用户输入到 Function 的完整数据流，检查所有转换点、序列化、缓存

---

## Classify

**确认为漏洞**：
- 用户输入直接作为 Function 构造函数的函数体或参数
- 无防护或防护机制可绕过（如仅过滤部分字符、基于黑名单、正则表达式）
- 即使存在简单过滤（如 `replace` 删除关键字），仍可通过：
  - Unicode 编码（如 `\u0070\u0072\u006f\u0063\u0065\u0073\u0073` → `process`）
  - 字符拆分与拼接（如 `pro` + `cess`）
  - 使用 Function 内的对象属性访问（如 `(function(){}).constructor.prototype.constructor('code')()` 绕过）

**误报**：
- Function 仅用于执行硬编码常量字符串
- 用户输入经过严格白名单验证，且白名单不包含任何可执行的操作（如仅允许数值、布尔值）
- 使用 `vm.runInContext()` 或 `vm.runInNewContext()` 在严格沙箱内执行（需检查是否可逃逸）

**代码异味**：
- Function 存在但有防护，但防护机制未经充分测试（如仅过滤显而易见的关键字）
- 业务可用表达式解析库（如 `expression-evaluator`、`jsep`）或声明式规则引擎替代
- 权限控制依赖前端或 session，未在后端验证

---

## Low Risk

以下情况可评为低风险：
- **严格的白名单验证**：Function 的参数/函数体在 AST 级别解析，仅允许预定义的操作符和变量（如 `+`, `-`, `*`, `/`, 数值、布尔常量）
- **完全沙箱隔离**：使用 Node.js `vm` 模块的 `runInNewContext()` 并禁用所有全局对象访问
- **权限严格受限**：代码执行权限受限，无法访问 `process`、`require`、`global`、`Buffer`、文件系统、网络接口
- **内网隔离**：仅限特定用户（如管理员）、特定 IP 段、或内网环境访问
- **执行环境隔离**：在无法访问敏感资源的容器/虚拟机内执行
- **完整的审计日志和监控**：所有 Function 创建和执行被记录、可溯源
