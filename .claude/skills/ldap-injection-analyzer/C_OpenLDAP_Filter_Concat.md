# C OpenLDAP 过滤器拼接

## Details

### 代码示例
C语言使用OpenLDAP客户端库时，字符串拼接容易引入注入：

```c
#include <ldap.h>
#include <stdio.h>
#include <string.h>

// 危险示例1：sprintf拼接过滤器
int authenticate_user(const char *username, const char *password) {
    LDAP *ld;
    LDAPMessage *result;
    char filter[256];

    // 危险：sprintf直接拼接
    sprintf(filter, "(&(uid=%s)(userPassword=%s))", username, password);

    ld = ldap_init("localhost", 389);
    ldap_simple_bind_s(ld, "cn=admin,dc=example,dc=com", "adminpw");

    int rc = ldap_search_s(ld, "dc=example,dc=com", LDAP_SCOPE_SUBTREE,
                           filter, NULL, 0, &result);

    return (rc == LDAP_SUCCESS && ldap_count_entries(ld, result) > 0);
}

// 危险示例2：strcat拼接
void search_users(const char *name, const char *dept) {
    char filter[512] = "(&(cn=*";

    // 危险：strcat拼接未转义内容
    strcat(filter, name);
    strcat(filter, "*)(department=");
    strcat(filter, dept);
    strcat(filter, "))");

    ldap_search_s(ld, base_dn, LDAP_SCOPE_SUBTREE, filter, NULL, 0, &result);
}

// 危险示例3：snprintf但未转义
int find_by_uid(const char *uid) {
    char filter[256];
    char dn[512];

    // 危险：虽然用了snprintf防溢出，但未转义内容
    snprintf(filter, sizeof(filter), "(uid=%s)", uid);
    snprintf(dn, sizeof(dn), "uid=%s,ou=users,dc=example,dc=com", uid);

    ldap_search_s(ld, dn, LDAP_SCOPE_BASE, filter, NULL, 0, &result);
}

// 危险示例4：从CGI获取输入
#include <stdlib.h>

void cgi_search() {
    char *query_string = getenv("QUERY_STRING");
    char username[128] = {0};
    char filter[256];

    // 解析username参数（简化示例）
    sscanf(query_string, "username=%127s", username);

    // 危险：直接使用用户输入
    sprintf(filter, "(uid=%s)", username);

    ldap_search_s(ld, "dc=example,dc=com", LDAP_SCOPE_SUBTREE, filter, NULL, 0, &result);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `#include <ldap.h>`
- `ldap_search_s()`, `ldap_search_ext_s()`, `ldap_search_st()`
- `sprintf()`, `snprintf()`, `strcat()`, `strncat()`
- 字符串拼接构造过滤器或DN
- `getenv()`, `argv[]` 等输入源

重点检查文件：
```
src/ldap_client.c
src/auth.c
cgi-bin/*.c
src/directory_util.c
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 自定义转义函数：`escape_ldap_filter()`, `escape_dn()`
- 输入验证：`isalnum()`, `strcspn()` 检查特殊字符
- 白名单检查：`strcmp()` 与预定义值比较
- 使用安全字符串函数：`strncpy()`, `strlcpy()`（虽然不能防注入）

**L3：逐行读** - 验证防护完整性：
```c
// 检查点1：是否有自定义转义函数
char* escape_ldap_filter(const char *input) {
    // 检查此函数实现是否正确转义所有LDAP元字符
    // 应转义: *, (, ), \, NUL
}

// 检查点2：缓冲区大小是否足够
char escaped[1024];
escape_ldap_filter(username, escaped, sizeof(escaped));
sprintf(filter, "(uid=%s)", escaped);

// 检查点3：是否所有输入都被转义
char safe_user[256];
escape_ldap_filter(username, safe_user, sizeof(safe_user));
// 但department未转义！
sprintf(filter, "(&(uid=%s)(dept=%s))", safe_user, department);
```

关键检查点：
- 过滤器构造是否使用sprintf/strcat等危险函数
- 是否存在自定义转义函数及其实现
- 缓冲区大小是否防止溢出（虽不防注入但也重要）
- 所有用户输入是否都被转义

## Classify

### 漏洞判定规则
- **明确漏洞**：`ldap_search*()`的filter参数使用sprintf/strcat直接拼接用户输入
- **高危信号**：
  - 使用`sprintf()`或`strcat()`构造过滤器
  - CGI程序从`getenv("QUERY_STRING")`获取输入后直接使用
  - DN字符串包含未转义输入
- **误报排除**：
  - 使用自定义转义函数且实现正确
  - 输入经过严格的字符白名单验证
  - 输入来自配置文件或常量

### 风险评估
- **高风险**：认证绕过、缓冲区溢出+注入
- **中风险**：限定条件注入
- **低风险**：仅只读操作，范围受限

## Low risk

### 低风险评级的情形

1. **输入字符白名单**
   - 使用`isalnum()`验证每个字符
   - 拒绝所有特殊字符：`*`, `(`, `)`, `&`, `|`, `\`

2. **固定的过滤器**
   - 过滤器来自配置文件，不包含用户输入
   - 用户输入仅用于后续的结果过滤

3. **只读操作**
   - 仅使用`ldap_search*()`，无`ldap_add()`, `ldap_modify()`
   - LDAP连接使用只读账户

4. **转义函数正确实现**
   - 自定义`escape_ldap_filter()`函数正确转义所有元字符
   - 所有输入都经过此函数处理
