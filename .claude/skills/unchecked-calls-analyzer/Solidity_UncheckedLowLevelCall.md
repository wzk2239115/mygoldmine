# Solidity - 未检查低层级调用 (UncheckedLowLevelCall)

**漏洞概述**  
使用 `call()`/`staticcall()`/`delegatecall()`/`send()` 进行外部调用时，未检查返回的布尔值，导致调用失败被静默忽略，合约继续执行后续逻辑。常见于代币转账、跨合约委托调用、预言机响应处理等场景。

---

## Details

**典型代码模式：**

```solidity
// 危险：未检查返回值
function withdraw(address payable recipient, uint256 amount) external {
    recipient.call{value: amount}("");  // 返回值被忽略
    balances[msg.sender] -= amount;      // 即使转账失败也会扣款
}

// 危险：delegatecall 未检查
function upgrade(address logic, bytes memory data) external {
    logic.delegatecall(data);  // 失败被忽略，状态可能不一致
}

// 危险：send 未检查
payable(user).send(reward);  // 失败不影响后续逻辑
```

**快速定位核心操作技巧** `[审计等级: L1-L2]`
- **关键词扫描**：搜索 `.call()`、`.delegatecall()`、`.staticcall()`、`.send()`
- **语法特征**：低层级调用语句未赋值给变量，或赋值后变量未使用
- **上下文线索**：涉及资金转移、权限委托、外部合约交互的函数
- **IDE辅助**：利用编译器警告"unused return value"快速定位

**快速定位保护机制技巧** `[审计等级: L2-L3]`
- **显式检查**：查找 `require(success, ...)` 或 `if(!success) revert`
- **SafeCall库**：检查是否使用 OpenZeppelin 的 `Address.functionCall()` 等安全封装
- **事件记录**：确认是否通过事件记录失败（注意：仅记录不足以防御）
- **异常处理**：检查 try-catch 块是否正确处理失败场景
- **误区警惕**：`transfer()` 会自动 revert，但 gas 限制可能导致其他问题

---

## Classify

**判定为漏洞的条件：**
- 调用失败导致状态不一致（如扣款但未转账成功）
- 关键业务逻辑依赖调用成功但未验证（如权限变更、余额更新）
- 资金安全受影响（用户资金损失或合约资金锁死）

**判定为误报的情况：**
- 调用失败在业务逻辑上可接受（如批量转账中允许部分失败）
- 已通过其他机制保障安全（如后续操作会验证状态一致性）
- 非关键路径的辅助性调用（如日志记录、通知类操作）

**代码异味信号：**
- 虽有检查但仅记录日志而不阻止执行
- 使用 `send()` 而非 `call()` 且未配套检查（隐性设计缺陷）
- 错误处理逻辑过于宽松（如 catch 空块）

**判定依据权重：**
1. 状态变更先后顺序（Checks-Effects-Interactions 模式）
2. 失败影响范围（用户资金 > 合约状态 > 辅助功能）
3. 可利用性（是否可构造攻击场景）

---

## Low risk

**以下情况可降级为低风险：**

1. **非关键路径操作**  
   - 失败不影响核心业务逻辑（如奖励发放失败但主流程完成）
   - 可通过其他途径补救（如用户可手动 claim）

2. **已有兜底机制**  
   - 后续状态检查会自动修正不一致
   - 存在冗余验证层（如链下监控 + 手动介入）

3. **攻击成本过高**  
   - 需要特定权限才能触发（如仅 owner 可调用）
   - 经济上不可行（Gas 成本大于潜在收益）

4. **历史遗留但已废弃**  
   - 功能已停用但代码未删除
   - 仅在测试网或内部环境使用

5. **标准库安全包装**  
   - 虽未显式检查但使用了 SafeERC20 等成熟库
   - 依赖合约已验证安全（如官方 WETH）

**注意：** 即使评为低风险，仍建议添加显式检查以符合最佳实践，避免未来重构时引入新风险。
