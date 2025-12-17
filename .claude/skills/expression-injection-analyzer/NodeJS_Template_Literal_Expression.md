# Node.js 模板字符串表达式注入

**漏洞成因**：JavaScript 模板字符串（backtick-quoted 字符串）中包含表达式 `${...}`，当这些表达式包含用户输入且被直接 eval 或通过 Function 构造执行时，导致任意代码执行。常见于动态 SQL 构造、API 调用、代码生成等场景。

---

## Details

**代码示例**：
```javascript
// 危险：模板字符串直接执行
const userInput = req.query.search;
const query = `SELECT * FROM users WHERE name = '${userInput}'`;
database.execute(query);  // SQL 注入

// 危险：模板字符串用作代码执行的输入
const formula = req.body.formula;
const code = `return ${formula}`;
const calculate = new Function(code);
calculate();  // 代码注入

// 较安全：使用参数化查询
const query = 'SELECT * FROM users WHERE name = ?';
database.execute(query, [userInput]);

// 较安全：使用正则白名单验证
const userInput = req.query.search;
if (!/^[a-zA-Z0-9_]+$/.test(userInput)) {
    throw new Error('Invalid input');
}
const query = `SELECT * FROM users WHERE name = '${userInput}'`;
```

**快速定位核心操作**：
- 关键词：反引号（backtick）、`${}`、`Function()`、`eval()`、数据库查询构造
- 查看是否存在字符串拼接构造的 SQL、URL、代码片段
- 追踪模板字符串中的变量来源
- 检查是否进行了输入验证和转义
- 关注是否将模板字符串传入危险函数

**快速定位保护机制**：
- 是否使用了参数化查询或参数化 API 调用
- 是否对用户输入进行了白名单验证
- 是否对特殊字符进行了转义
- 是否避免了 eval 和 Function 构造
- 是否使用了类型检查防止注入

**审计等级**：**L2-L3**
- **L2**：跳读包含模板字符串的代码，识别拼接操作
- **L3**：逐行验证输入验证和参数化的完整性

---

## Classify

**确认为漏洞**：
- 模板字符串包含用户输入且直接用于数据库查询
- 模板字符串用于动态代码生成并被 eval 或 Function 执行
- 不存在输入验证或仅使用黑名单过滤
- 特殊字符未被转义

**误报**：
- 模板字符串仅用于展示，不涉及代码执行或数据库操作
- 所有用户输入都经过严格的白名单验证
- 使用了参数化查询或 API 调用

**代码异味**：
- 存在模板字符串拼接但缺少明确的输入验证
- 过多的字符串拼接逻辑，难以维护和审计

---

## Low Risk

以下情况可评为低风险：
- **参数化查询**：数据库操作完全使用参数化方式
- **严格白名单**：用户输入被严格限制在数字、字母、下划线等安全字符
- **类型转换**：用户输入被强制转换为特定类型（如整数）
- **内网应用**：仅由可信内部用户使用
- **沙箱隔离**：代码执行在隔离环境中，权限最小化

**注意**：模板字符串的注入风险取决于使用场景和输入验证的完整性。
