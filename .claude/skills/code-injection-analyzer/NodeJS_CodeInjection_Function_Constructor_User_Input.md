# Node.js Function() 构造函数代码执行注入

## 漏洞成因

JavaScript 的 `Function()` 构造函数可将字符串动态编译为函数并执行。当用户可控的输入被传入构造函数时，攻击者可注入恶意代码在应用上下文中执行任意代码，造成完整的代码执行。不同于 `eval()`，Function 构造函数的危险性更隐蔽，且在模板字符串拼接场景中极易被忽视。

---

## Details

### 代码示例

```javascript
// 危险模式1：直接使用用户输入作为函数体
const express = require('express');
const app = express();

app.post('/calculate', (req, res) => {
    const formula = req.body.formula;
    const fn = new Function('x', formula);  // 危险：formula 完全可控
    const result = fn(10);
    res.json({ result });
});

// 危险模式2：使用用户输入拼接函数体
app.post('/validator', (req, res) => {
    const validationRule = req.body.rule;
    const validator = new Function('data', `return ${validationRule};`);  // 危险
    const isValid = validator(req.body.data);
    res.json({ valid: isValid });
});

// 危险模式3：多参数拼接
app.post('/processor', (req, res) => {
    const operation = req.query.op;
    const params = req.query.args;
    // Function(arg1, arg2, ..., argN, functionBody)
    const fn = new Function('a', 'b', operation);  // 危险
    res.json({ result: fn(1, 2) });
});

// 危险模式4：从数据库值构造函数
app.get('/rule/:id', (req, res) => {
    const rule = db.get(`SELECT code FROM rules WHERE id = ?`, [req.params.id]);
    if (rule.isCustom) {  // 误以为数据库就是安全的
        const fn = new Function('input', rule.code);  // 危险
        const output = fn(req.query.input);
        res.json({ output });
    }
});

// 危险模式5：使用箭头函数语法
app.post('/transform', (req, res) => {
    const transform = req.body.transform;
    const fn = new Function('obj', `return (${transform});`);  // 危险
    const result = fn({ a: 1, b: 2 });
    res.json({ result });
});

// 危险模式6：异步函数构造
app.post('/async-execute', async (req, res) => {
    const code = req.body.code;
    const asyncFn = new Function('input', `
        return (async () => {
            ${code}  // 危险
        })();
    `);
    const result = await asyncFn(req.body.input);
    res.json({ result });
});
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `new Function(`、`Function.prototype.constructor(`
- 搜索 `Function(` 直接调用（非 `new` 也可）
- 搜索字符串拼接或模板字符串用于参数构造：`'return ' + variable`、`` `${variable}` ``
- 搜索与用户参数相关的变量在 Function 构造参数中的使用
- 搜索 `eval(` 变种如 `Function` 作为间接执行手段

**L2 跳读**：
- 定位所有 `new Function()` 调用，确认其参数来源
- 检查参数来自 HTTP 请求：`req.query`、`req.params`、`req.body`、`req.headers`、`req.cookies`
- 检查函数体参数（最后一个参数）是否包含用户输入
- 检查参数来自数据库时是否有额外验证（数据库输入来源也需追踪）
- 检查前置参数（函数参数名）是否可被污染
- 检查字符串拼接、模板字符串、或其他字符串构造方式

**L3 逐行读**：
- 确认用户输入的确切来源及传输流
- 检查参数被传入 Function 之前是否进行了处理（解码、转义等）
- 追踪所有影响 Function 的中间变量赋值
- 检查是否使用了 sandbox、vm 模块等隔离
- 验证函数返回值是否被直接执行或调用
- 检查是否存在无意的代码注入点（如参数名也来自用户输入）

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 Function 之前是否有条件判断：`if`、`switch`、白名单检查
- 搜索黑名单关键词：`require`、`import`、`process`、`child_process`、`fs`、`eval`、`Function`
- 搜索白名单：`allowedFunctions`、`PERMITTED_OPERATIONS`、`validExpressions`
- 检查是否限制了函数体类型（仅允许表达式vs语句）
- 检查是否使用了 `Function` 之外的替代方案（AST 验证、正则限制等）

**L3 逐行读**：
- 分析白名单/黑名单的实现：精确匹配还是包含匹配？
- 检查验证是否在 Function 调用前完整执行
- 分析保护的绕过风险（大小写、编码、注释等）
- 检查是否存在多条代码路径，某些路径跳过验证
- 检查是否对函数参数名进行了验证
- 审查 Function 返回的函数是否在隔离的执行上下文中运行

**L4 跨模块追踪**：
- 追踪自定义验证函数：`validateExpression()`、`isSafeCode()`、`sanitizeFormula()` 等
- 查找是否使用了 JavaScript 解析库（`acorn`、`babylon`、`@babel/parser`）进行 AST 验证
- 检查是否有全局中间件对所有 Function 调用进行拦截
- 查找 `vm` 模块使用：`vm.runInNewContext()`、`vm.runInThisContext()`
- 追踪环境变量配置是否影响 Function 安全性
- 检查是否使用了 Proxy 或 Object.defineProperty 冻结全局对象

---

## Classify

### 漏洞判定

- **直接使用用户输入作为函数体** → **确认漏洞**
  - 示例：`new Function('x', req.body.formula)`、`` new Function(`return ${userInput}`) ``

- **使用用户输入拼接函数体字符串** → **确认漏洞**
  - 示例：`new Function('data', 'return ' + userInput + ';')`
  - 示例：`` new Function(`return (${userInput});`) ``

- **函数参数名来自用户输入** → **确认漏洞**
  - 示例：`new Function(userProvidedParamName, 'return a + b;')`

- **从不可信源（数据库、外部 API、缓存）获取函数体，无进一步验证** → **确认漏洞**
  - 即使来自数据库，若数据库可被用户影响（如自定义规则表、用户上传的脚本），仍需验证

- **白名单验证不完整或可被绕过**（如大小写敏感、Unicode、换行符、注释等）→ **确认漏洞**
  - 示例：`if (!code.includes('dangerous')) new Function(code)` 可被 `/*dangerous*/` 或大小写变体绕过

- **使用黑名单而非白名单** → **高风险**
  - 黑名单容易被绕过，如 `process` 可被绕过为 `this.constructor.constructor('return process')()`

### 误报判定

- **函数体完全来自硬编码常量** → **误报**
  - 示例：`const templates = { add: 'return a + b', mul: 'return a * b' }; new Function('a', 'b', templates[template])`

- **严格的白名单，且白名单本身不可被用户篡改** → **误报**
  - 示例：`const SAFE = ['a+b', 'a*b', 'a-b']; if (!SAFE.includes(code)) throw Error(); new Function('a', 'b', code)`

- **使用了 AST 验证或完整的代码分析** → **误报**
  - 示例：解析代码为 AST，验证仅包含允许的节点类型（如 BinaryExpression、Identifier）

- **使用 `vm` 模块在沙箱中执行，且沙箱不暴露危险 API** → **误报**
  - 示例：`vm.runInNewContext(userCode, {})`，沙箱中无 `require`、`process` 等

- **仅用于简单计算表达式，且输入严格限制为数字、运算符** → **误报**
  - 示例：`new Function('x', `return ${whitelistedExpression}`)`，其中表达式仅能由 `[0-9+\-*/().]` 组成

### 代码异味

- **使用黑名单检查危险关键字** → **需进一步测试**
  - 可被大小写、Unicode 转义、Unicode normalization 等绕过

- **使用 `String.includes()` 进行关键字扫描** → **需检查覆盖面**
  - 仅检查当前变量，未检查拼接后完整字符串中的关键字组合

- **验证在多个分支中存在遗漏** → **潜在风险**
  - 示例：某些代码路径（如错误处理分支）跳过验证直接调用 Function

- **验证后又进行了字符串处理** → **需追踪完整数据流**
  - 示例：先验证再 URL 解码、Base64 解码、或其他转换

- **仅在前端验证，后端未验证** → **确认可直接绕过**

- **使用注释试图禁用代码** → **无效**
  - 示例：`if (code.includes('require')) code = '/*' + code + '*/'` 仍可执行注释后的代码

### 审计等级

- **L1**：关键词扫描，快速定位所有 Function 构造调用
- **L2**：跳读确认参数来源、字符串拼接方式、验证逻辑
- **L3**：逐行读取数据流、检查所有参数来源和处理
- **L4**：跨模块追踪自定义验证、AST 解析库使用、vm 模块配置

---

## Low risk

### 低风险场景

- **函数体来自硬编码常量或配置文件**：所有可能的函数体在代码中明确列举，不依赖用户输入
  - 示例：`const FORMULAS = { sum: 'return a + b', mul: 'return a * b' }; new Function('a', 'b', FORMULAS[template])`

- **严格的白名单验证**：使用精确匹配（而非包含），验证所有参数，且白名单内容不可被用户修改
  - 示例：`const ALLOWED = /^[0-9+\-*/(). ]+$/; if (!ALLOWED.test(code)) throw Error(); new Function('x', 'return ' + code)`

- **完整的 AST 分析验证**：使用 `acorn`、`@babel/parser` 等库解析代码，验证仅包含允许的语法节点
  - 示例：确保仅包含 BinaryExpression、Identifier、Literal 等安全节点，无 CallExpression

- **沙箱隔离执行**：使用 Node.js `vm` 模块或 `node-vm2` 在隔离上下文中运行，不暴露全局对象、require、process 等
  - 示例：`vm.runInNewContext(code, {})`，沙箱中仅暴露必要的数据上下文

- **参数来源完全受控**：参数仅来自配置文件、环境变量、或已验证的管理员输入，无普通用户输入
  - 示例：功能仅限管理员使用，且权限检查无提升漏洞

- **功能权限隔离**：此功能仅在特定的权限等级（如 admin、dev）下可用
  - 示例：`if (!user.isAdmin) return 403`，且权限验证机制完善

- **完整的审计日志**：所有 Function 构造操作被记录，包含用户身份、输入代码、执行结果、时间戳，支持实时告警
  - 示例：记录每次调用的完整上下文，便于事后审计和威胁检测

- **输入限制为特定类型**：仅接受数字、日期、布尔等基础类型，非字符串代码
  - 示例：验证输入必须匹配 `/^-?\d+(\.\d+)?$/`，确保仅为数字

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- 虽然当前实现相对安全，但 Function 构造本身属于代码执行的危险操作，建议通过预定义的函数库、表达式引擎（如 `expr-eval`、`mathjs`）替代，以进一步降低风险
- 应定期审查白名单内容和权限配置，确保无权限提升漏洞
- 应建立完整的测试覆盖，确保绕过场景（如大小写、Unicode、编码变体、特殊字符、换行符、注释）被充分检验
- 应评估业务场景是否必须使用 Function，考虑使用静态规则、配置驱动的逻辑替代动态代码生成
- 若使用了 vm 沙箱，应定期更新 Node.js 版本和沙箱库，因为沙箱逃逸漏洞时有发生
