# UnboundID 过滤器注入

## Details

### 代码示例
UnboundID LDAP SDK如果未正确使用Filter类会导致注入：

```java
import com.unboundid.ldap.sdk.*;

// 危险示例1：直接拼接过滤器字符串
public SearchResult searchUsers(String username) throws LDAPException {
    LDAPConnection connection = getConnection();
    // 危险：字符串拼接
    String filter = "(uid=" + username + ")";
    SearchRequest request = new SearchRequest("dc=example,dc=com", SearchScope.SUB, filter);
    return connection.search(request);
}

// 危险示例2：使用String.format
public boolean authenticate(String uid, String password) throws LDAPException {
    String filter = String.format("(&(uid=%s)(userPassword=%s))", uid, password);  // 危险
    SearchResult result = connection.search("dc=example,dc=com", SearchScope.SUB, filter);
    return result.getEntryCount() > 0;
}

// 危险示例3：Filter.create但参数未转义
public SearchResult complexSearch(Map<String, String> criteria) throws LDAPException {
    StringBuilder filterStr = new StringBuilder("(&");
    for (Map.Entry<String, String> entry : criteria.entrySet()) {
        // 危险：动态构造未转义
        filterStr.append("(").append(entry.getKey()).append("=").append(entry.getValue()).append(")");
    }
    filterStr.append(")");
    Filter filter = Filter.create(filterStr.toString());  // create不会转义，仅解析
    return connection.search("dc=example,dc=com", SearchScope.SUB, filter);
}

// 危险示例4：DN参数注入
public Entry getUser(String uid) throws LDAPException {
    String dn = "uid=" + uid + ",ou=users,dc=example,dc=com";  // 危险
    return connection.getEntry(dn);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import com.unboundid.ldap.sdk.*`
- `LDAPConnection`, `SearchRequest`, `Filter`
- `.search()`, `.searchForEntry()`, `.getEntry()`
- 字符串拼接：`+`, `String.format()`, `StringBuilder`
- `Filter.create()`, `Filter.createANDFilter()`

重点检查文件：
```
src/main/java/**/ldap/*Client.java
src/main/java/**/service/*LdapService.java
src/main/java/**/auth/*AuthService.java
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `Filter.encodeValue()`静态方法
- `Filter.createEqualityFilter()`使用
- `DN.escapeRDNValue()`调用
- 输入白名单验证

**L3：逐行读** - 验证防护完整性：
```java
// 检查点1：使用Filter.encodeValue转义
String safe = Filter.encodeValue(username);
String filterStr = "(uid=" + safe + ")";
Filter filter = Filter.create(filterStr);

// 检查点2：使用Filter工厂方法
Filter filter = Filter.createEqualityFilter("uid", username);
// 工厂方法会自动转义吗？需验证SDK版本

// 检查点3：DN转义
String safeDN = "uid=" + DN.escapeRDNValue(uid) + ",ou=users,dc=example,dc=com";
Entry entry = connection.getEntry(safeDN);
```

关键检查点：
- 是否使用Filter.encodeValue转义
- 是否使用Filter工厂方法而非字符串拼接
- DN组件是否使用DN.escapeRDNValue

## Classify

### 漏洞判定规则
- **明确漏洞**：过滤器或DN字符串直接拼接未转义的用户输入
- **高危信号**：
  - `Filter.create(String)`的参数包含拼接输入
  - 认证方法中的字符串拼接
  - DN参数包含未转义输入
- **误报排除**：
  - 使用`Filter.encodeValue()`转义
  - 使用`Filter.createEqualityFilter()`等工厂方法
  - 使用`DN.escapeRDNValue()`转义DN

### 风险评估
- **高风险**：认证绕过、完整目录遍历
- **中风险**：限定条件注入
- **低风险**：仅只读，范围受限

## Low risk

### 低风险评级的情形

1. **使用Filter工厂方法**
   - `Filter.createEqualityFilter("uid", username)`
   - SDK负责转义（需确认版本）

2. **输入白名单验证**
   - 正则验证：仅允许字母数字
   - 枚举值验证

3. **只读操作**
   - 仅search/getEntry，无add/modify/delete

4. **属性限制**
   - SearchRequest指定返回属性
   - 不返回敏感字段
