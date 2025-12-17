# Go 动态表达式求值注入

**漏洞成因**：Go 语言虽然不提供内置的 `eval()` 函数，但部分第三方库（如 `govaluate`、`expr`、`cel-go`）提供表达式求值功能。当应用使用这些库解析和执行用户输入的表达式时，攻击者可构造恶意表达式访问变量、调用函数、执行复杂逻辑等，可能导致信息泄露、逻辑绕过或拒绝服务。常见于计算器、规则引擎、动态配置、条件判断等场景。

---

## Details

**代码示例**：
```go
// 危险：使用 govaluate 库执行用户输入的表达式
package main
import (
    "github.com/Knetic/govaluate"
    "net/http"
)

func handler(w http.ResponseWriter, r *http.Request) {
    userExpr := r.URL.Query().Get("expr")
    expression, _ := govaluate.NewEvaluableExpression(userExpr) // 危险：用户提供的表达式
    parameters := map[string]interface{}{"x": 10, "y": 20}
    result, _ := expression.Evaluate(parameters)
    // 用户可构造复杂表达式访问参数或进行逻辑操作
}

// 危险：使用 antonmedv/expr 库
import "github.com/antonmedv/expr"
program, _ := expr.Compile(userInput) // 危险：编译用户输入
output, _ := expr.Run(program, env)

// 危险：使用 CEL (Common Expression Language)
import "github.com/google/cel-go/cel"
env, _ := cel.NewEnv()
ast, _ := env.Compile(userInput) // 危险：用户可控的 CEL 表达式
prg, _ := env.Program(ast)
result, _ := prg.Eval(map[string]interface{}{})

// 攻击载荷示例（取决于库的能力）
// "x * 999999999 + y * 999999999"  // 拒绝服务
// "password == 'admin' || true"  // 逻辑绕过
// 复杂的嵌套表达式导致性能问题

// 较安全：限制表达式复杂度和长度
if len(userExpr) > 100 {
    http.Error(w, "Expression too long", http.StatusBadRequest)
    return
}

// 较安全：使用表达式白名单
allowedExpressions := []string{"x + y", "x * y", "x - y"}
if !contains(allowedExpressions, userExpr) {
    http.Error(w, "Invalid expression", http.StatusBadRequest)
    return
}

// 较安全：限制表达式中可访问的变量和函数
parameters := map[string]interface{}{
    "x": 10,
    "y": 20,
    // 不包含敏感数据或函数
}
```

**快速定位核心操作**：
- 关键词：`govaluate.NewEvaluableExpression`、`expr.Compile`、`cel.NewEnv`、`Evaluate()`、`Run()`
- 查找第三方表达式求值库的使用：`github.com/Knetic/govaluate`、`github.com/antonmedv/expr`、`github.com/google/cel-go`
- 追踪表达式字符串的来源，判断是否包含用户输入
- 检查表达式求值时传递的参数和环境对象
- 关注表达式的复杂度限制和超时设置
- 搜索 `go.mod` 文件中的相关依赖

**快速定位保护机制**：
- 表达式字符串是否来自可信的配置文件而非用户输入
- 是否对表达式长度和复杂度进行限制
- 是否使用表达式白名单验证
- 求值环境中是否仅包含必要的变量，不包含敏感数据
- 是否设置了表达式执行的超时时间
- 是否对表达式进行语法验证和安全检查
- 第三方库版本是否为最新稳定版

**审计等级**：**L2-L3**
- **L2**：跳读表达式求值代码，识别第三方库的使用
- **L3**：逐行验证表达式来源和环境配置，确认安全措施

---

## Classify

**确认为漏洞**：
- 使用表达式求值库执行用户输入的表达式
- 未对表达式长度和复杂度进行限制，可能导致 DoS
- 求值环境中包含敏感数据或功能
- 未设置表达式执行超时，可能导致资源耗尽
- 表达式可被用于逻辑绕过或信息泄露

**误报**：
- 表达式字符串来自可信的配置文件
- 使用表达式白名单，仅允许预定义的安全表达式
- 求值环境仅包含必要的、非敏感的变量
- 设置了合理的表达式长度限制和执行超时
- 对表达式进行了语法和安全检查

**代码异味**：
- 大量使用动态表达式求值，增加复杂度和风险
- 表达式字符串通过字符串拼接构造
- 求值环境中包含过多的变量和函数
- 缺乏对表达式执行的监控和日志记录

---

## Low Risk

以下情况可评为低风险：
- **表达式白名单**：仅允许执行预定义的安全表达式
- **复杂度限制**：设置表达式长度限制（如 100 字符）和嵌套深度限制
- **受限环境**：求值环境仅包含必要的数学变量，不包含敏感数据
- **执行超时**：设置表达式执行的超时时间（如 1 秒）
- **语法验证**：对表达式进行语法验证，拒绝非法表达式
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有表达式求值操作均记录日志并监控异常模式

**注意**：虽然 Go 的表达式求值库相对安全，但仍需控制表达式的复杂度和执行时间，避免 DoS 攻击和逻辑绕过。
