# NodeJS - libxmljs 库 XPath 注入

## Details

### 漏洞成因
`libxmljs` 是 Node.js 的 C++ 绑定库，提供高性能的 XML 解析和 XPath 查询功能。其 `get()` 和 `find()` 方法接收 XPath 表达式字符串。当用户输入通过字符串拼接或模板字符串直接嵌入表达式时，攻击者可注入 XPath 语法元素（如 `'`, `or`, `//`, `@`）操纵查询逻辑，导致未授权数据访问或身份验证绕过。常见于 XML 配置管理和文档查询系统。

代码示例：
```javascript
const libxmljs = require('libxmljs');

app.get('/search', (req, res) => {
    const category = req.query.category;
    const xmlDoc = libxmljs.parseXml(xmlString);

    const query = `//product[@category='${category}']`;
    const results = xmlDoc.find(query);

    res.json(results.map(node => node.text()));
});
```

### 快速定位核心操作 (L1: 关键词扫描)
- `require('libxmljs')`, `libxmljs.parseXml()`, `libxmljs.parseXmlString()`
- `.find()`, `.get()` 方法调用
- 模板字符串拼接：`` `//path[${var}]` ``, `+`, `.concat()`
- XPath 语法特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`, `not()`

### 快速定位保护机制 (L2-L4)
- **参数化查询** (L2 跳读) - libxmljs 不原生支持参数化，检查是否有自定义封装
- **输入白名单** (L2 跳读) - 查找 `validator` 库使用、正则表达式验证 `/^[a-zA-Z0-9_-]+$/`
- **转义函数** (L3 逐行读) - 检查自定义 `escapeXPath()` 实现，验证是否处理 `'`, `"`, `\`, `/`, `[`, `]`
- **数据流追踪** (L4 跨模块) - 从 `req.query`, `req.body`, `req.params` 到 XPath 查询的完整路径分析

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据通过字符串拼接直接嵌入 XPath 表达式
2. 未实施有效的输入验证、转义或参数化机制
3. 表达式通过 `.find()` 或 `.get()` 执行
4. 查询的 XML 文档包含敏感信息（用户数据、配置、权限）

**误报情况**：
- 拼接的数据来自服务器端常量或配置文件
- 用户输入经过严格的白名单验证（如固定的枚举值）
- XPath 表达式结构固定，用户输入仅影响数值型参数
- XML 文档为公开的静态数据，无敏感内容

**代码异味**：
- 存在自定义转义函数但未覆盖所有 XPath 特殊字符
- 使用正则表达式黑名单过滤，而非白名单验证
- 输入验证逻辑分散在多个函数或模块中
- 依赖客户端验证而非服务器端强制验证

## Low risk

### 低风险评级场景

1. **强类型转换** - 用户输入经过 `parseInt()`, `parseFloat()` 强制转换为数值
   - 例：`//item[@id=${parseInt(id, 10)}]` 且验证转换结果

2. **枚举值限制** - 输入受限于预定义的固定选项
   - 例：`const validCategories = ['electronics', 'books']; if (!validCategories.includes(input)) return;`

3. **非敏感数据** - XML 文档仅包含公开的产品目录或静态配置

4. **只读查询** - XPath 仅用于数据检索，不涉及身份验证或授权逻辑

5. **开发环境** - 代码运行在隔离的测试或开发环境中

6. **结果过滤** - 查询结果经过额外的访问控制层或数据脱敏处理

7. **长度限制** - 输入长度严格限制（如 max 10 字符），降低攻击面
