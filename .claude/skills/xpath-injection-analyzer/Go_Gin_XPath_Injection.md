# Go - Gin 框架 XPath 注入

## Details

### 漏洞成因
Gin 是 Go 生态中流行的高性能 web 框架。当 Gin 应用使用 XPath 库（如 `antchfx/xmlquery`）进行 XML 数据查询时，从 Gin 的上下文对象（`c.Query()`, `c.PostForm()`, `c.Param()`）获取的用户输入若直接通过字符串拼接嵌入 XPath 表达式，将导致注入漏洞。Gin 的中间件机制如果未正确配置验证中间件，无法自动防御此类注入。常见于 REST API、XML 数据处理和 SOAP 客户端集成。

代码示例：
```go
import (
    "github.com/gin-gonic/gin"
    "github.com/antchfx/xmlquery"
)

func searchHandler(c *gin.Context) {
    username := c.Query("username")
    password := c.PostForm("password")

    doc, _ := xmlquery.LoadURL("users.xml")
    expr := "//user[username='" + username + "' and password='" + password + "']"
    node := xmlquery.FindOne(doc, expr)

    if node != nil {
        c.JSON(200, gin.H{"status": "success"})
    }
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import "github.com/gin-gonic/gin"`, `gin.Context`, `*gin.Context`
- `c.Query()`, `c.PostForm()`, `c.Param()`, `c.GetQuery()`, `c.DefaultQuery()`
- `xmlquery.Find()`, `xmlquery.FindOne()`, `xmlquery.QueryAll()`
- 字符串拼接：`+`, `fmt.Sprintf()`, `strings.Builder`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **Gin 验证中间件** (L2 跳读) - 检查 `binding` 标签, `ShouldBind()`, `ShouldBindJSON()`
- **自定义中间件** (L2 跳读) - 查找 `router.Use()`, 自定义验证中间件函数
- **验证函数** (L3 逐行读) - 检查 `validator` 包使用, `regexp.MatchString()` 验证
- **转义实现** (L3 逐行读) - 检查自定义 `sanitize()` 或 `escapeXPath()` 函数
- **服务层追踪** (L4) - 从 Gin handler 到 service 层的数据流，检查业务逻辑层的处理

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. Gin 上下文对象的用户输入通过字符串拼接嵌入 XPath 表达式
2. 未使用 Gin 的 binding 验证或验证不严格
3. 无有效的转义或参数化机制
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、配置）

**误报情况**：
- 用户输入通过 `ShouldBind()` 绑定到 struct 且有 `binding` 标签验证
- 使用 `validator` 包的自定义验证规则
- 拼接的数据来自配置文件或已认证的会话
- XML 数据为公开的静态资源

**代码异味**：
- 使用 `c.DefaultQuery()` 提供默认值但未验证输入
- binding 标签存在但验证不严格（如仅 `required`）
- 在 handler 中直接处理 XPath，未通过 service 层封装
- 自定义转义函数但未覆盖所有特殊字符

## Low risk

### 低风险评级场景

1. **Binding 验证** - 使用 Gin 的 struct binding 且有严格的验证标签
   - 例：`type Query struct { Field string \`form:"field" binding:"alphanum,max=20"\` }`

2. **自定义验证器** - 使用 `validator` 包注册自定义验证函数
   - 例：`binding.Validator.Engine().(*validator.Validate).RegisterValidation("xpath_safe", ...)`

3. **枚举值验证** - 输入限制为预定义的枚举值
   - 例：`if !contains([]string{"name", "email"}, field) { c.AbortWithStatus(400) }`

4. **整数转换** - 输入经过 `strconv.Atoi()` 强制转换
   - 例：`id, err := strconv.Atoi(c.Param("id")); if err != nil { return }`

5. **非敏感数据** - XML 数据为公开的产品目录或配置

6. **认证中间件** - 路由通过 JWT 或 session 中间件保护

7. **结果过滤** - 查询结果经过权限检查或数据脱敏

8. **速率限制** - 存在速率限制中间件，降低攻击效率
