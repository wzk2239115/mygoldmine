# Solidity_StorageCollisionInUpgrade

**漏洞类型：** 升级时存储冲突

**适用场景：** 代理模式（UUPS、Transparent Proxy、Beacon Proxy）、模块化协议升级、治理驱动的合约替换

**核心风险：** 逻辑合约升级时存储变量布局变更，导致新旧版本数据映射错误或状态损坏

---

## Details

### 代码示例

```solidity
// V1 逻辑合约
contract LogicV1 {
    address public owner;      // slot 0
    uint256 public balance;    // slot 1
}

// V2 逻辑合约 - 错误示例：插入新变量导致布局冲突
contract LogicV2 {
    address public owner;      // slot 0
    bool public paused;        // slot 1 ❌ 覆盖了原 balance
    uint256 public balance;    // slot 2 ❌ 位置错位
}

// V2 正确示例：追加新变量
contract LogicV2Fixed {
    address public owner;      // slot 0
    uint256 public balance;    // slot 1 ✓ 保持原位置
    bool public paused;        // slot 2 ✓ 新变量追加
}
```

### 快速定位核心操作的技巧

**【L3: 逐行读】** 审查逻辑合约版本演进：
- 对比新旧版本状态变量声明顺序
- 检查是否在中间插入/删除/修改变量类型
- 关注 `struct`、`mapping`、`array` 等复杂类型的内部调整
- 识别继承链变化（父合约顺序变更会影响存储布局）

**【L2: 跳读】** 关键标志：
- `contract V2 is` 继承声明变化
- 状态变量类型修改（`uint256` → `uint128`）
- 使用 `storage gap` 或 `__gap[50]` 保留槽位

**【L4: 跨模块追踪】** 复杂场景：
- 多层继承时追溯所有父合约的存储变量
- 库合约（`library`）使用 `delegatecall` 时的存储上下文
- Diamond 模式下多 facet 的存储槽分配策略

### 快速定位保护机制的技巧

**【L1: 关键词扫描】** 寻找防护标识：
- `__gap` 数组声明（OpenZeppelin 升级模式）
- `@custom:storage-location` 注解（ERC-7201 命名空间存储）
- `StorageSlot` 库使用（指定槽位写入）

**【L2: 跳读】** 检查保护措施：
- 是否在每个可升级合约末尾预留 `uint256[50] private __gap`
- 是否使用 EIP-1967 标准槽位（`bytes32(uint256(keccak256('...')) - 1)`）
- 是否采用非结构化存储（unstructured storage）避免冲突

**【L3: 逐行读】** 深度验证：
- 计算实际存储槽占用（考虑打包规则）
- 验证 `initializer` 中是否操作了固定槽位
- 确认 `immutable` 和 `constant` 变量的使用（不占存储槽）

**【L0: 快速跳过】** 以下情况无需深入：
- 纯视图合约无状态变量
- 明确声明为非可升级合约

---

## Classify

### 漏洞判定标准
- **确认漏洞：** 新版本在旧变量前插入/删除变量，或修改变量类型导致槽位错位，且无保护措施
- **高危场景：** 影响关键财务数据（余额、权限、所有权）或导致合约逻辑完全失效
- **中危场景：** 仅影响部分非关键状态，可通过额外迁移恢复

### 误报识别
- **使用 ERC-7201 命名空间：** 变量存储在独立哈希槽，不受顺序影响
- **仅追加变量：** 新变量始终在末尾添加，保持旧布局不变
- **测试网/未部署合约：** 尚未实际升级，仅设计阶段

### 代码异味判定
- **缺少 storage gap：** 虽当前版本无冲突，但未来扩展性受限
- **继承顺序不规范：** 虽未触发实际冲突，但增加维护风险
- **变量命名混乱：** 难以追踪版本演进，提高审计难度

---

## Low Risk

### 低风险评级场景

1. **仅常量变化：** 仅修改 `constant` 或 `immutable` 变量，不影响存储布局
2. **纯逻辑优化：** 仅修改函数实现，状态变量声明完全一致
3. **新增 View 函数：** 不涉及状态变更，仅增加查询接口
4. **规范的 Gap 预留：** 合约末尾预留足够 gap，新变量消耗 gap 空间而非插入
5. **文档化的命名空间存储：** 严格遵循 ERC-7201，所有新变量使用独立槽位且有明确注释
6. **完善的测试覆盖：** 升级前后有完整的存储快照对比测试，验证数据一致性

### 降级依据
- 影响范围限于测试环境或极少资金的合约
- 已有应急降级方案（如 Timelock + 多签控制）
- 状态变量仅用于辅助计算，非持久化关键数据
