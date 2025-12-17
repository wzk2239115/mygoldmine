# Apache Directory DN 注入

## Details

### 代码示例
Apache Directory API在DN操作时如果未正确转义会导致注入：

```java
import org.apache.directory.api.ldap.model.name.Dn;
import org.apache.directory.api.ldap.model.name.Rdn;
import org.apache.directory.ldap.client.api.*;

// 危险示例1：DN字符串拼接
public void addUser(String cn, String ou) throws Exception {
    // 危险：直接拼接DN字符串
    String dnStr = "cn=" + cn + ",ou=" + ou + ",dc=example,dc=com";
    Dn dn = new Dn(dnStr);  // 解析不等于转义
    Entry entry = new DefaultEntry(dn);
    connection.add(entry);
}

// 危险示例2：search的base DN注入
public List<Entry> searchInOU(String ouName) throws Exception {
    String baseDn = "ou=" + ouName + ",dc=example,dc=com";  // 危险
    EntryCursor cursor = connection.search(baseDn, "(objectClass=*)", SearchScope.ONELEVEL);
    return processCursor(cursor);
}

// 危险示例3：过滤器注入
public boolean authenticate(String username, String password) throws Exception {
    // 危险：过滤器未转义
    String filter = "(&(uid=" + username + ")(userPassword=" + password + "))";
    SearchCursor cursor = connection.search("dc=example,dc=com", filter, SearchScope.SUBTREE);
    return cursor.next();
}

// 危险示例4：Modify操作的DN注入
public void updateUser(String uid, String newMail) throws Exception {
    String dn = "uid=" + uid + ",ou=users,dc=example,dc=com";  // 危险
    Modification mod = new DefaultModification(ModificationOperation.REPLACE_ATTRIBUTE, "mail", newMail);
    connection.modify(dn, mod);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import org.apache.directory.api.ldap.*`
- `LdapConnection`, `LdapNetworkConnection`
- `.search()`, `.add()`, `.modify()`, `.delete()`
- `new Dn()`, `new Rdn()`
- 字符串拼接：`+`, `String.format()`, `StringBuilder`

重点检查文件：
```
src/main/java/**/ldap/*Connection*.java
src/main/java/**/directory/*Service.java
src/main/java/**/repository/*LdapRepository.java
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `Rdn.escapeValue()`方法调用
- `FilterEncoder.encodeFilterValue()`使用
- 使用`Dn`和`Rdn`类的构造方法而非字符串拼接
- 输入验证逻辑

**L3：逐行读** - 验证防护完整性：
```java
// 检查点1：正确使用Rdn.escapeValue
import org.apache.directory.api.ldap.model.name.Rdn;
String safeCn = Rdn.escapeValue(cn).toString();
Dn dn = new Dn("cn=" + safeCn + ",ou=users,dc=example,dc=com");

// 检查点2：使用Rdn构造器
Rdn rdn = new Rdn("cn", cn);  // 构造器会自动转义吗？需验证
Dn dn = new Dn(rdn, new Dn("ou=users,dc=example,dc=com"));

// 检查点3：过滤器转义
import org.apache.directory.api.ldap.model.filter.FilterEncoder;
String safe = FilterEncoder.encodeFilterValue(username);
String filter = "(uid=" + safe + ")";
```

关键检查点：
- DN字符串是否直接拼接
- 是否区分DN转义和过滤器转义
- base DN是否包含用户输入

## Classify

### 漏洞判定规则
- **明确漏洞**：DN或过滤器字符串直接拼接未转义的用户输入
- **高危信号**：
  - `new Dn(String)`的参数包含拼接的用户输入
  - search的base DN或filter包含未转义输入
  - add/modify/delete的DN参数未转义
- **误报排除**：
  - 使用`Rdn.escapeValue()`转义DN组件
  - 使用`FilterEncoder.encodeFilterValue()`转义过滤器
  - 输入经过严格验证

### 风险评估
- **高风险**：完整的LDAP注入，可读写目录
- **中风险**：限定操作类型的注入
- **低风险**：仅只读操作，范围受限

## Low risk

### 低风险评级的情形

1. **只读操作**
   - 仅使用search/lookup，未使用add/modify/delete
   - 即使注入也无法修改目录

2. **DN来自配置**
   - base DN从配置文件读取
   - 用户输入仅用于过滤器值部分

3. **输入严格验证**
   - 使用`Pattern.matches()`验证输入
   - 白名单限制：仅允许字母数字

4. **连接权限受限**
   - LDAP连接使用只读账户
   - 无write权限，注入无法造成数据篡改
