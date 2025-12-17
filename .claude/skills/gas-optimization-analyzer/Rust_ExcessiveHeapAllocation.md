# Rust_ExcessiveHeapAllocation

**漏洞描述**  
Solana 程序中频繁使用 `Vec`、`String`、`Box` 等堆分配数据结构，而非栈上数组或引用操作，导致运行时 CU（Compute Units）消耗激增，降低交易吞吐量并增加用户成本。

## Details

**代码示例特征：**
```rust
// 高频堆分配模式
let mut results = Vec::new();  // 循环内或高频调用
for account in accounts.iter() {
    let data = account.try_borrow_data()?;
    let parsed = parse_account(&data)?;  // 返回 String/Vec
    results.push(parsed);
}

// 字符串拼接
let mut log = String::new();
log.push_str("Transfer: ");
log.push_str(&amount.to_string());
```

**快速定位核心操作（L2-L3）：**
- **关键模式**：循环内 `Vec::new()`、`String::from()`、`Box::new()`、`to_vec()`、`clone()`
- **高频场景**：账户迭代（`iter()`）、数据反序列化（`try_from_slice`）、日志拼接
- **CU 热点**：`instruction` 处理函数、跨程序调用（CPI）准备阶段、账户验证逻辑
- **审计技巧**：搜索 `Vec::with_capacity` 缺失、数组长度固定但用 `Vec`、临时对象未 `&` 传递

**快速定位保护机制（L1）：**
- **预期优化**：栈数组 `[T; N]`、`ArrayVec`、`&[u8]` 切片操作、`Cow<str>`
- **缓存复用**：`RefCell`/`OnceCell` 包装的全局状态、`LazyStatic` 初始化
- **编译器检查**：`#[inline]` 标记、`clippy::unnecessary_to_owned` lint
- **监控手段**：`msg!` 调试输出 + 本地测试 CU 消耗（使用 `solana-program-test`）

## Classify

**漏洞判定标准：**
- **确认漏洞**：循环内动态分配且迭代次数与账户数线性相关；单次调用 CU 消耗超出预算导致交易失败
- **误报情形**：初始化阶段一次性分配（非热路径）；已使用 `with_capacity` 预留容量；数据规模受常量约束
- **代码异味**：可优化但不影响功能，如小规模数据（<10 元素）的 `Vec`；日志字符串拼接（非生产环境）

**分析维度：**
1. **频率**：是否在循环/高频调用路径
2. **规模**：分配大小是否与外部输入相关
3. **替代性**：能否用固定大小栈结构替代
4. **实际影响**：测试网 CU 消耗是否接近 200K 上限

## Low risk

**低风险场景：**
1. **单次初始化**：程序启动时一次性分配全局状态，后续仅读取
2. **边界清晰**：数组长度受 `MAX_ACCOUNTS`（<32）等常量严格限制
3. **已有缓解**：使用 `smallvec`、`arrayvec` 等栈优先库；明确标注 `// TODO: optimize`
4. **非关键路径**：测试辅助函数、管理员专用指令（调用频率低）
5. **成本可控**：实测 CU 消耗 <10K 且业务逻辑确需动态容量

**评级依据：**
低风险需同时满足"非用户热路径"且"已做容量规划"或"技术债务已标记"

## 审计专业技巧

### 1. 真实漏洞识别（高可信度）

**模式一：循环内无容量预留的 Vec**
```rust
// ❌ 真实漏洞：循环内重复分配，容量增长导致 O(n²) 复杂度
for account in accounts.iter() {
    let mut temp = Vec::new();  // 每次迭代重新分配，无初始容量
    temp.push(account.lamports);  // 触发多次扩展
}
```
**审计特征**：
- 无 `with_capacity` 预留
- 迭代次数与账户数相关（来自 `accounts` 参数）
- 实测表现：1000 账户时可增加 50K+ CU

**模式二：字符串拼接在交易处理路径**
```rust
// ❌ 真实漏洞：每个字符拼接触发堆扩展，O(n²) 时间复杂度
pub fn process_instruction(accounts: &[AccountInfo]) -> ProgramResult {
    let mut log = String::new();
    for account in accounts.iter() {
        log.push_str(&format!("Account: {}\n", account.key));  // 高频拼接
    }
    msg!("{}", log);
    Ok(())
}
```
**审计特征**：
- 在 `process_instruction` 或 `entrypoint` 中的字符串操作
- 拼接次数与外部输入（账户数、数据长度）成正比
- 实测表现：100+ 拼接操作时，CU 上升 5-10 倍

**模式三：嵌套分配（Vec of Vec）**
```rust
// ❌ 真实漏洞：多层堆分配导致内存碎片和 CU 爆炸
let mut matrix: Vec<Vec<u64>> = Vec::new();
for i in 0..accounts.len() {
    let row = parse_data(&accounts[i].data.borrow())?;  // 返回 Vec<u64>
    matrix.push(row);  // 嵌套分配
}
```
**审计特征**：
- 返回值为 `Vec<T>` 的函数调用，结果再推入另一个 Vec
- 三维以上数据结构的动态分配
- 实测表现：50 个账户时 CU 增加 80K+

### 2. 常见误报排查清单

**误报案例一：初始化阶段的 Vec 分配**
```rust
// ✅ 误报：单次初始化，非热路径
pub fn init_program() -> ProgramResult {
    let mut state = Vec::with_capacity(1000);  // 仅初始化时执行
    // ... 初始化逻辑 ...
    Ok(())
}
```
**区分方法**：
- 检查函数调用链：是否来自 `instruction!()` 或仅来自 `mod_init`
- 控制流分析：是否在全局 `lazy_static!` 块内
- 容量规划：已使用 `with_capacity` 预留

**误报案例二：受常量限制的小规模分配**
```rust
// ✅ 误报：MAX_ACCOUNTS = 32（常量），规模受控
const MAX_ACCOUNTS: usize = 32;
let mut validator_set = Vec::with_capacity(MAX_ACCOUNTS);
for account in accounts.iter().take(MAX_ACCOUNTS) {
    validator_set.push(*account.key);
}
```
**区分方法**：
- 代码中明确有 `.take(CONSTANT)` 或 `if accounts.len() > CONSTANT { return Err }` 边界检查
- `with_capacity(CONSTANT)` 中的常量可追溯到程序常量定义
- CU 消耗完全确定且不超过 1K

**误报案例三：数据无法采用栈分配的合理场景**
```rust
// ✅ 误报：格式解析确实需要动态分配
let json_data = String::from_utf8(compressed_data.to_vec())?;
// 无法用栈数组替代，因为数据大小和内容不确定
```
**区分方法**：
- 验证数据来源：是否来自外部序列化格式（JSON/MessagePack）
- 检查大小限制：是否有 `if data.len() > MAX_SIZE` 检查
- 替代方案评估：使用流式解析库（serde_json with limiting）

### 3. 审计工具链与验证方法

**动态测试方法：**
```bash
# 使用 solana-program-test 模拟环境计算 CU
cargo test --lib -- --nocapture -- compute_units_test

# 启用 msg! 宏输出，观察 CU 变化趋势
# 输出示例：
# Account count: 10, CU: 5000
# Account count: 20, CU: 12000  # 线性增长 → 正常
# Account count: 50, CU: 150000 # 二次增长 → 漏洞
```

**静态分析指标：**
- 使用 `cargo clippy` 与自定义 lint：`Vec::with_capacity` 检测缺失
- 关键词快速搜索：`Vec::new()` + `for` 组合、`String::new()` + 循环拼接
- 调用图分析：追踪堆分配函数是否在 `#[inline]` 函数或关键路径中

**代码评审核心问题：**
1. "这次分配是否在用户热路径（instruction 处理）中？"
2. "分配大小是否与账户数、数据长度这类不可控因素相关？"
3. "现有实现是否已用预容量、栈数组或延迟初始化来优化？"
4. "本地或测试网实测 CU 消耗是否超过 10K 且呈线性增长？"

### 4. 真实漏洞 vs 误报的判断矩阵

| 特征 | 真实漏洞 | 误报 |
|------|--------|------|
| **调用频率** | instruction 处理主路径 | init/admin 函数 |
| **分配规模** | 与账户数/数据长度相关 | 常量或静态已知 |
| **容量规划** | 无 `with_capacity` 或缺容量限制 | 已预留或 `take(CONST)` |
| **CU 影响** | 线性/二次增长，超 10K | 固定 <1K 或可忽略 |
| **替代方案** | 栈数组/切片/smallvec 可行 | 技术上无可行替代 |
| **修复成本** | 低（改用栈结构） | 中/高（重构解析流程） |

### 5. 漏报防护

**常见漏报点：**
- 隐藏在依赖库中的堆分配（e.g. `serde::to_vec`）→ 需审查依赖库关键函数
- 异步任务中的分配（e.g. `tokio::spawn`）→ Solana 程序无异步，但需检查中间库的隐式分配
- 错误路径中的分配（e.g. `Err(format!("...").into())`）→ 虽然罕见但仍计入 CU
- 宏展开后的隐式分配 → 必要时运行 `cargo expand` 查看宏展开结果
