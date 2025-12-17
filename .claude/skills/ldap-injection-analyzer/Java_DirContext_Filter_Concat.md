# Java DirContext 过滤器拼接

## Details

### 代码示例
Java JNDI DirContext 接口用于LDAP操作，未转义的过滤器拼接会导致注入：

```java
import javax.naming.directory.*;
import javax.naming.ldap.*;

// 危险示例1：基本的过滤器拼接
public User authenticate(String username, String password) {
    String filter = "(&(uid=" + username + ")(userPassword=" + password + "))";  // 危险
    SearchControls controls = new SearchControls();
    NamingEnumeration<SearchResult> results = ctx.search("dc=example,dc=com", filter, controls);
    return processResults(results);
}

// 危险示例2：使用String.format
public List<User> searchUsers(String department, String role) {
    String filter = String.format("(&(dept=%s)(role=%s))", department, role);  // 危险
    return ldapTemplate.search("", filter, userMapper);
}

// 危险示例3：StringBuilder拼接
public boolean checkMembership(HttpServletRequest request) {
    String username = request.getParameter("username");
    String group = request.getParameter("group");

    StringBuilder filter = new StringBuilder();
    filter.append("(&(uid=").append(username).append(")");  // 危险
    filter.append("(memberOf=cn=").append(group).append(",ou=groups,dc=example,dc=com))");

    return ldapSearch(filter.toString());
}

// 危险示例4：初始上下文参数
Hashtable<String, String> env = new Hashtable<>();
String user = request.getParameter("user");
env.put(Context.SECURITY_PRINCIPAL, "uid=" + user + ",ou=users,dc=example,dc=com");  // DN注入
DirContext ctx = new InitialDirContext(env);
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import javax.naming.directory.*`, `DirContext`, `SearchControls`
- `.search()` 方法调用
- `request.getParameter()`, `@PathVariable`, `@RequestParam` 等输入获取
- 字符串拼接：`+` 操作符，`String.format()`, `StringBuilder.append()`
- LDAP过滤器模式：`"(&"`, `"(|"`, `"(uid="`, `"(cn="`

重点检查文件：
```
src/main/java/com/*/service/*LdapService.java
src/main/java/com/*/controller/*AuthController.java
src/main/java/com/*/util/*DirectoryUtil.java
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `LdapEncoder.filterEncode()` (Spring Security)
- `Filter.encodeValue()` (Apache Directory API)
- 自定义的转义方法
- LdapTemplate的参数化查询

**L3：逐行读** - 验证防护完整性：
```java
// 检查点1：是否使用了转义
import org.springframework.security.ldap.LdapEncoder;
String escaped = LdapEncoder.filterEncode(username);
String filter = "(uid=" + escaped + ")";

// 检查点2：是否所有参数都被转义
String user = LdapEncoder.filterEncode(username);
String dept = department;  // 未转义！
String filter = "(&(uid=" + user + ")(dept=" + dept + "))";

// 检查点3：是否使用参数化查询
ldapTemplate.search(
    query().where("uid").is(username),  // 参数化，安全
    userMapper
);
```

关键检查点：
- 过滤器字符串中的所有动态部分
- DN参数是否包含用户输入
- 是否使用了LdapTemplate的参数化接口

## Classify

### 漏洞判定规则
- **明确漏洞**：`ctx.search()` 的filter参数直接拼接未转义的用户输入
- **高危信号**：
  - 认证方法中的过滤器拼接
  - SECURITY_PRINCIPAL包含用户输入
  - 使用`+`或`String.format()`构造过滤器
- **误报排除**：
  - 使用`LdapEncoder.filterEncode()`转义所有输入
  - 使用Spring LdapTemplate的参数化查询
  - 输入经过严格的白名单验证

### 风险评估
- **高风险**：认证绕过、权限提升、完整目录遍历
- **中风险**：限定条件下的信息泄露
- **低风险**：查询范围受限，返回属性白名单化

## Low risk

### 低风险评级的情形

1. **输入白名单验证**
   - 使用枚举或预定义常量
   - Pattern.matches验证：`"^[a-zA-Z0-9]+$"`
   - 无法注入特殊字符

2. **属性返回限制**
   - SearchControls指定返回属性：`setReturningAttributes(new String[]{"cn", "displayName"})`
   - 不返回敏感信息

3. **Base DN范围限制**
   - 搜索限定在非敏感OU
   - 如`ou=public,dc=example,dc=com`

4. **使用LdapTemplate参数化**
   - Spring LdapTemplate的`query().where()`方法
   - 库负责转义
