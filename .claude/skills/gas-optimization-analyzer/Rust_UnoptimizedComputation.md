# Rust_UnoptimizedComputation

**漏洞类型**：Gas 优化 - 未优化计算  
**影响范围**：Solana 程序中的账户状态更新、代币铸造/销毁、权限验证等业务逻辑  
**核心问题**：复杂计算未缓存中间结果，导致重复计算浪费 Compute Units (CU)

---

## Details

### 典型代码模式

```rust
// 未优化：重复计算同一值
pub fn process_instruction(accounts: &[AccountInfo], data: &[u8]) -> ProgramResult {
    let account = &accounts[0];
    
    // 多次调用相同计算
    if calculate_fee(amount, rate) > threshold {
        let fee = calculate_fee(amount, rate);  // 重复计算
        transfer(account, fee)?;
    }
    
    // 循环内重复计算不变量
    for i in 0..100 {
        let base_value = expensive_hash(seed);  // 每次循环都重算
        process_item(i, base_value)?;
    }
    
    // 重复解析同一账户数据
    validate_owner(account)?;  // 内部解析 account.data
    update_balance(account)?;  // 再次解析 account.data
    
    Ok(())
}
```

### 快速定位核心操作技巧 **[L2: 跳读]**

1. **搜索循环结构**：`for`、`while`、`loop` 关键字，检查循环内是否有与迭代变量无关的计算
2. **搜索重复函数调用**：同一函数在相邻代码块内多次调用且参数相同
3. **关注 CU 密集操作**：
   - `sha256`、`keccak256`、`blake3` 等哈希计算
   - `try_from_slice`、`unpack`、`deserialize` 等反序列化
   - `checked_*` 系列安全运算（`checked_add`、`checked_mul`）
   - 跨程序调用 (CPI) 前的准备计算
4. **审查嵌套条件分支**：`if-else` 分支中相同表达式的重复求值

### 快速定位保护机制技巧 **[L1: 关键词扫描]**

1. **查找缓存变量**：`let cached_*`、`let computed_*`、`let temp_*` 等命名模式
2. **检查延迟计算**：`lazy_static!`、`OnceCell`、条件性计算（仅在需要时计算）
3. **验证数据复用**：
   - 账户数据一次性反序列化后多次引用
   - 中间结果存储在结构体字段中跨函数复用
4. **确认预计算优化**：常量表、查找表 (LUT)、位运算替代乘除法

---

## Classify

### 漏洞判定标准

- **高危**：核心业务逻辑中，重复计算导致 CU 消耗超过单笔交易限制（200K-1.4M CU），交易失败影响业务可用性
- **中危**：非关键路径中，重复计算浪费 10%-50% CU，显著增加用户成本但不影响功能
- **低危/代码异味**：重复计算浪费 <10% CU，优化收益有限

### 误报识别

1. **编译器优化已处理**：简单常量表达式、纯函数调用（Rust 编译器可能自动优化）
2. **可读性优先**：代码刻意保留重复计算以提升可读性，且 CU 消耗可忽略（<100 CU）
3. **边界情况**：计算仅在错误路径执行，实际触发概率极低

### 归类依据

- **查看计算复杂度**：O(1) 简单运算通常可接受，O(n) 以上需验证是否缓存
- **度量 CU 消耗**：使用 `solana_program::log::sol_log_compute_units!()` 实测，判断优化价值
- **评估触发频率**：高频路径（每笔交易必经）优先级高于低频分支

---

## Low risk

满足以下条件可降级为低风险：

1. **冷路径优化**：重复计算仅存在于初始化、管理员操作等低频场景
2. **微量 CU 浪费**：实测浪费 <500 CU，相对总消耗占比 <5%
3. **简单运算**：仅涉及基本算术（加减法、位运算），无哈希/序列化等重操作
4. **已有限流**：程序通过其他机制（如费率限制、账户锁）限制调用频率，降低累积影响
5. **测试覆盖充分**：有完善的性能测试证明实际场景下 CU 消耗在安全范围内
6. **临时实现**：代码注释标明为 MVP 版本，后续将优化（需确认优化计划）
