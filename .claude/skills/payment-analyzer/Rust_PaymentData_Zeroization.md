# Rust_PaymentData_Zeroization

## Details

**核心漏洞特征**：Rust应用中敏感支付数据（密钥、密码、卡号等）从内存释放时未清零，可能被恢复。

**代码示例定位**：查找敏感数据处理代码，关键词包括 `secret`, `password`, `card_number`, `pin`, `let mut` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `let secret =` 或 `let password =` - 检查敏感数据定义
- 搜索 `String` 或 `Vec<u8>` - 检查是否使用zeroize库
- 搜索内存释放操作（函数结束、drop） - 检查是否清零
- 搜索 `clone()` 或 `to_string()` - 检查是否产生副本

**快速定位保护机制**（L2: 跳读）：
- 检查是否导入并使用zeroize库
- 检查敏感数据结构是否实现Zeroize trait
- 检查是否使用ZeroizeOnDrop
- 检查秘钥卸载流程

## Classify

**漏洞判定标准**：
- 敏感数据使用普通String或Vec → **漏洞**
- 函数结束时数据未清零 → **漏洞**
- 多处clone敏感数据 → **漏洞**
- 错误处理中敏感数据未清零 → **漏洞**

**误报情况**：
- 使用zeroize库管理敏感数据 → 低风险
- ZeroizeOnDrop自动清零 → 低风险
- 编译器优化下自动清零 → 低风险

**代码异味**：
- 虽有zeroize但未覆盖所有敏感字段 → 审计
- 中间临时变量未清零 → 审计

## Low risk

**低风险评级条件**：
1. **库选择**：使用zeroize库管理敏感数据
2. **数据结构**：敏感字段使用Zeroize trait
3. **自动清零**：实现ZeroizeOnDrop trait
4. **完整覆盖**：所有敏感字段都清零（密钥、密码、卡号等）
5. **错误路径**：所有异常分支都清零敏感数据