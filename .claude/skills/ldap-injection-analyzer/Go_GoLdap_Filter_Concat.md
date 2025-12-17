# Go go-ldap 过滤器拼接

## Details

### 代码示例
Go `go-ldap/ldap` 库在过滤器拼接时未转义会导致注入：

```go
package main

import (
    "github.com/go-ldap/ldap/v3"
    "github.com/gin-gonic/gin"
)

// 危险示例1：基本的过滤器拼接
func authenticateUser(username, password string) bool {
    conn, _ := ldap.Dial("tcp", "localhost:389")
    defer conn.Close()

    // 危险：fmt.Sprintf拼接
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
    return len(result.Entries) > 0
}

// 危险示例2：使用字符串拼接
func searchUsers(name, email string) []*ldap.Entry {
    // 危险：字符串拼接
    filter := "(&(cn=*" + name + "*)(mail=*" + email + "*))"

    searchReq := ldap.NewSearchRequest(
        baseDN, ldap.ScopeWholeSubtree,
        ldap.NeverDerefAliases, 0, 0, false,
        filter, []string{"dn", "cn", "mail"}, nil,
    )

    result, _ := conn.Search(searchReq)
    return result.Entries
}

// 危险示例3：Gin handler中的注入
func searchHandler(c *gin.Context) {
    username := c.Query("username")
    dept := c.PostForm("department")

    // 危险：直接使用用户输入
    filter := fmt.Sprintf("(&(uid=%s)(department=%s))", username, dept)

    // 执行搜索...
    c.JSON(200, gin.H{"filter": filter})
}

// 危险示例4：动态构造过滤器
func buildFilter(criteria map[string]string) string {
    var parts []string
    for key, value := range criteria {
        // 危险：key和value都未验证
        parts = append(parts, fmt.Sprintf("(%s=%s)", key, value))
    }
    return "(&" + strings.Join(parts, "") + ")"
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import "github.com/go-ldap/ldap/v3"`
- `ldap.Dial()`, `ldap.NewSearchRequest()`
- `conn.Search()`, `conn.Bind()`
- `c.Query()`, `c.PostForm()`, `c.Param()` Gin框架输入
- `fmt.Sprintf()`, 字符串拼接 `+`

重点检查文件：
```
handlers/auth.go
services/ldap_service.go
utils/ldap_utils.go
middleware/ldap_auth.go
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap.EscapeFilter()` 函数调用
- 自定义的 `escapeFilterValue()` 函数
- 正则验证：`regexp.MatchString()`
- 白名单映射

**L3：逐行读** - 验证防护完整性：
```go
import "github.com/go-ldap/ldap/v3"

// 检查点1：是否使用EscapeFilter
escaped := ldap.EscapeFilter(username)
filter := fmt.Sprintf("(uid=%s)", escaped)

// 检查点2：是否所有输入都转义
safeUser := ldap.EscapeFilter(username)
dept := department  // 未转义！
filter := fmt.Sprintf("(&(uid=%s)(dept=%s))", safeUser, dept)

// 检查点3：属性名是否白名单验证
allowedAttrs := map[string]bool{"uid": true, "cn": true, "mail": true}
if !allowedAttrs[attrName] {
    return errors.New("invalid attribute")
}
```

关键检查点：
- 过滤器字符串中的所有动态部分
- 是否使用 `ldap.EscapeFilter()`
- 属性名是否来自用户输入

## Classify

### 漏洞判定规则
- **明确漏洞**：`NewSearchRequest`的filter参数直接包含未转义的用户输入
- **高危信号**：
  - `fmt.Sprintf()`拼接用户输入
  - HTTP输入参数直接用于过滤器
  - map遍历构造过滤器
- **误报排除**：
  - 使用`ldap.EscapeFilter()`转义所有输入
  - 输入经过正则或白名单验证
  - 输入来自配置文件

### 风险评估
- **高风险**：认证绕过、完整目录遍历
- **中风险**：限定条件注入
- **低风险**：查询范围受限，返回属性白名单化

## Low risk

### 低风险评级的情形

1. **输入白名单验证**
   - 使用`regexp.MatchString("^[a-zA-Z0-9]+$", username)`
   - 仅允许预定义值

2. **属性返回限制**
   - `NewSearchRequest`的Attributes参数限制返回字段
   - 如`[]string{"cn", "displayName"}`

3. **Base DN范围限制**
   - Base DN限定为非敏感OU

4. **输入长度限制**
   - `username[:16]`截断输入
