# Rust 配置文件表达式注入

**漏洞成因**：在解析 TOML、YAML 等配置文件时，将其中包含的表达式字段动态求值或传递给脚本引擎执行，导致用户通过配置文件注入恶意表达式。常见于配置框架、参数化配置解析、条件执行等场景。

---

## Details

**代码示例**：
```rust
// 危险：配置表达式直接求值
use serde_json::Value;

let config: Value = serde_json::from_str(&config_str)?;
let expr = config["condition"].as_str().unwrap();
// expr = "1 == 1 || std::fs::read_to_string('/etc/passwd')"
evaluate_expression(expr)?;  // 直接执行表达式

// 危险：使用脚本引擎执行配置表达式
use lua::Lua;

let lua = Lua::new();
let config_expr = config["rule"].as_str().unwrap();
lua.load(config_expr).eval::<()>()?;  // 执行用户提供的 Lua 代码

// 较安全：配置值白名单验证
let config: Value = serde_json::from_str(&config_str)?;
let mode = config["mode"].as_str().unwrap();
match mode {
    "safe" => set_execution_mode(ExecutionMode::Safe),
    "strict" => set_execution_mode(ExecutionMode::Strict),
    _ => return Err("Invalid mode"),
}

// 较安全：使用受限的表达式解析器
let expr = config["expression"].as_str().unwrap();
let parsed = safe_expr_parser::parse(expr)?;  // 仅解析安全语法
evaluate_safe_expression(parsed)?;
```

**快速定位核心操作**：
- 关键词：`eval`、脚本引擎调用、表达式解析函数、配置读取和处理
- 查看配置文件读取的来源（文件、环境变量、远程 API）
- 检查是否存在配置热重载机制
- 追踪配置值是否直接进入表达式评估函数
- 关注是否使用了危险的脚本引擎库

**快速定位保护机制**：
- 是否对配置值进行了白名单验证
- 是否使用了安全的表达式解析器而非通用脚本引擎
- 是否限制了配置来源和权限
- 是否对表达式的复杂度、长度、执行时间有限制
- 是否使用了类型系统的优势进行静态验证

**审计等级**：**L2-L3**
- **L2**：跳读配置读取和表达式处理的关键路径
- **L3**：逐行分析配置值的流向和验证逻辑

---

## Classify

**确认为漏洞**：
- 配置文件中的表达式字段被直接传入脚本引擎或 eval 函数
- 配置来源包括用户可控的渠道
- 表达式求值环境未被沙箱化，可访问危险 API
- 配置验证缺失或不完整

**误报**：
- 配置完全由应用内部提供
- 配置字段为简单数据类型，不支持表达式
- 存在严格的白名单限制，配置值完全安全

**代码异味**：
- 配置处理代码中存在脚本引擎调用
- 支持热重载配置但缺少审计

---

## Low Risk

以下情况可评为低风险：
- **受限环境**：配置由系统管理员管理，普通用户无权限
- **沙箱隔离**：表达式在受限环境执行，无法访问文件和网络
- **表达式能力弱**：仅支持基础运算，不支持函数调用
- **内网应用**：仅由内部可信用户使用

**注意**：Rust 的类型系统可帮助编译期检查，但运行时仍需验证。
