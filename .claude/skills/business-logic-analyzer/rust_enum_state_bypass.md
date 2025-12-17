# Rust 枚举状态机转换漏洞

**漏洞本质**：状态机转换未充分利用枚举类型系统约束，允许运行时非法状态跳转

---

## Details

**审计等级**：**L3（逐行读）** → **L4（跨模块追踪）**

**代码特征**：
```rust
// 高危模式：使用基础类型存储状态
struct Order {
    status: String,  // 或 i32, &str
    amount: u64,
}

// 危险操作：字符串/整数直接赋值状态
order.status = "completed".to_string();  // 绕过状态转换逻辑
```

**快速定位核心操作**：
- 搜索 `status =`、`state =`、`phase =` 等状态赋值
- 关注 `String`/`i32` 类型的状态字段，非枚举定义
- 追踪 `set_status()`、`update_state()` 等状态变更函数
- 检查是否存在 `pub` 字段直接暴露状态

**快速定位保护机制**：
- 查找 `match` 语句验证前置状态（`Current -> Next` 合法性）
- 寻找 `impl` 块中的状态转换方法（如 `fn transition()`）
- 检查是否使用 `enum` 类型系统编码状态约束
- 验证是否有 `private` 字段 + `getter/setter` 模式

**典型漏洞场景**：
```rust
// 场景1：公开可变状态字段
pub struct Workflow {
    pub current_step: u8,  // 直接修改绕过校验
}

// 场景2：缺少转换验证
impl Order {
    fn set_status(&mut self, new: String) {
        self.status = new;  // 未校验 pending->completed 是否合法
    }
}

// 场景3：运行时字符串匹配
if order.status == "paid" {  // 拼写错误导致逻辑绕过
    ship();
}
```

**审计检查清单**：
1. 状态字段是否为 `enum` 类型？（非枚举→L4追踪）
2. 状态赋值是否经过转换函数？（直接赋值→漏洞）
3. 转换函数是否校验前置状态？（无校验→漏洞）
4. 状态字段是否 `pub`？（公开可变→高危）
5. 是否存在字符串比较状态？（魔法值→易绕过）

---

## Classify

### ✅ 确认漏洞
1. **公开可变状态字段** + **无转换校验**
   ```rust
   pub status: String  // 可被外部任意修改
   ```
2. **跨权限状态跳转**：用户可从 `draft` 直接跳至 `approved`
3. **字符串/整数硬编码状态** + **关键业务逻辑**（支付/审批/权限）

### ⚠️ 代码异味
1. 使用基础类型存储状态，但有完善校验函数（性能妥协但安全）
2. 状态转换逻辑分散在多个模块，难以审计（维护性问题）
3. `match` 分支未覆盖所有状态组合（潜在panic，非安全漏洞）

### ❌ 误报
1. 状态字段为 `private` + 仅通过类型安全的枚举转换
   ```rust
   status: OrderStatus,  // enum 类型
   impl { fn next(&self) -> Result<OrderStatus> {...} }
   ```
2. 使用 `typestate` 模式编码状态机（编译时保证）
3. 字符串状态仅用于日志/展示，非业务判断依据

---

## Low Risk

**低风险场景**（建议优先级降级）：
1. **非关键业务流程**：日志状态、UI展示状态、调试标志
2. **单向状态机**：只能前进不可回退（如进度条：0% → 100%）
3. **无权限差异**：所有状态对应相同权限等级
4. **内部私有模块**：状态字段 `private` 且仅内部 crate 使用
5. **已有完善单元测试**：覆盖所有非法状态转换测试用例

**降级判断标准**：
- 漏洞利用需要控制 `>=2` 个独立变量
- 非法状态触发无实际业务影响（如仅panic崩溃）
- 状态转换需通过复杂条件竞争（概率性触发）

**示例**：
```rust
// 低风险：内部日志状态
struct Logger {
    level: String,  // "debug"/"info" - 仅影响输出
}

// 高风险：支付状态
struct Payment {
    status: String,  // "pending"/"completed" - 影响资金
}
```