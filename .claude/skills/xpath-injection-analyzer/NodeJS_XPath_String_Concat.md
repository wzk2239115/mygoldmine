# NodeJS - xpath 库字符串拼接注入

## Details

### 漏洞成因
Node.js 的 `xpath` 库通过 `select()` 方法接收 XPath 表达式字符串进行 XML 节点查询。当用户输入通过模板字符串、字符串拼接（`+`）或 `concat()` 直接嵌入表达式时，攻击者可注入 XPath 语法字符（如 `'`, `"`, `or`, `and`, `//`）来改变查询逻辑，绕过身份验证或窃取数据。

代码示例：
```javascript
const xpath = require('xpath');
const dom = require('xmldom').DOMParser;

app.get('/search', (req, res) => {
    const userInput = req.query.username;
    const doc = new dom().parseFromString(xmlData);
    const query = `//user[username='${userInput}']`;
    const nodes = xpath.select(query, doc);
    res.json(nodes);
});
```

### 快速定位核心操作 (L1: 关键词扫描)
- `require('xpath')`, `xpath.select()`, `xpath.select1()`
- 模板字符串拼接：`` `${var}` ``, 字符串拼接：`+`, `.concat()`
- XPath 特殊符号：`//`, `'`, `"`, `[`, `]`, `or`, `and`, `@`
- 数据源：`req.query`, `req.body`, `req.params`, `req.headers`

### 快速定位保护机制 (L2-L4)
- **参数化方式** (L2 跳读) - 检查是否使用 XPath 变量绑定或预编译表达式（xpath 库本身不支持，需自定义）
- **输入验证** (L2 跳读) - 查找白名单验证、正则表达式验证（如 `/^[a-zA-Z0-9]+$/`）
- **转义函数** (L3 逐行读) - 检查是否有自定义转义函数处理单引号、双引号等特殊字符
- **跨模块追踪** (L4) - 追踪用户输入流向，从请求参数到 XPath 查询的完整链路

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据通过字符串拼接或模板字符串直接嵌入 XPath 表达式
2. 无有效的输入验证或转义处理
3. 表达式被 `xpath.select()` 或 `xpath.select1()` 执行
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、个人数据）

**误报情况**：
- 拼接的内容完全来自服务器端常量或枚举值
- 用户输入经过严格的白名单验证（如仅允许 `[a-zA-Z0-9_]`）
- XPath 表达式结构固定，用户输入仅影响非关键部分（如排序字段）
- XML 数据源不包含敏感信息

**代码异味**：
- 存在自定义转义函数但未覆盖所有 XPath 特殊字符
- 使用黑名单过滤而非白名单验证
- 输入验证逻辑复杂且分散在多个模块

## Low risk

### 低风险评级场景

1. **固定查询模板** - 用户输入仅为数值类型且经过类型转换验证
   - 例：`//product[@id=${parseInt(userId)}]` 且 parseInt 结果验证为数字

2. **严格白名单验证** - 输入限制为预定义的枚举值
   - 例：仅允许 `['name', 'email', 'phone']` 作为字段名

3. **非敏感数据查询** - XML 数据不包含用户凭证、权限或个人隐私信息
   - 例：公开的产品目录或配置文件

4. **内部工具环境** - 代码仅在受信任的管理后台或开发环境运行

5. **受限查询权限** - XPath 查询结果经过额外的访问控制验证
