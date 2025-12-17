# Go LdapV3 注入

## Details

### 代码示例
Go ldap.v3包在使用时如果不当会导致注入：

```go
import (
    "gopkg.in/ldap.v3"
    "net/http"
)

// 危险示例1：HTTP handler中的注入
func loginHandler(w http.ResponseWriter, r *http.Request) {
    username := r.FormValue("username")
    password := r.FormValue("password")

    conn, _ := ldap.Dial("tcp", "localhost:389")
    defer conn.Close()

    // 危险：直接拼接
    filter := fmt.Sprintf("(&(uid=%s)(userPassword=%s))", username, password)

    searchRequest := ldap.NewSearchRequest(
        "dc=example,dc=com",
        ldap.ScopeWholeSubtree,
        ldap.NeverDerefAliases,
        0, 0, false,
        filter,
        []string{"dn"},
        nil,
    )

    result, _ := conn.Search(searchRequest)
    if len(result.Entries) > 0 {
        w.Write([]byte("Login successful"))
    }
}

// 危险示例2：动态base DN
func searchInOU(ouName, filter string) []*ldap.Entry {
    // 危险：base DN包含用户输入
    baseDN := fmt.Sprintf("ou=%s,dc=example,dc=com", ouName)

    searchReq := ldap.NewSearchRequest(
        baseDN,
        ldap.ScopeWholeSubtree,
        ldap.NeverDerefAliases,
        0, 0, false,
        filter,
        []string{"*"},
        nil,
    )

    result, _ := conn.Search(searchReq)
    return result.Entries
}

// 危险示例3：复杂过滤器构造
type SearchCriteria struct {
    Name       string
    Department string
    Role       string
}

func buildSearchFilter(criteria SearchCriteria) string {
    var filters []string

    if criteria.Name != "" {
        // 危险：未转义
        filters = append(filters, fmt.Sprintf("(cn=*%s*)", criteria.Name))
    }
    if criteria.Department != "" {
        filters = append(filters, fmt.Sprintf("(department=%s)", criteria.Department))
    }
    if criteria.Role != "" {
        filters = append(filters, fmt.Sprintf("(role=%s)", criteria.Role))
    }

    return "(&" + strings.Join(filters, "") + ")"
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import "gopkg.in/ldap.v3"`
- `ldap.Dial()`, `ldap.NewSearchRequest()`
- `r.FormValue()`, `r.URL.Query().Get()`, `r.PostFormValue()`
- `fmt.Sprintf()`, 字符串拼接

重点检查文件：
```
handlers/*.go
services/*_service.go
pkg/ldap/*.go
api/*.go
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap.EscapeFilter()` 调用
- 正则验证
- 白名单检查

**L3：逐行读** - 验证防护完整性：
```go
// 检查点1：EscapeFilter使用
escaped := ldap.EscapeFilter(username)
filter := fmt.Sprintf("(uid=%s)", escaped)

// 检查点2：base DN是否包含用户输入
// 需自定义DN转义函数
func escapeDN(value string) string {
    // 实现DN转义
}

// 检查点3：条件分支是否都转义
if name != "" {
    safeNameldap.EscapeFilter(name)
    filters = append(filters, fmt.Sprintf("(cn=%s)", safeName))
}
```

关键检查点：
- 所有动态内容是否转义
- base DN是否包含用户输入
- 条件构造是否有遗漏

## Classify

### 漏洞判定规则
- **明确漏洞**：filter或base DN直接包含未转义的HTTP输入
- **高危信号**：
  - 认证handler中的注入
  - base DN动态构造
  - 结构体字段直接用于过滤器
- **误报排除**：
  - 所有输入使用`ldap.EscapeFilter()`
  - base DN固定或来自配置
  - 输入严格验证

### 风险评估
- **高风险**：认证绕过、目录遍历
- **中风险**：限定条件注入
- **低风险**：范围受限

## Low risk

### 低风险评级的情形

1. **输入验证**
   - `regexp.MatchString()`验证格式
   - 白名单检查

2. **Base DN固定**
   - Base DN来自配置，不含用户输入

3. **属性白名单**
   - Attributes参数限制返回字段

4. **只读操作**
   - 仅Search，无Modify/Add/Delete
