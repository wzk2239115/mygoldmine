# Solidity ERC-20: Invalid Event Definition

## Details

### Code Examples

**问题代码示例 1：Transfer 事件缺失 indexed 修饰符**
```solidity
// ❌ 标准定义应该对 from 和 to 进行 indexed 修饰
event Transfer(address from, address to, uint256 value);

function transfer(address to, uint256 amount) public returns (bool) {
    balances[msg.sender] -= amount;
    balances[to] += amount;
    emit Transfer(msg.sender, to, amount);
    return true;
}
```

**问题代码示例 2：Approval 事件参数顺序错误**
```solidity
// ❌ 参数顺序应为 owner, spender, value
event Approval(address spender, address owner, uint256 value);

function approve(address spender, uint256 amount) public returns (bool) {
    allowances[msg.sender][spender] = amount;
    emit Approval(spender, msg.sender, amount);
    return true;
}
```

**问题代码示例 3：事件拼写错误**
```solidity
// ❌ 事件名应为 Transfer，不是 Transfers
event Transfers(address indexed from, address indexed to, uint256 value);

// ❌ 或者使用错误的参数类型
event Transfer(address indexed from, address indexed to, uint256 from_amount, uint256 to_amount);
```

### 核心操作定位技巧
- **L1: 关键词扫描** - 搜索 `event Transfer` 和 `event Approval` 定义
- 检查参数列表：Transfer 应为 `(address indexed from, address indexed to, uint256 value)`，Approval 应为 `(address indexed owner, address indexed spender, uint256 value)`
- 确认参数类型：from/to/owner/spender 必须为 address，value 必须为 uint256

### 保护机制定位技巧
- **L2: 跳读** - 浏览合约中所有 emit 语句，检查 Transfer 和 Approval 事件的调用位置和参数顺序
- 验证 emit Transfer(from, to, value) 和 emit Approval(owner, spender, value) 是否按正确顺序传参
- **L3: 逐行读** - 逐行对比标准 ERC-20 接口，确认事件签名完全匹配

---

## Classify

### 漏洞判定标准 (Bug)
- Transfer 事件定义中缺少 indexed 修饰符（标准要求 from 和 to 都应为 indexed）
- Approval 事件定义中缺少 indexed 修饰符（标准要求 owner 和 spender 都应为 indexed）
- 事件参数顺序错误（Transfer: from/to/value，Approval: owner/spender/value）
- 事件参数类型错误（如使用 uint instead of address）
- 事件名拼写错误（如 `Transfers` 而非 `Transfer`，`Aproval` 而非 `Approval`）

### 误报排除标准 (False Positive)
- 合约定义了额外的自定义事件（如 `TransferBatch`），但标准事件定义正确
- 继承自 OpenZeppelin 等标准库，事件定义已在基合约中正确声明
- 事件在接口中声明，实现合约继承了接口并正确使用事件

### 代码异味 (Code Smell)
- Transfer 或 Approval 事件从未被 emit（对应的函数中没有触发事件）
- 事件参数中包含冗余信息或缺少关键参数
- indexed 修饰符应用不一致（某些部署版本有，某些没有）

---

## Low Risk

### 应评为低风险的情况
- 合约在注释中明确说明使用自定义事件定义，且该定义在合约生态中一致使用
- 合约通过代理模式委托给标准 ERC-20 库实现，事件由目标合约正确定义
- 仅在 transfer/approve 的内部辅助函数中改动事件定义，公开接口的事件定义符合标准
- indexed 修饰符缺失但合约架构通过其他日志机制（如自定义查询函数）提供了等价的索引能力
