# NodeJS Express LDAP 身份认证注入

## Details

### 代码示例
Express 应用通常在认证路由中使用 `ldapjs` 或原生 LDAP 库来验证用户身份。以下是常见的易受攻击模式：

```javascript
const ldap = require('ldapjs');

app.post('/login', (req, res) => {
  const username = req.body.username;  // 用户输入
  const password = req.body.password;

  // 危险：直接拼接用户输入到过滤器
  const filter = `(&(uid=${username})(userPassword=${password}))`;

  const client = ldap.createClient({ url: 'ldap://localhost:389' });
  client.search('ou=users,dc=example,dc=com', { filter }, (err, res) => {
    // 处理结果
  });
});
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `req.body`, `req.params`, `req.query` 等用户输入点
- `client.search()`, `client.bind()`, `ldap.search()` 等查询操作
- 过滤器中包含 `${username}` 或字符串拼接的模式
- 字符串模板中出现 LDAP 特殊字符 `(`, `)`, `&`, `|`, `*`

在 Express 项目中，重点检查：
```
/routes/*        - 认证相关路由
/middleware/*    - 认证中间件
/config/*        - LDAP 配置
```

### 快速定位保护机制的技巧
**L2：跳读** - 寻找以下防护迹象：
- `ldap.escapeFilter()` 或 `escapeFilterStrings()` 调用
- 参数化查询模式，如库提供的占位符
- 输入验证的正则表达式或白名单检查
- 专用的 LDAP 过滤器构造库（如 `ldap-filter-parser`）的使用

**L3：逐行读** - 检查防护的完整性：
```javascript
// 安全的防护方式
const filter = ldap.EscapeFilterString(username);
// 或
const filter = escapeFilter(username);  // 需要验证此函数实现
```

关键检查点：
- 转义函数是否覆盖 LDAP 元字符：`*`, `(`, `)`, `\`, `NUL`
- 转义是否在过滤器构造前应用
- 是否使用了参数化查询的库特性

## Classify

### 漏洞判定规则
- **明确漏洞**：用户输入直接拼接到过滤器中，无任何转义或验证
- **高危信号**：字符串模板或字符串拼接构造过滤器 + 来自 HTTP 请求的输入
- **误报排除**：
  - 使用了完整的 LDAP 转义函数，且转义在输入使用前执行
  - 采用了库提供的参数化接口
  - 输入经过严格的白名单验证（如仅允许字母数字）

### 风险评估
- **高风险**：可执行完整 LDAP 查询注入，改变查询逻辑、提升权限、绕过认证
- **中风险**：限定条件下的注入（如已有部分过滤器限制），但仍可获得信息泄露
- **低风险**：输入受到关键字节限制的注入，实际危害受限

## Low risk

### 低风险评级的情形

1. **输入长度严格限制**
   - 用户名限制为 8 个字符以内，且只允许字母数字
   - 无法注入足够的 LDAP 语法字符来改变查询结构

2. **上游验证的限制**
   - LDAP 用户存在性预检查后才进入注入点
   - 即使注入也只能在已知用户的上下文中操作

3. **查询结果处理的隔离**
   - 搜索结果仅用于二次验证（如比对密码哈希值），无权限提升机制
   - 返回结果不直接影响会话权限

4. **字符黑名单覆盖全**（极少见）
   - 代码明确检查并拒绝了 `*`, `(`, `)`, `&`, `|`, `!` 等所有 LDAP 元字符
   - 需要逐行验证黑名单的完整性

