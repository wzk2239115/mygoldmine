# NodeJS ActiveDirectory 注入

## Details

### 代码示例
`activedirectory` 是一个基于 ldapjs 的高级 AD 操作库。未正确处理用户输入同样会导致注入：

```javascript
const ActiveDirectory = require('activedirectory');

// 危险示例1：认证查询
app.post('/login', (req, res) => {
  const username = req.body.username;
  const password = req.body.password;

  // 危险：findUser 方法使用的过滤器可能包含未转义输入
  const query = `sAMAccountName=${username}`;  // 危险
  ad.findUser(query, (err, user) => {
    if (user) ad.authenticate(user.dn, password, handleAuth);
  });
});

// 危险示例2：查找用户
const searchUser = (searchTerm) => {
  // 危险：直接拼接搜索条件
  const opts = {
    filter: `(&(objectClass=user)(cn=*${searchTerm}*))`,
    attributes: ['dn', 'cn', 'mail']
  };
  ad.find(opts, callback);
};

// 危险示例3：isUserMemberOf 的使用
router.get('/checkMembership', (req, res) => {
  const username = req.query.username;
  const group = req.query.group;

  // 危险：group 未验证
  ad.isUserMemberOf(username, group, (err, isMember) => {
    res.json({ isMember });
  });
});

// 危险示例4：使用原始的 ldapjs 方法
const ad = new ActiveDirectory(config);
const username = req.body.username;

// 危险：混合使用 activedirectory 和 ldapjs
ad._query.search('dc=example,dc=com', {
  filter: `(sAMAccountName=${username})`,  // 危险
  scope: 'sub'
}, handleResults);
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `require('activedirectory')`, `new ActiveDirectory()`
- `.findUser()`, `.findUsers()`, `.find()`, `.authenticate()`
- `.isUserMemberOf()`, `.getGroupMembershipForUser()`
- `req.body`, `req.query`, `req.params` 用户输入
- 模板字符串 `` `${var}` ``, 字符串拼接 `+`

重点检查文件：
```
controllers/adController.js
services/activeDirectory.js
middleware/adAuth.js
routes/users.js
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap-escape` 包的导入和使用
- 输入验证：正则表达式、白名单
- 使用 activedirectory 的高级方法而非原始过滤器
- 配置中的 `baseDN` 限制

**L3：逐行读** - 验证防护完整性：
```javascript
// 检查点1：findUser 参数是否被转义
const ldapEscape = require('ldap-escape');
const escaped = ldapEscape.filter(username);
ad.findUser(escaped, callback);

// 检查点2：自定义过滤器是否安全
const opts = {
  filter: ad.opts.userFilter  // 使用配置中的过滤器模板
    .replace('%s', ldapEscape.filter(username))
};

// 检查点3：是否使用了底层 ldapjs 方法
ad._query.search()  // 危险信号！应检查其 filter 参数
```

关键检查点：
- 是否直接传递用户输入给 AD 方法
- 是否访问了 `ad._query` 等底层对象
- 过滤器字符串的构造方式

## Classify

### 漏洞判定规则
- **明确漏洞**：用户输入直接用于构造 LDAP 过滤器或传递给 AD 方法
- **高危信号**：
  - 认证流程中的注入（`findUser`, `authenticate`）
  - 使用 `ad._query` 等底层方法
  - 自定义 `filter` 选项包含未转义输入
- **误报排除**：
  - 使用 `ldap-escape` 正确转义所有输入
  - 仅使用 activedirectory 的高级方法，且输入来自配置文件
  - 输入经过严格验证（白名单、正则）

### 风险评估
- **高风险**：认证绕过、权限提升、AD 完整目录遍历
- **中风险**：限定条件下的信息泄露
- **低风险**：查询结果仅用于显示，输入受严格限制

## Low risk

### 低风险评级的情形

1. **使用高级 API**
   - 仅使用 `ad.findUser(username)` 而不自定义过滤器
   - 依赖 activedirectory 库的内部转义（需验证版本）
   - 未访问 `ad._query` 等底层对象

2. **输入白名单验证**
   - 用户名经过严格验证：`/^[a-zA-Z0-9._-]+$/`
   - 长度限制：`username.length <= 64`
   - 无法注入特殊字符

3. **baseDN 范围限制**
   - activedirectory 配置中 `baseDN` 限定为非敏感 OU
   - 如 `ou=external,dc=example,dc=com`
   - 无法访问管理员或服务账户

4. **只读操作且结果受限**
   - 仅使用 `findUsers` 查询用户列表
   - 返回属性白名单化：`attributes: ['cn', 'displayName']`
   - 不返回敏感信息
