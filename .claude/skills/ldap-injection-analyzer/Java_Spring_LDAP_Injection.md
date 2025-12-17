# Spring LDAP 注入

## Details

### 代码示例
Spring LDAP框架如果使用不当仍可能引入注入：

```java
import org.springframework.ldap.core.LdapTemplate;
import org.springframework.ldap.query.LdapQueryBuilder;

// 危险示例1：使用字符串过滤器
@Service
public class UserService {
    @Autowired
    private LdapTemplate ldapTemplate;

    public List<User> findUsers(String username) {
        // 危险：直接拼接过滤器
        String filter = "(uid=" + username + ")";
        return ldapTemplate.search("", filter, new UserAttributeMapper());
    }
}

// 危险示例2：部分使用查询构造器
public User authenticate(String uid, String dept) {
    // 危险：where子句安全，但andFilter不安全
    return ldapTemplate.searchForObject(
        query().where("uid").is(uid)  // 安全
               .and("(department=" + dept + ")"),  // 危险！
        userMapper
    );
}

// 危险示例3：自定义AttributeMapper中的注入
public class UserMapper implements AttributeMapper<User> {
    public User mapFromAttributes(Attributes attrs, String filter) {
        // filter参数可能包含未转义输入
        // 如果在这里再次构造LDAP查询，可能导致二次注入
    }
}

// 危险示例4：使用AndFilter但传入未转义字符串
public List<User> search(String name, String email) {
    AndFilter filter = new AndFilter();
    filter.and(new EqualsFilter("cn", name));  // 看似安全
    // 但如果name包含特殊字符，EqualsFilter可能无法正确转义（需验证版本）
    filter.and(new EqualsFilter("mail", email));
    return ldapTemplate.search("", filter.encode(), userMapper);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `@Autowired LdapTemplate`, `LdapTemplate.search()`
- `LdapQueryBuilder`, `query().where()`
- `@RequestParam`, `@PathVariable` Spring MVC注解
- `AndFilter`, `OrFilter`, `EqualsFilter`
- 字符串拼接：`+`, `String.format()`

重点检查文件：
```
src/main/java/**/service/*Service.java
src/main/java/**/repository/*Repository.java
src/main/java/**/controller/*Controller.java
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 纯粹使用`query().where().is()`链式调用
- `LdapEncoder.filterEncode()`调用
- `@Valid`配合Bean Validation
- `EqualsFilter`, `LikeFilter`等过滤器类的使用

**L3：逐行读** - 验证防护完整性：
```java
// 检查点1：是否完全使用查询构造器
ldapTemplate.search(
    query().where("uid").is(username),  // 参数化，安全
    userMapper
);

// 检查点2：是否混合使用
query().where("uid").is(uid)
       .and("(dept=" + dept + ")")  // 危险！

// 检查点3：EqualsFilter是否正确转义（取决于Spring LDAP版本）
EqualsFilter filter = new EqualsFilter("uid", username);
// 需要查阅版本文档确认是否自动转义
```

关键检查点：
- 是否纯粹使用Spring LDAP的查询构造器API
- 是否存在字符串过滤器的混合使用
- 过滤器类（EqualsFilter等）的版本是否安全

## Classify

### 漏洞判定规则
- **明确漏洞**：`ldapTemplate.search()`使用字符串过滤器，包含未转义输入
- **高危信号**：
  - 字符串拼接构造过滤器
  - `query().and()`传入字符串而非Filter对象
  - 认证服务中的过滤器拼接
- **误报排除**：
  - 完全使用`query().where().is()`参数化接口
  - 使用`LdapEncoder.filterEncode()`转义
  - `@Valid`验证且规则覆盖LDAP特殊字符

### 风险评估
- **高风险**：认证绕过、权限提升、数据泄露
- **中风险**：部分参数可注入，影响受限
- **低风险**：主要使用参数化接口，仅次要参数可能有问题

## Low risk

### 低风险评级的情形

1. **完全使用查询构造器**
   - 所有查询使用`query().where().is()`
   - 未使用字符串过滤器
   - 依赖Spring LDAP的内部转义

2. **Bean Validation验证**
   - DTO使用`@Pattern`, `@Size`等注解
   - `@Valid`在Controller层自动验证
   - 无效输入被自动拒绝

3. **只读操作**
   - 仅使用`search()`, `lookup()`
   - 未使用`bind()`, `unbind()`, `modifyAttributes()`

4. **属性白名单**
   - `setReturningAttributes()`限制返回字段
   - 仅返回非敏感属性
