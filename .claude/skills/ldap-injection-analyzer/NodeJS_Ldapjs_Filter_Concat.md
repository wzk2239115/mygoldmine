# NodeJS ldapjs 过滤器拼接

## Details

### 代码示例
`ldapjs` 是 Node.js 中最流行的 LDAP 客户端库。未转义的过滤器拼接会导致严重注入漏洞：

```javascript
const ldap = require('ldapjs');

// 危险示例1：基本的过滤器拼接
app.post('/login', (req, res) => {
  const username = req.body.username;  // 用户输入
  const password = req.body.password;

  const filter = `(&(uid=${username})(userPassword=${password}))`;  // 危险
  client.search('dc=example,dc=com', { filter }, (err, searchRes) => {
    // 处理结果
  });
});

// 危险示例2：模板字符串拼接
const searchUsers = (name, email) => {
  const filter = `(&(cn=*${name}*)(mail=*${email}*))`;  // 危险
  client.search(baseDN, { filter, scope: 'sub' }, callback);
};

// 危险示例3：使用字符串拼接
function findUser(username) {
  const filter = '(uid=' + username + ')';  // 危险
  return new Promise((resolve, reject) => {
    client.search(baseDN, { filter }, (err, res) => {
      // ...
    });
  });
}

// 危险示例4：动态属性名
router.get('/search', (req, res) => {
  const attr = req.query.attr;  // 如 "uid", "mail"
  const value = req.query.value;
  const filter = `(${attr}=${value})`;  // 危险：属性名也不可信
  client.search(baseDN, { filter }, handleResult);
});
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `require('ldapjs')`, `ldapjs.createClient()`
- `client.search()`, `client.bind()` 方法调用
- `req.body`, `req.params`, `req.query`, `req.headers` 用户输入
- 模板字符串 `` `${var}` ``, 字符串拼接 `+` 操作符
- LDAP 过滤器模式：`(&`, `(|`, `(uid=`, `*`

重点检查文件：
```
routes/auth.js
controllers/userController.js
middleware/ldapAuth.js
services/ldapService.js
utils/directory.js
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap.EscapeFilterString()` 或自定义转义函数
- `ldap-escape` npm 包的使用
- 正则验证：`/^[a-zA-Z0-9]+$/.test(input)`
- 白名单映射：`const allowedAttrs = ['uid', 'cn', 'mail']`

**L3：逐行读** - 验证防护完整性：
```javascript
// 检查点1：是否使用了转义
const ldapEscape = require('ldap-escape');
const escaped = ldapEscape.filter(username);
const filter = `(uid=${escaped})`;

// 检查点2：是否所有输入都被转义
const user = ldapEscape.filter(req.body.username);
const dept = req.body.dept;  // 未转义！
const filter = `(&(uid=${user})(department=${dept}))`;

// 检查点3：属性名是否使用白名单
const allowedAttrs = ['uid', 'cn', 'mail'];
if (!allowedAttrs.includes(req.query.attr)) {
  return res.status(400).send('Invalid attribute');
}
```

关键检查点：
- 过滤器字符串中的所有动态部分
- 是否使用了 `ldap-escape` 或等效转义
- 属性名是否也被视为用户输入

## Classify

### 漏洞判定规则
- **明确漏洞**：`client.search()` 的 filter 参数直接包含未转义的用户输入
- **高危信号**：
  - 认证路由中的过滤器拼接
  - 模板字符串或 `+` 拼接用户输入
  - 属性名（attr）来自用户输入且无白名单
- **误报排除**：
  - 使用 `ldap-escape` 正确转义所有输入
  - 输入通过严格的正则或白名单验证
  - 使用了查询构造器的参数化接口

### 风险评估
- **高风险**：认证绕过、权限提升、完整目录遍历
- **中风险**：限定条件下的信息泄露
- **低风险**：查询范围受限，返回属性白名单化

## Low risk

### 低风险评级的情形

1. **输入白名单验证**
   - 使用枚举或预定义值：`const validDepts = ['IT', 'HR']`
   - `if (!validDepts.includes(dept))` 拒绝任意输入
   - 无法注入特殊字符

2. **属性返回限制**
   - `client.search(baseDN, { filter, attributes: ['cn', 'displayName'] })`
   - 仅返回非敏感属性
   - 即使注入也无法获取关键信息

3. **Base DN 范围限制**
   - 搜索限定在公开子树：`ou=public,dc=example,dc=com`
   - 无法访问管理员或特权账户

4. **输入长度限制**
   - `username.substring(0, 16)` 截断输入
   - 长度不足以构造完整注入 payload
