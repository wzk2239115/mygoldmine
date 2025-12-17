# NodeJS - Express 框架 XPath 注入

## Details

### 漏洞成因
Express 框架是 Node.js 最流行的 web 框架。当 Express 应用使用 `xpath` 或 `libxmljs` 等库进行 XML 数据查询时，从 `req.query`, `req.body`, `req.params` 获取的用户输入若直接通过字符串拼接嵌入 XPath 表达式，将导致注入漏洞。Express 的中间件机制如果未正确配置验证中间件，会使漏洞更易触发。常见于 REST API、配置管理接口和数据查询端点。

代码示例：
```javascript
const express = require('express');
const xpath = require('xpath');
const dom = require('xmldom').DOMParser;

const app = express();
app.use(express.json());

app.post('/api/users/search', (req, res) => {
    const { username, role } = req.body;
    const doc = new dom().parseFromString(userDatabase);

    const query = `//user[username='${username}' and role='${role}']`;
    const users = xpath.select(query, doc);

    res.json(users);
});
```

### 快速定位核心操作 (L1: 关键词扫描)
- `express`, `app.get()`, `app.post()`, `app.put()`, `router.route()`
- `req.query`, `req.body`, `req.params`, `req.headers`
- `xpath.select()`, `libxmljs.find()`, `.get()`, `.evaluate()`
- 模板字符串拼接：`` `//path[${var}]` ``, `+`, `.concat()`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **验证中间件** (L2 跳读) - 检查 `express-validator`, `joi`, `yup` 等验证库的使用
- **输入过滤** (L2 跳读) - 查找 `validator.isAlphanumeric()`, 正则验证 `/^[a-zA-Z0-9]+$/`
- **自定义中间件** (L3 逐行读) - 检查 `app.use()` 中的自定义输入清理中间件
- **转义函数** (L3 逐行读) - 验证自定义 `sanitizeXPath()` 或 `escapeInput()` 函数的完整性
- **跨模块追踪** (L4) - 追踪从路由处理器到 XPath 查询的完整数据流，检查中间处理层

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. Express 路由处理器中的用户输入（`req.*`）通过字符串拼接嵌入 XPath 表达式
2. 未使用验证中间件或验证不充分
3. 无有效的转义或参数化机制
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、个人数据）

**误报情况**：
- 用户输入通过 `express-validator` 等库进行严格白名单验证
- 拼接的数据来自服务器端常量或已验证的会话数据
- 使用了完整的 XPath 转义中间件
- XML 数据源为公开的静态配置，无敏感内容

**代码异味**：
- 验证中间件存在但验证规则不严格（如仅检查非空）
- 自定义转义函数未覆盖所有 XPath 特殊字符
- 使用正则表达式黑名单过滤，可能存在绕过
- 输入验证逻辑在路由处理器内部而非中间件，增加遗漏风险

## Low risk

### 低风险评级场景

1. **强验证中间件** - 使用 `express-validator` 等库进行严格白名单验证
   - 例：`body('username').isAlphanumeric().trim().escape()`

2. **数值型参数** - 输入经过类型转换且验证为有效数字
   - 例：`parseInt(req.params.id, 10)` 且检查 `isNaN()`

3. **枚举值限制** - 输入受限于预定义的固定选项
   - 例：`const validRoles = ['admin', 'user']; if (!validRoles.includes(role)) return res.status(400);`

4. **非敏感数据** - XPath 查询的 XML 数据为公开的产品目录或静态配置

5. **只读接口** - API 端点仅用于数据检索，不涉及身份验证或授权判断

6. **内部 API** - 接口仅对内部服务开放，且有额外的认证层

7. **结果过滤** - 查询结果经过权限检查或数据脱敏中间件处理

8. **速率限制** - 存在速率限制中间件，降低攻击者探测和利用的效率
