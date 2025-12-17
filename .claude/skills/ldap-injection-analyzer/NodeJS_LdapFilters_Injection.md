# NodeJS LdapFilters 注入

## Details

### 代码示例
`ldap-filters` 或类似的过滤器构造库如果使用不当，仍可能引入注入漏洞：

```javascript
// 危险示例1：直接拼接到自定义过滤器
const { parseFilter } = require('ldap-filters');

function buildFilter(username, role) {
  // 危险：字符串拼接后再解析
  const filterStr = `(&(uid=${username})(role=${role}))`;
  return parseFilter(filterStr);  // 解析不等于转义
}

// 危险示例2：动态构造复杂过滤器
const buildComplexFilter = (criteria) => {
  let filterParts = [];
  for (let [key, value] of Object.entries(criteria)) {
    // 危险：未验证 key 和 value
    filterParts.push(`(${key}=${value})`);
  }
  return `(&${filterParts.join('')})`;
};

// 示例：criteria = { uid: "admin", dept: "*))(|(uid=*" }

// 危险示例3：使用库但未转义输入
const Filter = require('ldap-filters').Filter;

router.post('/search', (req, res) => {
  const username = req.body.username;
  // 危险：Filter.parse 不会转义，仅解析语法
  const filter = Filter.parse(`(uid=${username})`);
  client.search(baseDN, { filter: filter.toString() }, handleResult);
});

// 危险示例4：部分使用库，部分手工拼接
const { EqualityFilter } = require('ldap-filters');

function searchUser(uid, dept) {
  const uidFilter = new EqualityFilter({ attribute: 'uid', value: uid });  // 安全
  // 危险：部分手工拼接
  const deptPart = `(department=${dept})`;  // 未转义
  const combined = `(&${uidFilter.toString()}${deptPart})`;
  return combined;
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `require('ldap-filters')`, `parseFilter`, `Filter.parse()`
- `EqualityFilter`, `SubstringFilter`, `AndFilter`, `OrFilter` 等类
- 字符串拼接：`` `${var}` ``, `+` 操作符
- `Object.entries()`, `for...of` 动态遍历用户输入
- `filter.toString()` 转换为字符串后使用

重点检查文件：
```
services/filterBuilder.js
utils/ldapFilters.js
routes/search.js
middleware/ldapQuery.js
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 使用库的构造函数而非字符串拼接：`new EqualityFilter({ attribute, value })`
- 输入白名单验证：`const validAttrs = ['uid', 'cn']`
- 值的转义：`ldap-escape` 包的使用
- 属性名的验证逻辑

**L3：逐行读** - 验证防护完整性：
```javascript
// 检查点1：是否完全使用库的 API
const filter = new EqualityFilter({
  attribute: 'uid',  // 常量
  value: username    // 值是否被库正确处理？
});

// 检查点2：动态属性是否使用白名单
const allowedAttrs = ['uid', 'cn', 'mail'];
if (!allowedAttrs.includes(req.body.attr)) {
  throw new Error('Invalid attribute');
}

// 检查点3：是否混合使用库和手工拼接
const filter1 = new EqualityFilter({ attribute: 'uid', value: uid });
const filterStr = `(&${filter1.toString()}(dept=${dept}))`;  // 危险！
```

关键检查点：
- 是否纯粹使用库的 API 而非字符串拼接
- 库是否自动转义值（需查阅文档或源码）
- 属性名是否来自用户输入

## Classify

### 漏洞判定规则
- **明确漏洞**：使用 `parseFilter()` 或 `Filter.parse()` 处理包含未转义用户输入的字符串
- **高危信号**：
  - 字符串拼接后再调用 `parseFilter()`
  - 动态遍历用户输入的对象构造过滤器
  - 混合使用库 API 和手工拼接
- **误报排除**：
  - 纯粹使用库的构造函数 API（如 `new EqualityFilter()`）
  - 库文档明确说明会自动转义值
  - 属性名使用白名单验证

### 风险评估
- **高风险**：完全的 LDAP 注入，可绕过认证或泄露敏感数据
- **中风险**：部分过滤器可注入，影响有限
- **低风险**：库正确使用且仅值可控，属性名受限

## Low risk

### 低风险评级的情形

1. **纯粹使用库的构造函数**
   - 完全使用 `new EqualityFilter({ attribute, value })` 形式
   - 未使用字符串拼接或 `parse()` 方法
   - 库负责转义，前提是库实现正确

2. **属性名白名单**
   - 所有属性名从白名单中选择
   - `const attrs = { uid: userId, cn: userName }`，键是常量
   - 用户无法控制属性名

3. **库版本已知安全**
   - 使用的 `ldap-filters` 版本经过安全审计
   - 已确认该版本正确转义所有输入
   - 无已知 CVE

4. **值的二次验证**
   - 虽然过滤器构造可能不完善，但值经过严格验证
   - 如 `value.match(/^[a-zA-Z0-9]+$/)` 拒绝特殊字符
