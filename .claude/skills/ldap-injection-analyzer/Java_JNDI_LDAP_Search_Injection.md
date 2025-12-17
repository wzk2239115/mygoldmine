# Java JNDI LDAP 搜索注入

## Details

### 代码示例
JNDI LDAP查询如果直接拼接用户输入会导致注入：

```java
import javax.naming.*;
import javax.naming.ldap.*;

// 危险示例1：JNDI搜索注入
public User findUser(String username) throws NamingException {
    InitialLdapContext ctx = getLdapContext();
    String filter = "(uid=" + username + ")";  // 危险
    SearchControls ctrl = new SearchControls();
    ctrl.setSearchScope(SearchControls.SUBTREE_SCOPE);
    NamingEnumeration<SearchResult> results = ctx.search("dc=example,dc=com", filter, ctrl);
    //...
}

// 危险示例2：动态DN构造
@PostMapping("/addUser")
public String addUser(@RequestParam String cn, @RequestParam String ou) {
    String dn = "cn=" + cn + ",ou=" + ou + ",dc=example,dc=com";  // DN注入
    Attributes attrs = new BasicAttributes();
    ctx.createSubcontext(dn, attrs);
}

// 危险示例3：复杂过滤器拼接
public List<User> advancedSearch(Map<String, String> criteria) {
    StringBuilder filter = new StringBuilder("(&");
    for (Map.Entry<String, String> entry : criteria.entrySet()) {
        // 危险：key和value都未验证
        filter.append("(").append(entry.getKey()).append("=").append(entry.getValue()).append(")");
    }
    filter.append(")");
    return search(filter.toString());
}

// 危险示例4：使用用户输入作为base DN
public void searchInOU(String ouName, String filter) {
    String baseDn = "ou=" + ouName + ",dc=example,dc=com";  // 危险
    ctx.search(baseDn, filter, controls);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `InitialLdapContext`, `InitialDirContext`, `LdapContext`
- `.search()`, `.createSubcontext()`, `.modifyAttributes()`
- `@RequestParam`, `@PathVariable`, `HttpServletRequest.getParameter()`
- 字符串拼接构造过滤器或DN

重点检查文件：
```
src/main/java/**/ldap/*.java
src/main/java/**/auth/*.java
src/main/java/**/directory/*.java
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `javax.naming.ldap.Rdn.escapeValue()`
- Apache Directory API的`Filter.encodeValue()`
- 输入验证框架：Bean Validation注解

**L3：逐行读** - 验证防护完整性：
```java
// 检查点1：DN转义
import javax.naming.ldap.Rdn;
String safeCn = Rdn.escapeValue(cn);
String dn = "cn=" + safeCn + ",ou=users,dc=example,dc=com";

// 检查点2：过滤器转义
String safeUid = escapeFilterValue(username);  // 检查此函数实现
String filter = "(uid=" + safeUid + ")";

// 检查点3：属性名白名单
Set<String> allowedAttrs = Set.of("uid", "cn", "mail");
if (!allowedAttrs.contains(attrName)) {
    throw new IllegalArgumentException("Invalid attribute");
}
```

关键检查点：
- DN和过滤器是否分别使用正确的转义方法
- 属性名是否来自用户输入
- 是否混用DN转义和过滤器转义

## Classify

### 漏洞判定规则
- **明确漏洞**：`ctx.search()`或DN构造直接包含未转义的用户输入
- **高危信号**：
  - base DN包含用户输入
  - 过滤器使用`+`或`StringBuilder`拼接
  - `createSubcontext()`的DN参数包含用户输入
- **误报排除**：
  - 使用`Rdn.escapeValue()`转义DN组件
  - 使用过滤器转义函数
  - 输入经过Bean Validation验证

### 风险评估
- **高风险**：认证绕过、目录写入、完整遍历
- **中风险**：限定条件下的注入
- **低风险**：转义覆盖主要参数，范围受限

## Low risk

### 低风险评级的情形

1. **Bean Validation验证**
   - 使用`@Pattern(regexp="^[a-zA-Z0-9]+$")`
   - `@Size(max=32)`长度限制
   - 验证失败时请求被拒绝

2. **只读操作**
   - 仅使用`search()`读取
   - 未使用`createSubcontext()`, `modifyAttributes()`等写操作

3. **Base DN固定**
   - Base DN来自配置文件，不包含用户输入
   - 如`env.getProperty("ldap.baseDn")`

4. **SearchControls限制**
   - `setCountLimit(100)`限制结果数
   - `setReturningAttributes()`限制返回属性
