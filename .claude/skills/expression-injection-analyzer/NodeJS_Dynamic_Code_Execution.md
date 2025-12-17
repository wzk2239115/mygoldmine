# Node.js 动态代码执行注入

**漏洞成因**：通过 `eval()`、`Function()` 构造函数、`vm` 模块等方式动态执行用户提供的代码或代码片段，代码执行环境未被沙箱化，导致用户可执行任意 JavaScript 代码，访问全局对象、文件系统、网络等系统资源。常见于模板处理、动态业务规则、代码生成等场景。

---

## Details

**代码示例**：
```javascript
// 危险：直接使用 eval 执行用户输入
const userCode = req.query.code;
eval(userCode);  // 用户可执行任意代码

// 危险：Function 构造函数执行
const formula = req.body.formula;
const calculate = new Function('x', formula);  // formula = "return __dirname"

// 危险：vm 模块未沙箱化
const vm = require('vm');
const userScript = req.body.script;
const context = { result: null };
vm.runInThisContext(userScript);  // 代码在当前上下文执行

// 较安全：使用沙箱化的 vm 模块
const vm = require('vm');
const userScript = req.body.script;
const sandbox = { Math, console: { log: () => {} } };  // 限制可访问对象
const context = vm.createContext(sandbox);
try {
    vm.runInContext(userScript, context, { timeout: 1000 });
} catch (e) {
    // 处理错误或恶意代码
}
```

**快速定位核心操作**：
- 关键词：`eval(`、`Function(`、`vm.runInThisContext`、`vm.runInNewContext`、`vm.runInContext`、`child_process.exec`
- 查看是否接收用户输入的代码字符串
- 追踪代码执行的上下文和沙箱环境
- 检查 vm 模块的 sandbox 配置是否包含危险对象
- 关注是否存在代码执行的超时和内存限制

**快速定位保护机制**：
- 是否完全避免 eval() 和 Function() 构造函数
- 是否使用 vm 模块创建隔离上下文
- 是否限制 sandbox 中暴露的全局对象
- 是否对代码执行时间和内存有限制
- 是否对代码进行静态分析或白名单验证

**审计等级**：**L3-L4**
- **L3**：逐行分析代码执行函数的调用和上下文配置
- **L4**：跨模块追踪用户输入到代码执行的完整链路，验证沙箱有效性

---

## Classify

**确认为漏洞**：
- 直接使用 `eval()` 或 `Function()` 执行用户输入的代码
- 使用 `vm` 模块但 sandbox 中包含危险对象（require、process、fs 等）
- 代码执行环境未被沙箱化，可访问应用全局范围
- 不存在代码执行的超时或内存限制

**误报**：
- 代码完全由应用内部定义，不接收用户输入
- 使用了严格的 vm 沙箱，仅暴露安全的对象和函数
- 代码经过白名单验证，仅允许特定的语法或函数调用
- 代码执行在隔离的子进程或容器中

**代码异味**：
- eval() 的使用有业务合理性（如动态计算公式），但缺少验证
- vm 模块的 sandbox 配置不规范，包含过多对象
- 代码执行逻辑不清晰，难以追踪输入源

---

## Low Risk

以下情况可评为低风险：
- **完全沙箱化**：使用 vm 模块创建隔离上下文，sandbox 仅包含安全对象（Math、JSON 等）
- **表达式能力弱**：仅支持基础数据操作和算术运算，不支持函数定义、循环等高级特性
- **代码执行控制**：严格的代码执行超时（< 100ms）和内存限制，防止拒绝服务
- **输入验证**：代码经过静态分析或白名单验证，仅允许预定义的语法模式
- **内网应用**：仅在内网部署，用户为可信的内部员工

**注意**：即使使用了 vm 模块，沙箱的有效性也需要仔细验证。
