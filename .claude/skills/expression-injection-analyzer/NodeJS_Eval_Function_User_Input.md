# NodeJS eval 函数用户输入注入

**漏洞成因**：JavaScript 的 `eval()` 函数和 `Function()` 构造函数可执行字符串形式的 JavaScript 代码。当 Node.js 应用将用户输入直接传递给这些函数时，攻击者可构造恶意代码访问文件系统、执行系统命令、窃取环境变量、修改全局对象等，导致远程代码执行（RCE）。常见于动态表达式求值、JSON 解析、配置加载、模板渲染等场景。

---

## Details

**代码示例**：
```javascript
// 危险：直接使用 eval() 执行用户输入
const userInput = req.query.expr;
const result = eval(userInput); // 危险：用户可注入任意 JavaScript 代码

// 危险：使用 Function() 构造函数
const userCode = req.body.code;
const fn = new Function(userCode); // 危险：动态创建函数
fn();

// 危险：使用 vm 模块但配置不当
const vm = require('vm');
vm.runInThisContext(userInput); // 危险：在当前上下文执行

// 攻击载荷示例
// require('child_process').exec('calc')
// process.mainModule.require('child_process').exec('calc')
// global.process.mainModule.constructor._load('child_process').exec('calc')
// require('fs').readFileSync('/etc/passwd', 'utf8')

// 危险：即使使用 vm.createContext() 也可能绕过
const context = vm.createContext({});
vm.runInContext(userInput, context); // 仍可能通过原型链逃逸

// 较安全：使用 JSON.parse() 而非 eval() 解析 JSON
const data = JSON.parse(userInput); // 仅解析 JSON，不执行代码

// 较安全：使用安全的表达式求值库
const { Parser } = require('expr-eval');
const parser = new Parser();
const expr = parser.parse(userInput);
const result = expr.evaluate({ x: 10, y: 20 }); // 限制表达式能力

// 较安全：使用 vm2 库（更严格的沙箱）
const { VM } = require('vm2');
const vm = new VM({ timeout: 1000, sandbox: {} });
vm.run(userInput); // 提供更强的沙箱隔离
```

**快速定位核心操作**：
- 关键词：`eval(`、`Function(`、`vm.runInThisContext`、`vm.runInContext`、`vm.runInNewContext`
- 查找 `eval()` 和 `Function()` 的调用位置
- 追踪这些函数的参数来源，判断是否包含用户输入
- 检查 `vm` 模块的使用方式和上下文配置
- 关注动态代码执行场景：表达式求值、配置加载、模板渲染
- 搜索 `package.json` 中的 `vm2`、`safe-eval` 等安全库

**快速定位保护机制**：
- 是否使用 `JSON.parse()` 而非 `eval()` 解析数据
- 是否使用安全的表达式求值库（如 `expr-eval`、`jsep`）
- 是否使用 `vm2` 而非原生 `vm` 模块
- 是否对用户输入进行白名单验证或语法检查
- 是否使用了 CSP (Content Security Policy) 限制代码执行
- 是否设置了代码执行的超时时间
- Node.js 版本是否为最新 LTS 版本

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速识别 `eval(` 和 `Function(` 的使用
- **L2**：跳读函数调用上下文，判断参数来源
- **L3**：逐行验证是否存在输入验证和沙箱隔离

---

## Classify

**确认为漏洞**：
- 直接使用 `eval()` 或 `Function()` 执行用户输入的字符串
- 使用原生 `vm` 模块且未充分隔离上下文
- 用户输入未经任何验证或过滤
- 可通过原型链或全局对象访问 `require`、`process`、`child_process` 等危险模块

**误报**：
- 使用 `JSON.parse()` 而非 `eval()` 解析 JSON 数据
- 使用 `vm2` 或其他安全的沙箱库且配置正确
- 用户输入经过严格的白名单验证，仅允许安全的数学表达式
- 代码字符串为硬编码常量或来自可信的配置文件

**代码异味**：
- 使用 `eval()` 或 `Function()` 处理动态逻辑，即使当前输入不可控
- 通过字符串拼接构造代码
- 使用原生 `vm` 模块而非更安全的 `vm2`
- 缺乏代码执行的审计日志和超时控制

---

## Low Risk

以下情况可评为低风险：
- **使用 JSON.parse**：仅解析 JSON 数据，不执行代码
- **安全求值库**：使用 `expr-eval`、`jsep` 等安全的表达式求值库
- **vm2 沙箱**：使用 `vm2` 提供严格的沙箱隔离且配置超时
- **表达式白名单**：用户输入必须匹配预定义的安全模式（如纯数学表达式）
- **容器隔离**：Node.js 应用运行在受限的容器或虚拟机中
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有动态代码执行均记录日志并实时监控异常模式

**注意**：Node.js 的 `eval()` 极其危险，几乎所有沙箱都可能被绕过，强烈建议避免使用并改用 `JSON.parse()` 或安全的替代方案。
