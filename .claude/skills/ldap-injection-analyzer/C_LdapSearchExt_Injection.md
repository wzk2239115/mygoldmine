# C LdapSearchExt 注入

## Details

### 代码示例
`ldap_search_ext_s()`是扩展搜索函数，同样存在注入风险：

```c
#include <ldap.h>

// 危险示例1：使用ldap_search_ext_s
int search_with_controls(const char *username, const char *dept) {
    LDAP *ld;
    LDAPMessage *res;
    char filter[512];
    LDAPControl **serverctrls = NULL;
    LDAPControl **clientctrls = NULL;
    struct timeval timeout = {10, 0};

    // 危险：sprintf拼接
    sprintf(filter, "(&(uid=%s)(department=%s))", username, dept);

    ld = ldap_init("localhost", 389);
    ldap_simple_bind_s(ld, admin_dn, admin_pw);

    int rc = ldap_search_ext_s(
        ld,
        "dc=example,dc=com",
        LDAP_SCOPE_SUBTREE,
        filter,              // 危险的过滤器
        NULL,                // attrs
        0,                   // attrsonly
        serverctrls,
        clientctrls,
        &timeout,
        LDAP_NO_LIMIT,
        &res
    );

    return rc;
}

// 危险示例2：分页搜索
int paged_search(const char *search_term) {
    char filter[256];
    LDAPControl *page_control = NULL;
    LDAPControl **controls = NULL;

    // 危险：未转义搜索词
    snprintf(filter, sizeof(filter), "(cn=*%s*)", search_term);

    // 创建分页控制
    ldap_create_page_control(ld, 100, NULL, 0, &page_control);

    controls = (LDAPControl **)malloc(2 * sizeof(LDAPControl *));
    controls[0] = page_control;
    controls[1] = NULL;

    ldap_search_ext_s(ld, base_dn, LDAP_SCOPE_SUBTREE,
                      filter, NULL, 0,
                      controls, NULL, NULL, 0, &res);
}

// 危险示例3：带属性选择
int search_specific_attrs(const char *uid) {
    char filter[256];
    char *attrs[] = {"dn", "cn", "mail", NULL};

    // 危险：虽然限制了返回属性，但过滤器仍可注入
    sprintf(filter, "(uid=%s)", uid);

    ldap_search_ext_s(ld, base_dn, LDAP_SCOPE_SUBTREE,
                      filter, attrs, 0,
                      NULL, NULL, NULL, 0, &res);
}

// 危险示例4：自定义base DN
int search_in_ou(const char *ou_name, const char *username) {
    char base[256];
    char filter[256];

    // 危险：base DN和过滤器都包含用户输入
    sprintf(base, "ou=%s,dc=example,dc=com", ou_name);
    sprintf(filter, "(uid=%s)", username);

    ldap_search_ext_s(ld, base, LDAP_SCOPE_SUBTREE,
                      filter, NULL, 0,
                      NULL, NULL, NULL, 0, &res);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `ldap_search_ext_s()`, `ldap_search_ext()`
- `LDAPControl`, `ldap_create_page_control()`
- `sprintf()`, `snprintf()` 构造过滤器
- base DN字符串拼接

重点检查文件：
```
src/ldap_search.c
src/paged_search.c
src/ldap_controls.c
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 转义函数调用
- base DN来自配置常量
- 属性返回列表限制（不防注入但降低影响）

**L3：逐行读** - 验证防护完整性：
```c
// 检查点1：过滤器转义
char escaped_uid[256];
escape_ldap_filter(uid, escaped_uid, sizeof(escaped_uid));
snprintf(filter, sizeof(filter), "(uid=%s)", escaped_uid);

// 检查点2：base DN是否固定
const char *base_dn = "dc=example,dc=com";  // 固定，安全
// vs
sprintf(base_dn, "ou=%s,dc=example,dc=com", user_input);  // 危险

// 检查点3：属性列表虽不防注入，但限制了泄露范围
char *safe_attrs[] = {"cn", "displayName", NULL};  // 不返回敏感字段
```

关键检查点：
- 过滤器参数的构造方式
- base DN是否包含用户输入
- 是否存在转义函数

## Classify

### 漏洞判定规则
- **明确漏洞**：`ldap_search_ext_s()`的filter或base参数直接拼接用户输入
- **高危信号**：
  - base DN包含用户输入
  - 过滤器使用sprintf/snprintf拼接
  - 分页搜索的过滤器未转义
- **误报排除**：
  - 过滤器经过转义函数处理
  - base DN来自配置文件
  - 输入经过严格验证

### 风险评估
- **高风险**：base DN注入+过滤器注入
- **中风险**：仅过滤器注入
- **低风险**：仅只读，返回属性受限

## Low risk

### 低风险评级的情形

1. **返回属性白名单**
   - `attrs`参数明确指定非敏感字段
   - 如`char *attrs[] = {"cn", "displayName", NULL}`

2. **base DN固定**
   - base DN来自`#define`或配置文件
   - 不包含用户输入

3. **分页控制不影响安全**
   - 虽然使用分页，但过滤器已正确转义

4. **超时和大小限制**
   - `timeout`和`sizelimit`参数限制查询
   - 虽不防注入但降低DoS风险
