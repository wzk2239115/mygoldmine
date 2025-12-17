# Node.js eval() 代码执行注入

## 漏洞成因

JavaScript 的 `eval()` 函数在当前作用域内执行传入的代码字符串。当用户可控的输入被传入 eval 时，攻击者可注入任意代码在应用的完整上下文中执行，包括访问所有变量、函数、模块和全局对象。eval 是 JavaScript 中最危险的动态执行函数，其风险大于 Function 构造函数（因为 eval 可访问局部作用域）。

---

## Details

### 代码示例

```javascript
// 危险模式1：直接执行用户输入
const express = require('express');
const app = express();

app.post('/calculate', (req, res) => {
    const expression = req.body.expr;
    const result = eval(expression);  // 危险：expression 完全可控
    res.json({ result });
});

// 危险模式2：使用用户输入拼接代码
app.post('/process', (req, res) => {
    const operation = req.body.op;
    const data = req.body.data;
    eval(`const result = data.${operation};`);  // 危险
    res.json({ result });
});

// 危险模式3：模板字符串拼接
app.get('/validate', (req, res) => {
    const rule = req.query.rule;
    const validator = eval(`(obj) => { return ${rule}; }`);  // 危险
    const isValid = validator(req.body.data);
    res.json({ valid: isValid });
});

// 危险模式4：动态属性访问
app.post('/property', (req, res) => {
    const key = req.body.key;
    const obj = { a: 1, b: 2, c: 3 };
    const value = eval(`obj['${key}']`);  // 危险：可被 eval 本身利用
    res.json({ value });
});

// 危险模式5：条件执行（仍然危险）
app.post('/exec', (req, res) => {
    const code = req.body.code;
    if (code.length < 100) {  // 长度检查不足以防止 eval
        eval(code);  // 危险
    }
    res.json({ executed: true });
});

// 危险模式6：从数据库执行代码
app.get('/rule/:id', (req, res) => {
    const rule = db.query(`SELECT code FROM rules WHERE id = ?`, [req.params.id]);
    if (rule) {
        eval(rule.code);  // 危险：数据库也可被污染
    }
    res.json({ executed: true });
});

// 危险模式7：误认为沙箱后的 eval
const { VM } = require('vm2');
app.post('/sandbox', (req, res) => {
    const code = req.body.code;
    // 虽然使用了沙箱，但主线程的 eval 仍是危险的
    const result = eval(code);  // 危险：沙箱未被利用
    res.json({ result });
});

// 危险模式8：使用 eval 进行反序列化
app.post('/deserialize', (req, res) => {
    const data = req.body.data;
    const obj = eval(`(${data})`);  // 危险：可执行任意代码
    res.json({ obj });
});
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `eval(` 调用（所有出现位置）
- 搜索 `eval` 前后的变量赋值
- 搜索字符串拼接或模板字符串用于 eval 参数：`'...' + variable`、`` `${variable}` ``
- 搜索与 eval 相关的变量在其他上下文中的使用
- 检查是否有类似 `evaluate()`、`execute()`、`run()` 的自定义包装函数调用 eval

**L2 跳读**：
- 定位所有 `eval(` 调用，记录行号和上下文
- 检查 eval 的参数来源：`req.query`、`req.params`、`req.body`、`req.headers`、`req.cookies`、数据库、缓存
- 检查参数是否经过字符串拼接或模板字符串构造
- 检查 eval 前是否有条件判断或验证逻辑
- 检查 eval 后的返回值或副作用（变量赋值、函数调用）
- 追踪是否存在多个 eval 调用（同一文件或不同模块）

**L3 逐行读**：
- 确认用户输入的确切来源及完整传输路径
- 检查参数被传入 eval 之前是否进行了处理（解码、解析、转义等）
- 逐行追踪所有影响 eval 参数的中间变量赋值和修改
- 检查是否使用了正则表达式、黑名单、白名单进行验证
- 检查验证逻辑是否在 eval 调用前完整执行
- 验证 eval 的返回值和执行的副作用
- 检查是否存在无意中暴露的全局变量或敏感信息

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 eval 前是否有严格的条件判断：`if`、`switch`、白名单检查
- 搜索黑名单关键词：`require`、`import`、`process`、`child_process`、`fs`、`eval`、`Function`、`__proto__`、`constructor`
- 搜索白名单：`allowedExpressions`、`PERMITTED_OPERATIONS`、`validPatterns`
- 检查是否使用了沙箱（`vm` 模块、`vm2`、`jailed` 等）
- 检查是否有长度限制、复杂度限制等启发式防护

**L3 逐行读**：
- 分析白名单实现：精确匹配、前缀匹配、还是正则表达式？可否被绕过？
- 分析黑名单实现：是否全面？可否被大小写、Unicode、编码、注释等绕过？
- 检查验证逻辑在 eval 调用的哪一步执行，是否存在 TOCTOU（Time-of-Check-Time-of-Use）漏洞
- 检查是否使用了 AST 解析库验证代码结构
- 检查是否对 eval 的参数进行了正则表达式限制
- 分析沙箱配置：是否禁止了危险的全局对象、原型链访问、内置函数

**L4 跨模块追踪**：
- 追踪自定义验证函数的实现：`validateCode()`、`isSafeExpression()`、`sanitizeInput()` 等
- 检查是否使用了 JavaScript 解析库（`acorn`、`babylon`、`@babel/parser`）进行 AST 验证
- 查找是否有全局中间件或 Hook 对所有 eval 调用进行拦截
- 追踪 `vm` 模块配置：`vm.runInNewContext()`、`vm.runInThisContext()`、`vm.runInIsolatedContext()`
- 检查是否对 Proxy、Object.freeze、Object.seal 等进行了配置以冻结全局对象
- 追踪是否使用了沙箱逃逸防护库（如 `secure-eval`）

---

## Classify

### 漏洞判定

- **直接使用用户输入作为 eval 参数** → **确认漏洞**
  - 示例：`eval(req.body.code)`、`eval(userInput)`

- **使用用户输入拼接 eval 参数** → **确认漏洞**
  - 示例：`eval('result = ' + userInput + ';')`
  - 示例：`` eval(`return ${userInput};`) ``

- **使用用户输入作为对象属性访问** → **确认漏洞**
  - 示例：`eval(`obj['${userKey}']`)`、`eval(`data.${userProp}`)`

- **从不可信源（数据库、缓存、外部 API）获取 eval 参数，无进一步验证** → **确认漏洞**
  - 即使来自数据库，若数据库可被用户影响（如自定义规则、用户上传的代码），仍需验证

- **白名单验证不完整或可被绕过**（大小写敏感、Unicode、注释、编码等）→ **确认漏洞**
  - 示例：`if (!code.includes('dangerous')) eval(code)` 可被注释或大小写绕过

- **使用黑名单而非白名单** → **高风险**
  - 黑名单容易被绕过（如大小写、Unicode、编码变体、注释等）

- **沙箱配置不完善，仍可逃逸** → **确认漏洞**
  - 示例：使用 `eval` 而非沙箱执行、沙箱暴露了全局对象

### 误报判定

- **eval 的参数完全来自硬编码常量** → **误报**
  - 示例：`const EXPRESSIONS = { add: '1+1', mul: '2*3' }; eval(EXPRESSIONS[key])`

- **严格的白名单，且白名单本身不可被用户篡改** → **误报**
  - 示例：`const SAFE = ['x+y', 'x*y']; if (!SAFE.includes(code)) throw Error(); eval(code)`

- **eval 被严格限制在沙箱中执行，且沙箱不暴露危险 API** → **误报**
  - 示例：`vm.runInNewContext(userCode, {})`，沙箱仅有必要数据对象

- **使用 AST 完整验证，确保仅包含安全的语法节点** → **误报**
  - 示例：解析为 AST，验证仅包含 BinaryExpression、Identifier、Literal

- **仅用于简单表达式计算，输入被严格限制为数字和运算符** → **误报**
  - 示例：`eval('return ' + whitelistedExpression)`，表达式仅能由 `[0-9+\-*/(). ]` 组成

### 代码异味

- **使用黑名单检查危险关键字** → **需进一步测试**
  - 可被大小写、Unicode、编码、注释、多行等绕过

- **仅检查当前变量中的关键字** → **需检查完整的 eval 参数**
  - 示例：`if (!code.includes('require')) eval(code)` 仅检查当前变量，拼接后可能包含关键字

- **使用长度限制防护** → **无效**
  - 短 payload 足以实现代码执行，如 `eval("eval(atob('...'))")`

- **使用前端验证** → **确认可绕过**
  - 后端未验证，可直接请求绕过前端检查

- **验证后又进行了字符串处理** → **需追踪完整数据流**
  - 示例：先验证再 URL 解码、Base64 解码、或其他转换

- **仅禁用了特定的函数名** → **无效**
  - 可通过 `this.constructor.constructor`、`Function` 等绕过

### 审计等级

- **L1**：关键词扫描，快速定位所有 eval 调用
- **L2**：跳读确认参数来源、字符串拼接方式、基本防护
- **L3**：逐行读取数据流、详细分析验证逻辑
- **L4**：跨模块追踪自定义验证、沙箱配置、AST 验证实现

---

## Low risk

### 低风险场景

- **eval 的参数完全来自硬编码常量**：所有可能的代码字符串在代码中明确列举，无用户输入
  - 示例：`const FORMULAS = { sum: 'a+b', mul: 'a*b' }; eval(FORMULAS[template])`

- **严格的白名单验证**：使用精确匹配（而非包含），验证完整的 eval 参数
  - 示例：`const ALLOWED = /^[0-9+\-*/(). ]+$/; if (!ALLOWED.test(code)) throw Error(); eval('return ' + code)`

- **完整的 AST 分析和验证**：使用 `acorn`、`@babel/parser` 等库解析代码，验证仅包含允许的语法节点
  - 示例：确保 AST 仅包含 BinaryExpression、Identifier、Literal，无 CallExpression、MemberExpression

- **使用完善的沙箱隔离执行**：使用 Node.js `vm` 模块或专业沙箱库（`vm2`、`jailed`），隔离全局对象和原型链
  - 示例：`vm.runInNewContext(code, {})`，沙箱无 `require`、`process`、`global` 等危险对象

- **eval 仅用于极简场景**：输入被严格限制为数字、日期、布尔等基础类型（非代码字符串）
  - 示例：`eval('return ' + whitelistedExpression)`，表达式仅由 `[0-9+\-*/(). ]` 组成

- **参数来源完全受控**：参数仅来自配置文件、环境变量、或已验证的管理员输入
  - 示例：功能仅限管理员使用，权限检查无提升漏洞

- **功能权限隔离**：此功能仅在特定权限等级下可用，且权限验证完善
  - 示例：`if (!user.isAdmin) return 403`

- **完整的审计日志和监控**：所有 eval 执行被详细记录，包含用户、代码内容、返回值、时间戳
  - 示例：记录每次执行的完整上下文，支持实时告警和事后审计

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- 虽然当前实现相对安全，但 eval 本身属于最危险的动态代码执行方式，建议通过预定义函数库、表达式引擎（如 `expr-eval`、`mathjs`、`safe-eval`）、或 DSL（Domain-Specific Language）替代
- 应定期审查白名单内容和权限配置，确保无权限提升漏洞
- 应建立完整的测试覆盖，确保各种绕过场景（大小写、Unicode、编码、注释、原型链污染）被充分检验
- 应评估业务场景是否真的需要 eval，是否可以使用配置驱动的逻辑、插件系统、或其他替代方案
- 若使用了沙箱，应定期更新 Node.js 版本和沙箱库，因为沙箱逃逸漏洞频繁被发现
- eval 可访问局部作用域，审计时需特别关注 eval 所在函数的上下文中是否存在敏感变量（如密钥、数据库连接、JWT token）
