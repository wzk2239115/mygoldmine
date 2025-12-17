# NodeJS - xmldom + xpath 组合注入

## Details

### 漏洞成因
`xmldom` 库提供 DOM 解析器，常与 `xpath` 库组合使用进行 XML 节点查询。当用户输入通过字符串拼接方式嵌入 XPath 查询表达式，且未经适当验证或转义时，攻击者可注入恶意 XPath 语法，导致逻辑绕过、数据泄露或未授权访问。此模式常见于 XML 配置文件查询和 SOAP 消息处理。

代码示例：
```javascript
const DOMParser = require('xmldom').DOMParser;
const xpath = require('xpath');

app.post('/login', (req, res) => {
    const username = req.body.username;
    const password = req.body.password;
    const doc = new DOMParser().parseFromString(userXML);

    const query = `//user[username='${username}' and password='${password}']`;
    const result = xpath.select(query, doc);

    if (result.length > 0) {
        res.send('Login success');
    }
});
```

### 快速定位核心操作 (L1: 关键词扫描)
- `require('xmldom')`, `DOMParser`, `parseFromString()`
- `require('xpath')`, `xpath.select()`, `xpath.evaluate()`
- 字符串拼接：模板字符串 `` `//path[${var}]` ``, `+`, `.concat()`
- 特征关键词：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **参数化查询** (L2 跳读) - 检查是否使用 XPath 变量或预编译机制（需自定义实现）
- **输入白名单** (L2 跳读) - 查找 `validator.isAlphanumeric()`, 正则验证 `/^[a-zA-Z0-9]+$/`
- **转义处理** (L3 逐行读) - 检查自定义 `escapeXPath()` 函数，验证是否转义 `'`, `"`, `\`, `/`
- **来源追踪** (L4 跨模块) - 追踪 `req.body`, `req.query`, `req.params` 的数据流，确认是否经过中间件验证

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据直接嵌入 XPath 表达式字符串
2. 未使用参数化查询或有效转义机制
3. 通过 `xpath.select()` 执行查询
4. XML 数据包含敏感信息（用户认证、授权、配置）

**误报情况**：
- 拼接内容为服务器端硬编码常量
- 用户输入通过严格白名单验证（如枚举类型）
- XPath 查询的 XML 数据为公开配置，无敏感信息
- 使用了完整的 XPath 转义库（如 `xpath-escape`）

**代码异味**：
- 自定义转义函数但未覆盖所有特殊字符（`[`, `]`, `@`, `//`）
- 使用正则替换处理输入，但正则表达式不完整
- 输入验证依赖前端验证而非后端强制

## Low risk

### 低风险评级场景

1. **数值型参数** - 输入经过 `parseInt()` 或 `Number()` 强制转换
   - 例：`//item[@id=${Number(itemId)}]` 且验证返回值为有效数字

2. **枚举值限制** - 输入仅限于预定义的字段名或固定选项
   - 例：`const allowedFields = ['name', 'age']; if (!allowedFields.includes(field)) return;`

3. **非关键数据** - XML 查询目标为公开数据集（产品列表、静态配置）

4. **只读操作** - XPath 查询仅用于读取，无法影响身份验证或授权逻辑

5. **沙箱环境** - 代码运行在隔离的测试环境或内部工具中

6. **额外验证层** - 查询结果经过二次权限检查或数据过滤
