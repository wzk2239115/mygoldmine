# Go AST 解析代码执行注入

## 漏洞成因

Go 的 `go/parser` 和 `go/ast` 包用于解析和操作 Go 源代码的抽象语法树。当用户可控的输入被用作待解析的 Go 代码时，攻击者可注入恶意代码。虽然 AST 解析本身不直接执行代码，但经由 `reflect` 包、脚本引擎、代码生成工具、或再次编译执行，可导致代码执行。此外，AST 遍历和修改过程中可能存在逻辑漏洞，如 unsafe pointer 转换、cgo 调用等。

---

## Details

### 代码示例

```go
package main

import (
    "fmt"
    "go/ast"
    "go/parser"
    "go/token"
    "io/ioutil"
    "net/http"
    "reflect"
)

// 危险模式1：直接解析用户输入的代码字符串
func handleCodeParse(w http.ResponseWriter, r *http.Request) {
    code := r.URL.Query().Get("code")
    fset := token.NewFileSet()
    // 危险：code 完全可控
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }
    fmt.Fprintf(w, "Parsed: %v\n", f)
}

// 危险模式2：解析后执行字段值
func handleFieldAccess(w http.ResponseWriter, r *http.Request) {
    code := r.FormValue("struct_def")
    fset := token.NewFileSet()
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    if err != nil {
        return
    }

    // 遍历 AST 获取变量值
    ast.Inspect(f, func(n ast.Node) bool {
        if decl, ok := n.(*ast.GenDecl); ok {
            // 通过反射访问结构字段
            for _, spec := range decl.Specs {
                if vspec, ok := spec.(*ast.ValueSpec); ok {
                    // 危险：使用反射执行动态操作
                    for _, value := range vspec.Values {
                        executeExpression(value)  // 危险
                    }
                }
            }
        }
        return true
    })
}

// 危险模式3：生成并编译 Go 代码
func handleCodeGeneration(w http.ResponseWriter, r *http.Request) {
    template := r.PostFormValue("template")
    formula := r.PostFormValue("formula")

    // 生成 Go 代码
    code := fmt.Sprintf(`
package main
func Calculate() int {
    return %s  // 危险：formula 未经验证
}`, formula)

    // 写入文件并编译
    ioutil.WriteFile("generated.go", []byte(code), 0644)
    // 危险：后续可能被编译和执行
}

// 危险模式4：使用 unsafe 指针转换
func handleUnsafePtr(w http.ResponseWriter, r *http.Request) {
    code := r.URL.Query().Get("expr")
    fset := token.NewFileSet()
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    if err != nil {
        return
    }

    ast.Inspect(f, func(n ast.Node) bool {
        // 危险：如果代码包含 unsafe.Pointer 转换
        if unaryExpr, ok := n.(*ast.UnaryExpr); ok {
            if callExpr, ok := unaryExpr.X.(*ast.CallExpr); ok {
                // 通过 unsafe 实现内存访问
                executeUnsafeOperation(callExpr)  // 危险
            }
        }
        return true
    })
}

// 危险模式5：导入并执行用户指定的包
func handleImportExec(w http.ResponseWriter, r *http.Request) {
    pkgPath := r.FormValue("pkg")
    funcName := r.FormValue("func")

    code := fmt.Sprintf(`
import "%s"

func init() {
    %s.%s()  // 危险：执行任意包的函数
}`, pkgPath, pkgPath, funcName)

    fset := token.NewFileSet()
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    // 后续编译和执行
    _ = f
}

// 危险模式6：修改 AST 后执行
func handleASTModification(w http.ResponseWriter, r *http.Request) {
    code := r.FormValue("code")
    fset := token.NewFileSet()
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    if err != nil {
        return
    }

    // 修改 AST：注入新的函数调用
    ast.Inspect(f, func(n ast.Node) bool {
        if fn, ok := n.(*ast.FuncDecl); ok {
            // 危险：在函数体中插入恶意调用
            injectedCall := &ast.ExprStmt{
                X: &ast.CallExpr{
                    Fun: &ast.Ident{Name: "maliciousFunc"},
                },
            }
            fn.Body.List = append(fn.Body.List, injectedCall)
        }
        return true
    })
    // 后续编译执行修改后的代码
}

// 危险模式7：从数据库加载代码模板
func handleDBCodeTemplate(w http.ResponseWriter, r *http.Request) {
    id := r.URL.Query().Get("template_id")

    // 从数据库加载代码
    var code string
    db.QueryRow("SELECT code FROM templates WHERE id = ?", id).Scan(&code)

    fset := token.NewFileSet()
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    if err != nil {
        return
    }
    // 危险：数据库也可被污染
    compileAndExecute(f)
}

// 危险模式8：使用 cgo 调用
func handleCGOCall(w http.ResponseWriter, r *http.Request) {
    libName := r.FormValue("library")
    funcName := r.FormValue("function")

    code := fmt.Sprintf(`
/*
#cgo LDFLAGS: -l%s
#include <dlfcn.h>
void* handle = dlopen("lib%s.so", RTLD_LAZY);
void (*fn)() = dlsym(handle, "%s");
fn();  // 危险：调用任意 C 函数
*/
import "C"`, libName, libName, funcName)

    fset := token.NewFileSet()
    f, err := parser.ParseFile(fset, "user.go", code, parser.AllErrors)
    // 后续编译执行，可调用任意系统库函数
    _ = f
}

// 辅助函数（示意）
func executeExpression(expr ast.Expr) {
    // 通过反射执行表达式
}

func executeUnsafeOperation(callExpr *ast.CallExpr) {
    // 执行 unsafe 操作
}

func compileAndExecute(f *ast.File) {
    // 编译并执行代码
}
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `parser.Parse`（ParseFile、ParseDir、ParseExpr）
- 搜索 `ast.Inspect`、`ast.Walk`、`ast.Print`
- 搜索 `reflect` 包的使用（特别是 `CallFunc`、动态调用）
- 搜索 `unsafe` 包的使用（指针转换、内存操作）
- 搜索 `cgo` 指令和 C 函数调用
- 搜索字符串拼接或格式化用于构造代码：`fmt.Sprintf`、字符串连接
- 搜索编译执行相关：`exec.Command("go", "run")`、`plugin.Open`

**L2 跳读**：
- 定位所有 `parser.Parse*` 调用，确认输入来源：`r.URL.Query()`、`r.FormValue()`、`r.PostFormValue()`、`r.Header.Get()`
- 检查输入是否经过字符串拼接或格式化
- 检查 AST 遍历后的处理：是否修改了 AST、是否传递给编译器、是否通过反射执行
- 检查是否使用了 `unsafe` 指针转换或 cgo 调用
- 检查是否生成 Go 代码文件并调用 `go run`、`go build` 等命令
- 检查是否导入了用户控制的包路径

**L3 逐行读**：
- 确认用户输入的确切来源和完整传输路径
- 检查输入是否进行了验证、清理、沙箱化
- 逐行追踪所有影响 Parse 参数的中间变量
- 检查 AST 遍历逻辑中是否存在漏洞（如无限循环、堆栈溢出）
- 检查反射调用的安全性：是否限制了可调用的函数、方法
- 检查 unsafe 操作的边界检查
- 检查是否存在格式字符串漏洞、注入点

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查解析前是否有条件判断或白名单验证
- 搜索代码检查关键词：`allowedFunctions`、`validExpressions`、`PERMITTED_IDENTIFIERS`
- 搜索沙箱或隔离机制：goroutine 隔离、context 超时、资源限制
- 检查是否禁用了 `unsafe`、`cgo` 等危险特性
- 检查是否对解析的代码进行了语法验证或类型检查

**L3 逐行读**：
- 分析代码验证逻辑的完整性
- 检查是否使用了白名单限制允许的标识符、函数、包
- 分析 unsafe 使用时的边界检查和长度验证
- 检查是否对生成的代码进行了代码审计
- 分析反射调用的权限控制：是否限制了可访问的类型和方法
- 检查是否使用了 SELinux、AppArmor 等强制访问控制

**L4 跨模块追踪**：
- 追踪自定义的代码验证库实现
- 检查是否使用了 SSA（Static Single Assignment）进行数据流分析
- 查找是否有全局的代码安全检查中间件
- 追踪 reflect 调用链：reflect.ValueOf → MethodByName → Call
- 检查 unsafe 指针转换的链路
- 查找编译和执行的后端实现：是否使用了编译缓存、代码签名验证
- 检查是否使用了 `go generate` 来生成安全的样板代码

---

## Classify

### 漏洞判定

- **直接解析用户输入的代码字符串** → **确认漏洞**
  - 示例：`parser.ParseFile(fset, "file.go", userInput, parser.AllErrors)`
  - 示例：`parser.ParseExpr(userExpression)`

- **解析后通过反射动态执行 AST 中的表达式** → **确认漏洞**
  - 示例：遍历 AST 后调用 `reflect.ValueOf(fn).Call()`

- **生成包含用户输入的 Go 代码，后续编译执行** → **确认漏洞**
  - 示例：`fmt.Sprintf("func test() { %s }", userInput)` 然后 `go run`

- **使用用户输入修改 AST，后续执行修改后的代码** → **确认漏洞**
  - 示例：在 AST 中注入恶意函数调用，然后编译执行

- **根据用户输入导入或调用任意包的函数** → **确认漏洞**
  - 示例：`fmt.Sprintf("package main; import \"%s\"; func init() { %s.%s() }", userPkg, userPkg, userFunc)`

- **在生成的代码中使用 unsafe 指针或 cgo 调用** → **确认漏洞**
  - 示例：用户输入包含 `unsafe.Pointer` 转换或 cgo 调用

- **使用用户输入的包路径进行 `plugin.Open`** → **确认漏洞**
  - 示例：`plugin.Open(userProvidedPath)`

### 误报判定

- **仅解析用户输入的代码，不执行、不修改、不通过反射调用** → **误报**
  - 示例：单纯的语法检查、代码格式化、代码分析等

- **严格的代码白名单验证**：仅允许特定的预定义表达式或函数 → **误报**
  - 示例：`allowedFuncs := map[string]bool{"Add": true, "Sub": true}; if !allowedFuncs[fnName] { return error }`

- **完整的 AST 验证，禁止危险节点**：拒绝包含 unsafe、cgo、动态导入等的代码 → **误报**
  - 示例：遍历 AST 检查不存在 `*ast.UnaryExpr`（unsafe）、`*ast.ImportSpec` 等

- **参数来源完全受控**：仅来自配置文件、环境变量、硬编码常量 → **误报**
  - 示例：代码模板来自配置文件，占位符仅被安全值替换

- **在完全隔离的沙箱环境中执行**：使用 seccomp、容器隔离等 → **误报**
  - 示例：编译后的代码运行在受限的容器中，无法访问系统资源

### 代码异味

- **使用黑名单检查危险关键字** → **需进一步测试**
  - 可被空格、注释、多行字符串等绕过
  - 示例：`if strings.Contains(code, "unsafe") { ... }` 可被 `/*unsafe*/` 或换行绕过

- **仅验证解析前的输入** → **需检查完整流程**
  - 示例：验证后又进行了字符串处理、替换等操作

- **使用 cgo 但未对 C 函数参数进行验证** → **潜在风险**
  - C 库可能存在缓冲区溢出等漏洞

- **在循环中多次解析和编译用户代码** → **DoS 风险**
  - 可能导致 CPU/内存溢出

- **使用 `plugin.Open` 加载动态库** → **需严格限制路径**
  - 可能被路径遍历攻击

- **反射调用未进行权限检查** → **高风险**
  - 可能调用非预期的方法

### 审计等级

- **L1**：关键词扫描，快速定位所有 parser、reflect、unsafe、cgo 使用
- **L2**：跳读确认数据来源、代码生成方式、执行流程
- **L3**：逐行读取数据流、分析验证逻辑、检查 AST 修改
- **L4**：跨模块追踪代码生成、编译执行、反射调用链路

---

## Low risk

### 低风险场景

- **仅进行代码解析，不执行任何代码**：单纯的语法分析、代码格式化、静态分析
  - 示例：`ast.Print(fset, f)` 用于代码展示、或提取代码统计信息

- **严格的代码白名单验证**：仅允许特定的预定义函数、表达式
  - 示例：解析前验证代码仅能包含 `Add`、`Sub` 等白名单函数，拒绝其他所有内容

- **完整的 AST 节点类型白名单**：使用 ast.Inspect 遍历时，拒绝所有非白名单节点
  - 示例：仅允许 `*ast.BinaryExpr`、`*ast.BasicLit`、`*ast.Ident`，拒绝 `*ast.CallExpr`（函数调用）、`*ast.ImportSpec`（导入）

- **禁止所有危险特性**：代码中不允许出现 unsafe、cgo、文件 I/O、网络操作
  - 示例：遍历 AST 时检查不存在 `unsafe` 包导入、cgo 指令、`os` 包调用等

- **参数来源完全受控**：代码模板来自不可变的配置文件、环境变量、硬编码常量
  - 示例：`codeTemplate := "func test(x int) int { return x %s }"` 其中 `%s` 仅被安全数值替换

- **功能权限隔离**：此功能仅限管理员或特定角色访问
  - 示例：`if !user.IsAdmin() { return errors.New("permission denied") }`

- **编译后的代码在完全隔离的环境中执行**：使用容器、VM、seccomp 等隔离机制
  - 示例：编译后的二进制运行在容器中，无法访问宿主机文件系统、网络

- **使用官方的代码生成工具**：如 `go generate`、`protoc` 等，而非用户输入驱动的生成
  - 示例：使用 `go generate` 从预定义模板生成样板代码

- **完整的审计日志和监控**：所有代码解析、生成、执行操作被详细记录
  - 示例：记录解析的代码内容、生成的二进制、执行的函数、时间戳

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- Go 的 AST 解析虽然不直接执行代码，但后续的反射调用、代码生成、编译执行等环节仍可导致代码执行，需要评估整个工作流的安全性
- 应定期审查代码白名单、函数白名单的完整性，确保无遗漏可执行危险操作的路径
- 应建立完整的测试覆盖，确保 AST 注入、反射调用、unsafe 指针操作等各种攻击向量被充分检验
- 应评估是否真的需要动态代码解析执行，是否可以使用配置驱动、策略模式等替代方案
- 若使用了反射，应严格限制可反射调用的类型和方法，使用 `reflect.TypeOf()` 进行类型检查
- 若使用了 unsafe，应进行完整的边界检查和指针有效性验证
- 若使用了 cgo，应了解被调用 C 库的安全性，定期更新依赖库版本
- 若编译执行用户代码，应在隔离的容器或虚拟机中进行，使用 seccomp 等限制系统调用
- 应避免在生产环境中直接使用 Go 编译器，使用预编译的二进制或沙箱化的执行环境
