# Rust 动态表达式求值注入

**漏洞成因**：Rust 本身不提供 `eval()` 函数，但部分第三方 crate（如 `evalexpr`、`meval`、`rhai`）提供表达式求值和脚本执行功能。当应用使用这些 crate 解析和执行用户输入的表达式时，攻击者可构造恶意表达式访问变量、调用函数、执行复杂逻辑等，可能导致信息泄露、逻辑绕过或拒绝服务。由于 Rust 的安全特性，直接 RCE 较难，但仍需注意 DoS 和逻辑风险。

---

## Details

**代码示例**：
```rust
// 危险：使用 evalexpr crate 执行用户输入
use evalexpr::*;

fn handle_request(user_input: &str) -> Result<Value, EvalexprError> {
    eval(user_input) // 危险：用户可注入复杂表达式
}

// 危险：使用 meval crate
use meval::eval_str;
let result = eval_str(user_input)?; // 危险：数学表达式求值

// 危险：使用 rhai 脚本引擎
use rhai::Engine;
let engine = Engine::new();
let result = engine.eval::<i64>(user_input)?; // 危险：执行 Rhai 脚本

// 攻击载荷示例（取决于库的能力）
// "10000000 * 10000000 * 10000000"  // DoS：资源耗尽
// 复杂的嵌套表达式导致栈溢出
// 逻辑绕过：构造复杂的布尔表达式

// 较安全：限制表达式长度和复杂度
if user_input.len() > 100 {
    return Err("Expression too long".into());
}

// 较安全：使用表达式白名单
let allowed = vec!["x + y", "x * y", "x - y"];
if !allowed.contains(&user_input) {
    return Err("Invalid expression".into());
}

// 较安全：使用受限的求值上下文
use evalexpr::*;
let context = context_map! {
    "x" => 10,
    "y" => 20,
}.unwrap();
eval_with_context(user_input, &context)?; // 仅允许访问特定变量

// 较安全：设置表达式执行超时
use std::time::Duration;
use std::thread;
let handle = thread::spawn(move || {
    eval(user_input)
});
match handle.join_timeout(Duration::from_secs(1)) {
    Ok(result) => result,
    Err(_) => return Err("Timeout".into()),
}
```

**快速定位核心操作**：
- 关键词：`eval(`、`eval_str`、`eval_with_context`、`Engine::new`、`engine.eval`
- 查找表达式求值 crate 的使用：`evalexpr`、`meval`、`rhai`、`calc`
- 追踪表达式字符串的来源，判断是否包含用户输入
- 检查表达式求值时传递的上下文和变量
- 关注表达式的复杂度限制和超时设置
- 搜索 `Cargo.toml` 文件中的相关依赖

**快速定位保护机制**：
- 表达式字符串是否来自可信的配置文件而非用户输入
- 是否对表达式长度和复杂度进行限制
- 是否使用表达式白名单验证
- 求值上下文中是否仅包含必要的变量，不包含敏感数据
- 是否设置了表达式执行的超时时间
- 是否使用了 Rust 的类型系统限制表达式返回值
- 依赖 crate 版本是否为最新稳定版

**审计等级**：**L2-L3**
- **L2**：跳读表达式求值代码，识别第三方 crate 的使用
- **L3**：逐行验证表达式来源和上下文配置，确认安全措施

---

## Classify

**确认为漏洞**：
- 使用表达式求值 crate 执行用户输入的表达式
- 未对表达式长度和复杂度进行限制，可能导致 DoS
- 求值上下文中包含敏感数据或功能
- 未设置表达式执行超时，可能导致资源耗尽
- 表达式可被用于逻辑绕过或信息泄露

**误报**：
- 表达式字符串来自可信的配置文件
- 使用表达式白名单，仅允许预定义的安全表达式
- 求值上下文仅包含必要的、非敏感的变量
- 设置了合理的表达式长度限制和执行超时
- 使用 Rust 的类型系统限制表达式能力

**代码异味**：
- 大量使用动态表达式求值，增加复杂度
- 表达式字符串通过字符串拼接构造
- 求值上下文中包含过多的变量和函数
- 缺乏对表达式执行的监控和日志记录

---

## Low Risk

以下情况可评为低风险：
- **表达式白名单**：仅允许执行预定义的安全表达式
- **复杂度限制**：设置表达式长度限制（如 100 字符）和嵌套深度限制
- **受限上下文**：求值上下文仅包含必要的数值变量，不包含敏感数据
- **执行超时**：使用 `std::thread` 设置表达式执行的超时时间（如 1 秒）
- **类型限制**：使用 Rust 的强类型系统限制表达式返回值类型
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有表达式求值操作均记录日志并监控异常模式
- **资源限制**：在容器中运行，限制 CPU 和内存使用

**注意**：Rust 的内存安全特性使得 RCE 较难，但仍需防范 DoS 攻击和逻辑绕过，应严格控制表达式的复杂度和执行时间。
