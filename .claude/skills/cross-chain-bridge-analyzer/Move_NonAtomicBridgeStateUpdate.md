# Move_NonAtomicBridgeStateUpdate

**漏洞类型：** 非原子桥接状态更新  
**影响范围：** Aptos/Sui 跨链桥资产托管与铸造逻辑  
**核心风险：** 状态更新操作非原子性，部分失败导致资产卡在中间状态，造成资产锁定或双重铸造

---

## Details

**典型代码模式：**
```move
public entry fun bridge_transfer(sender: &signer, amount: u64) {
    // Step 1: 锁定源链资产
    lock_asset(sender, amount);
    
    // Step 2: 更新桥接记录
    update_bridge_state(amount);  // ⚠️ 若此处失败，资产已锁定但状态未更新
    
    // Step 3: 发出跨链事件
    emit_cross_chain_event(sender, amount);  // ⚠️ 若此处失败，前面状态已改变
}

// 或在接收端
public entry fun complete_transfer(proof: Proof) {
    verify_proof(&proof);  // ⚠️ 验证通过后若后续失败会怎样？
    mint_wrapped_asset(proof.recipient, proof.amount);  // ⚠️ 铸造成功但...
    mark_proof_consumed(proof.id);  // ⚠️ 若此处失败，proof 可重放
}
```

**快速定位核心操作 (L3-逐行读)：**
- 搜索 `public entry fun` 且包含 `bridge/lock/mint/burn/transfer` 关键词的函数
- 关注多步骤资产操作：`lock + update + emit` 或 `verify + mint + mark` 组合
- 识别资源修改链：`borrow_global_mut` → 多次字段修改 → 事件发出
- 检查是否存在中间 `assert!` / `abort` 可能打断流程
- 重点：任意两步骤间若缺少事务性保障，均为风险点

**快速定位保护机制 (L2-跳读)：**
- ✓ 单一 `acquires` 资源一次性完成所有状态修改（原子性保障）
- ✓ 使用 `abort` + 全局状态回滚模式（Move 事务级回滚）
- ✓ 状态机模式：通过 `enum State { Pending, Locked, Completed }` 标记中间态，确保可恢复
- ✓ 双向记录：同时更新 `PendingBridge` 和 `CompletedBridge` 两个资源
- ✓ 使用 `vector::pop_back + abort` 模式确保要么全成功要么全回滚
- ✗ 缺失：跨函数调用的多步操作无 rollback 机制
- ✗ 缺失：`mint` 后未立即 `mark_consumed`，中间有其他逻辑

---

## Classify

**归类为严重漏洞 (Critical)：**
- 资产锁定后，状态更新/事件发出失败无补救机制，导致资产永久锁定
- 铸造成功后，proof 消费标记失败，允许重复铸造
- 跨函数调用无事务保护，子函数失败导致父函数状态不一致

**归类为中等风险 (Medium)：**
- 存在中间状态但有恢复机制（如管理员手动修复函数），但依赖链下监控
- 部分失败可通过重试恢复，但存在时间窗口风险

**归类为误报：**
- 单次 `borrow_global_mut` 内完成所有修改，Move 事务保证原子性
- 所有状态变更在同一 `acquires` 块内，失败自动全部回滚
- 使用 `Table/Vector` 原子操作（如 `vector::push_back` 单次调用）

**归类为代码异味：**
- 逻辑上可合并但分多步执行，虽然安全但增加 gas 和失败概率
- 事件发出顺序与状态变更顺序不一致，虽不影响安全但影响可观察性

---

## Low risk

**给予低风险评级的场景：**

1. **完善的失败恢复机制**：存在专用的 `recover_stuck_assets()` 函数，由治理多签触发，且有时间锁保护
2. **仅查询操作非原子**：状态读取分多步但无写操作，最多造成视图不一致
3. **金额限制充分**：单笔跨链金额有严格上限（如 < 0.1% TVL），即使卡住影响有限
4. **双边监控机制**：链下 relayer 实时监控中间态，自动触发恢复交易，历史成功率 > 99.9%
5. **状态机完整性**：虽然非原子但所有中间态可追溯且可回滚，无资产损失可能
6. **测试网或早期版本**：尚未处理真实资产，且文档明确标注实验性质

**不应降级的情况：**
- 即使有恢复机制，若依赖单点人工介入（非自动化/去中心化），不应低于 Medium
- 若历史曾发生过资产卡死事件，即使修复也应标记 Medium 以上
