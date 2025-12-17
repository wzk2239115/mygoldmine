# Go Gin LDAP 身份认证注入

## Details

### 代码示例
Gin 框架中常使用 `go-ldap/ldap` 库进行 LDAP 认证。以下是常见易受攻击模式：

```go
package main

import (
	"fmt"
	"github.com/gin-gonic/gin"
	"github.com/go-ldap/ldap/v3"
)

func authenticate(c *gin.Context) {
	username := c.PostForm("username")  // 用户输入
	password := c.PostForm("password")

	// 危险：直接拼接用户输入到过滤器
	filter := fmt.Sprintf("(&(uid=%s)(userPassword=%s))", username, password)

	conn, _ := ldap.Dial("tcp", "localhost:389")
	defer conn.Close()

	searchRequest := ldap.NewSearchRequest(
		"ou=users,dc=example,dc=com",
		ldap.ScopeWholeSubtree,
		ldap.NeverDerefAliases,
		0,
		0,
		false,
		filter,  // 未转义的过滤器
		[]string{"dn"},
		nil,
	)
	conn.Search(searchRequest)
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 检查以下特征：
- `c.PostForm()`, `c.Param()`, `c.Query()` 等获取用户输入
- `fmt.Sprintf()` 或 `+` 操作符构造过滤器字符串
- `ldap.Dial()`, `ldap.NewSearchRequest()` 等 LDAP 操作
- `filter` 变量中包含用户输入

重点检查文件：
```
handlers/auth.go            - 认证处理函数
utils/ldap.go              - LDAP 操作工具
middleware/auth.go         - 认证中间件
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap.EscapeFilter()` 或 `escapeFilterValue()` 的调用
- 自定义的转义函数实现
- 正则表达式验证用户输入

**L3：逐行读** - 验证防护完整性：
```go
// 安全的防护方式
import "github.com/go-ldap/ldap/v3"
filter := fmt.Sprintf("(&(uid=%s))", ldap.EscapeFilter([]string{username})[0])

// 或检查转义函数的实现
escapedUsername := escapeFilter(username)
```

关键检查点：
- `EscapeFilter()` 是否正确处理所有元字符
- 转义是否在 `fmt.Sprintf()` 之前应用
- 是否存在多处过滤器拼接的情况

## Classify

### 漏洞判定规则
- **明确漏洞**：`fmt.Sprintf()` 直接拼接用户输入到 LDAP 过滤器
- **高危信号**：HTTP 输入参数（`PostForm`, `Param`, `Query`）直接用于过滤器
- **误报排除**：
  - 使用了 `ldap.EscapeFilter()` 对所有用户输入进行转义
  - 输入通过严格的白名单验证（长度、字符集）
  - 使用了业界成熟的 LDAP 认证中间件

### 风险评估
- **高风险**：可通过 `*`, `(&`, `|)` 等构造任意 LDAP 查询，绕过认证或权限提升
- **中风险**：过滤器结构固定，仅特定参数可注入，限制了攻击面
- **低风险**：输入长度或字符集受严格限制，无法注入有效的 LDAP 语法

## Low risk

### 低风险评级的情形

1. **输入白名单验证**
   - 正则表达式要求仅字母数字：`^[a-zA-Z0-9]{1,32}$`
   - 长度限制在 8 字符以内

2. **库级别的防护**
   - 使用了官方库的参数化接口
   - `ldap.EscapeFilter()` 被正确应用于所有用户输入字段

3. **业务逻辑限制**
   - LDAP 查询结果仅用于存在性检查，不影响权限决策
   - 后续验证使用了额外的 hash 比对或 MFA
