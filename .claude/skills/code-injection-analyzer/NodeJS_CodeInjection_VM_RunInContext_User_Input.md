# NodeJS_CodeInjection_VM_RunInContext_User_Input

**漏洞类型**: 使用 vm.runInContext() 直接执行用户输入的代码，导致任意代码执行

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 基础 vm.runInContext 示例
const vm = require('vm');
const userInput = req.query.code; // 用户输入
const sandbox = { console };
vm.runInContext(userInput, sandbox); // 直接执行用户代码

// Express 路由示例
app.get('/eval', (req, res) => {
  const code = req.body.script;
  const context = vm.createContext({ Math, JSON });
  try {
    const result = vm.runInContext(code, context, { timeout: 1000 });
    res.json({ result });
  } catch(e) {
    res.status(400).send(e.message);
  }
});

// 动态模板或表达式示例
const vm = require('vm');
const template = req.query.template; // "Math.max(5, 10)"
const sandbox = { Math, Date };
const output = vm.runInContext(`(${template})`, sandbox);

// 多上下文示例
const context = vm.createContext({
  require,
  process,
  eval,
  Buffer
});
vm.runInContext(userInput, context);

// 事件处理器中的代码执行
const handlers = {
  'onClick': req.body.handler // "alert('xss')"
};
Object.keys(handlers).forEach(event => {
  vm.runInContext(handlers[event], vm.createContext({}));
});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- VM 模块导入: `require('vm')`, `import 'vm'`, `require('vm2')`
- 代码执行函数: `vm.runInContext()`, `vm.runInThisContext()`, `vm.runInNewContext()`, `Script.runInContext()`
- 用户输入来源: `req.query`, `req.body`, `req.params`, `req.headers`, `ctx.request`, `process.argv`, 文件读取后的变量
- 代码拼接: 含 `${userVar}`, `+userVar`, `` `code${userVar}` ``，直接在字符串中嵌入用户输入
- 上下文变量: 检查沙箱对象中是否包含 `require`, `process`, `eval`, `Function`, `Buffer`, `child_process`

**L2 跳读定位**:
- 从 API 路由入口或事件处理器扫描用户输入获取点
- 追踪变量从用户输入到 `vm.runInContext*()` 之间的数据流
- 重点关注: 输入是否经过过滤、是否有长度限制、是否被括号或模板包裹
- 检查是否存在代码拼接或字符串模板中直接插入用户数据的情况

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 关键词黑名单: 搜索是否有 `blacklist`, `forbidden`, `blocked`, `dangerous` 等关键词
- 输入检查: `if(/require|process|child_process|eval/i.test(code))`, `code.includes('require')`
- 代码静态分析: 搜索是否调用了 AST 解析或代码分析库 (如 `acorn`, `babel-parser`, `esprima`)
- 上下文限制: 检查 `vm.createContext()` 时传入的沙箱对象内容

**L3 逐行分析**:
- 沙箱对象检查:
  - 是否包含危险全局对象: `require`, `process`, `Buffer`, `eval`, `Function`
  - 是否包含 `child_process` 或执行命令的库
  - 是否显式禁用了这些对象 (如 `require: undefined`, `process: undefined`)
- 输入验证逻辑:
  - 是否通过正则表达式限制允许的关键词
  - 黑名单是否完整 (仅禁用 `require` 但允许 `import`、仅禁用 `process` 但允许其他对象)
  - 是否使用 `JSON.parse()` 限制输入为 JSON 格式
- 代码执行配置:
  - 是否设置 `timeout` 并检查其值是否合理 (防止无限循环)
  - 是否使用 `displayErrors: true` 导致泄露代码信息
  - 是否正确捕获异常并过滤错误信息
- 上下文隔离:
  - 是否使用 `vm.createContext()` 的可选参数创建隔离上下文
  - 是否使用了更安全的替代方案 (如 `isolated-vm`, `worker_threads`)

**L4 跨模块追踪**:
- 追踪沙箱对象的完整定义，检查所有传入上下文的变量
- 检查全局对象或原型链中是否存在危险方法 (如 `Object.prototype.constructor`)
- 查找是否有中间件或预处理逻辑对代码进行过滤
- 验证框架级的输入处理是否已清理危险代码
- 检查环境变量或配置文件中是否有安全相关设置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接或经过简单拼接后被传入 `vm.runInContext*()` 执行
- 沙箱对象包含 `require`, `process`, `eval`, `Function` 或其他危险函数
- 可通过访问 `process.env`, `require('child_process')` 等执行任意系统命令
- 缺少有效的输入验证或黑名单不完整 (如仅禁用 `require` 但允许 `eval`)
- 代码执行的结果或错误信息返回给用户，导致信息泄露
- 无超时设置或超时时间过长，易被利用进行拒绝服务攻击

**误报判定**:
- 用户输入仅限于固定格式 (如纯数字、JSON 数据)，无法执行任意代码
- 代码来自配置文件或数据库中的管理员预设脚本，非实时用户输入
- 使用了严格的白名单验证 (如 `JSON.parse()` 确保输入为合法 JSON) 加上完整的危险对象禁用
- 沙箱对象完全隔离，显式设置为 `{ Object, console }` 等安全子集，所有危险全局对象均为 `undefined`
- 使用了已验证安全的沙箱库 (如经过安全审计的 `isolated-vm` 配置)

**代码异味**:
- 虽然有输入检查但使用黑名单方式 (如仅禁用 `require`, `process`，但可能存在其他执行方式)
- 沙箱对象中包含 `Math`, `String`, `Array` 等内置对象，但允许访问其构造函数 (可能导致原型污染或越狱)
- 设置了 `timeout` 但未检查返回值或异常处理不当
- 错误消息包含用户输入的代码段，导致代码信息泄露
- 使用了已知存在漏洞的 `vm2` 库或旧版 `vm` 模块版本

---

## Low risk

### 低风险场景

**输入限制严格**:
- 用户输入限制为纯数字、固定字符集或 JSON 格式，通过 `JSON.parse()` 严格验证
- 输入长度有严格限制 (如最多 100 字符)，难以构造复杂攻击代码
- 输入仅用于数学表达式计算或简单字符串操作，无法访问外部功能

**沙箱隔离完整**:
- 沙箱对象仅包含 `Math`, `console.log` 等安全的内置对象
- 所有危险全局对象 (require, process, eval, Function, Buffer) 均显式设置为 `undefined`
- 使用 `Object.freeze()` 冻结沙箱对象，防止运行时修改
- 通过 `vm.runInThisContext()` 结合完整隔离实现

**权限与使用场景限制**:
- 功能仅限于后台管理员或内部开发人员，有严格的身份验证和访问日志
- 执行的代码来自系统预定义的模板或配置文件，非用户动态输入
- 有速率限制和执行次数限制，难以进行批量利用

**执行环保护**:
- 设置合理的 `timeout` (如 100-500ms) 并正确处理超时异常
- 使用 `worker_threads` 或 `child_process` 在隔离的进程中执行，父进程不受影响
- 捕获所有异常且错误消息不包含用户输入代码或系统信息
- 有异常检测和监控机制，可及时发现异常代码执行尝试

**架构级保护**:
- 使用经过审计的安全沙箱库 (如配置得当的 `isolated-vm`)
- Node.js 版本为最新稳定版，VM 模块已修复已知漏洞
- 应用运行在容器或虚拟机内，即使代码执行也被限制在隔离环境中
