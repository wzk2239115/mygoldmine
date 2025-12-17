# C LdapInit 搜索注入

## Details

### 代码示例
使用`ldap_init()`初始化连接后进行搜索，未转义输入会导致注入：

```c
#include <ldap.h>
#include <string.h>

// 危险示例1：基本搜索注入
LDAP* init_and_search(const char *username) {
    LDAP *ld;
    LDAPMessage *res;
    char filter[256];

    // 初始化连接
    ld = ldap_init("ldap.example.com", LDAP_PORT);
    if (ld == NULL) {
        return NULL;
    }

    // 绑定
    ldap_simple_bind_s(ld, "cn=admin,dc=example,dc=com", "password");

    // 危险：直接拼接用户输入
    sprintf(filter, "(uid=%s)", username);

    ldap_search_s(ld, "dc=example,dc=com", LDAP_SCOPE_SUBTREE,
                  filter, NULL, 0, &res);

    return ld;
}

// 危险示例2：从命令行参数
int main(int argc, char *argv[]) {
    if (argc < 2) {
        return 1;
    }

    LDAP *ld;
    LDAPMessage *result;
    char filter[512];

    // 危险：argv直接用于过滤器
    sprintf(filter, "(&(cn=%s)(objectClass=person))", argv[1]);

    ld = ldap_init("localhost", 389);
    ldap_simple_bind_s(ld, bind_dn, bind_pw);
    ldap_search_s(ld, base_dn, LDAP_SCOPE_SUBTREE, filter, NULL, 0, &result);

    // 处理结果...
    ldap_msgfree(result);
    ldap_unbind(ld);
}

// 危险示例3：从环境变量
void search_by_env() {
    char *username = getenv("LDAP_USER");
    char filter[256];

    if (username) {
        // 危险：环境变量未验证
        sprintf(filter, "(uid=%s)", username);

        LDAP *ld = ldap_init("localhost", 389);
        ldap_simple_bind_s(ld, admin_dn, admin_pw);
        ldap_search_s(ld, base_dn, LDAP_SCOPE_SUBTREE, filter, NULL, 0, &res);
    }
}

// 危险示例4：结构体字段
typedef struct {
    char username[128];
    char department[128];
} SearchParams;

int search_with_params(SearchParams *params) {
    char filter[512];

    // 危险：结构体字段未转义
    sprintf(filter, "(&(uid=%s)(department=%s))",
            params->username, params->department);

    LDAP *ld = ldap_init("localhost", 389);
    ldap_search_s(ld, base_dn, LDAP_SCOPE_SUBTREE, filter, NULL, 0, &res);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `ldap_init()`, `ldap_open()` 初始化函数
- `ldap_simple_bind_s()`, `ldap_bind_s()` 绑定函数
- `ldap_search_s()`, `ldap_search_ext_s()` 搜索函数
- `sprintf()`, `snprintf()` 格式化字符串
- `argv[]`, `getenv()`, `stdin` 输入源

重点检查文件：
```
src/main.c
src/ldap_utils.c
src/search.c
tools/ldap_cli.c
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 自定义转义函数的调用
- `strchr()`, `strpbrk()` 检查特殊字符
- `argc`, `argv` 参数验证
- 环境变量验证逻辑

**L3：逐行读** - 验证防护完整性：
```c
// 检查点1：是否验证输入
if (argc < 2 || strlen(argv[1]) > 64) {
    fprintf(stderr, "Invalid input\n");
    return 1;
}

// 检查是否有字符验证
for (int i = 0; argv[1][i]; i++) {
    if (!isalnum(argv[1][i])) {
        fprintf(stderr, "Invalid character\n");
        return 1;
    }
}

// 检查点2：是否使用转义函数
char escaped[256];
escape_filter(argv[1], escaped, sizeof(escaped));
sprintf(filter, "(uid=%s)", escaped);

// 检查点3：缓冲区大小
char filter[512];  // 是否足够大？
snprintf(filter, sizeof(filter), "(uid=%s)", username);  // 防溢出但不防注入
```

关键检查点：
- 是否验证命令行参数和环境变量
- sprintf vs snprintf（后者防溢出不防注入）
- 是否存在转义函数

## Classify

### 漏洞判定规则
- **明确漏洞**：`ldap_init()`后的搜索操作直接使用未转义的输入
- **高危信号**：
  - `argv[]`直接用于过滤器
  - `getenv()`的返回值直接拼接
  - 结构体字段未验证直接使用
- **误报排除**：
  - 输入经过字符白名单验证
  - 使用转义函数且实现正确
  - 过滤器来自配置文件

### 风险评估
- **高风险**：命令行工具或CGI程序的注入
- **中风险**：限定输入源的注入
- **低风险**：仅内部使用，输入受控

## Low risk

### 低风险评级的情形

1. **命令行参数验证**
   - 检查`argc`数量
   - 验证`argv[]`每个字符：`isalnum()`
   - 长度限制：`strlen(argv[1]) <= 32`

2. **环境变量验证**
   - 检查`getenv()`返回值非NULL
   - 验证内容格式

3. **仅内部工具**
   - 程序仅由管理员运行
   - 不暴露给外部用户

4. **只读LDAP操作**
   - 仅search，无modify/add
   - LDAP账户权限受限
