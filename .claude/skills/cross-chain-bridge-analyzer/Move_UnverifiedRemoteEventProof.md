# Move_UnverifiedRemoteEventProof | 未验证远程事件证明

**漏洞类型**：跨链桥 - 事件验证缺陷  
**影响链**：Aptos / Sui  
**风险等级**：Critical

## Details

### 代码示例
```move
// 典型漏洞模式：直接接受中继器提交的事件数据
public entry fun process_cross_chain_mint(
    relayer: &signer,
    user: address,
    amount: u64,
    event_hash: vector<u8>,
    chain_id: u64
) acquires Bridge {
    let bridge = borrow_global_mut<Bridge>(@bridge_addr);
    // ❌ 未验证 event_hash 在源链的真实性
    // ❌ 未验证 Merkle Proof / Light Client 证明
    // ❌ 未验证多签 Guardian 签名
    coin::mint_to<BridgedToken>(user, amount);
    event::emit(MintEvent { user, amount });
}
```

### 核心操作定位技巧 (L3-L4)
- **关键函数特征**：`process_*`, `handle_*`, `relay_*`, `execute_cross_chain_*`
- **参数红旗**：接受 `event_hash`/`proof`/`message` 但未调用验证模块
- **资产操作后置**：直接 `mint`/`transfer`/`withdraw` 而无前置验证逻辑
- **审计路径**：
  1. **L3-逐行读**：检查入口函数的参数处理流程
  2. **L4-跨模块追踪**：确认是否调用独立的 `verify_proof` 模块
  3. **L4-Guardian依赖**：追踪多签验证器地址集合的更新权限

### 保护机制定位技巧 (L2-L4)
- **L2-跳读扫描**：搜索 `verify`, `proof`, `merkle`, `signature`, `guardian`
- **L3-逐行确认**：
  - Merkle Tree 验证：`verify_merkle_proof(root, leaf, proof)`
  - Light Client：`verify_block_header(height, validators, proof)`
  - 多签机制：`verify_guardian_signatures(msg_hash, signatures, threshold)`
- **L4-状态追踪**：
  - Guardian 集合存储位置：`GuardianSet` resource
  - 证明根存储：`verified_roots: Table<u64, vector<u8>>`
  - Nonce/Sequence 防重放：`processed_sequences: Table<vector<u8>, bool>`

## 审计专业技巧与误报区分

### 🔍 实战审计核心步骤

#### 1. 验证链完整性检查
```move
// ✅ 正确做法：三层验证
public fun process_bridge_transfer(
    user: address,
    amount: u64,
    proof: vector<u8>,
    message_hash: vector<u8>,
    signatures: vector<vector<u8>>
) acquires BridgeState {
    let state = borrow_global_mut<BridgeState>(@bridge);

    // 第一层：Merkle 证明验证（源链事件）
    assert!(
        verify_merkle_proof(&state.root, &proof, &message_hash),
        E_INVALID_PROOF
    );

    // 第二层：多签验证（Guardian 集合）
    verify_guardian_sigs(message_hash, signatures, state.quorum);

    // 第三层：防重放检查（Nonce）
    assert!(!table::contains(&state.processed, &message_hash), E_ALREADY_PROCESSED);
    table::add(&mut state.processed, message_hash, true);

    coin::mint_to<BridgedToken>(user, amount);
}
```

#### 2. 真实漏洞特征识别（必现红旗）
| 特征 | 严重度 | 识别方法 |
|------|--------|---------|
| **完全缺失验证** | Critical | grep -r "mint\|transfer" 后 3 行内无 assert/verify 调用 |
| **验证被跳过** | Critical | verify 函数存在但入口函数未调用，或存在无条件分支跳过验证 |
| **单点信任** | High | 整个跨链操作依赖单一 signer 权限，无多签/证明 |
| **硬编码 Guardian** | High | Guardian 地址写死在代码中，无法更新或仅 admin 可改 |
| **无重放保护** | High | 同一 message_hash/sequence 可多次处理 |

#### 3. 常见误报陷阱与区分

**误报场景 A：链下验证模式**
```
❌ 审计员误判："智能合约中无验证逻辑，存在漏洞！"
✅ 实际情况分析：
   - 链下签名服务已验证事件并生成多签证明
   - 合约仅负责验证签名（密码学验证已做）
   - 需追踪：验证服务的可信度 + 签名阈值 + 更新机制

区分方法：
   1. 搜索是否调用 ed25519::verify() / ecdsa::verify()
   2. 追踪多签参与者是否由多链治理控制
   3. 确认签名生成服务的代码开源性
```

**误报场景 B：乐观验证 + 挑战期**
```
❌ 审计员误判："链上未验证，直接 mint，存在漏洞！"
✅ 实际情况分析：
   - 使用乐观验证：先 mint，后续可由 validator 挑战
   - 挑战期内 (如 7 天) 任何人可提交欺诈证明
   - 若验证为假，自动 burn 代币 + 惩罚中继器

区分方法：
   1. 搜索 "challenge", "fraud", "dispute_period"
   2. 确认欺诈证明的验证逻辑完整性
   3. 验证 burn/惩罚机制是否自动执行
   4. 评估挑战期长度是否合理（< 7 天视为高风险）
```

**误报场景 C：分阶段部署**
```
❌ 审计员误判："验证函数只有 TODO 注释，未实现！"
✅ 实际情况分析：
   - Phase 1：部署验证框架（仅在主网部署前激活）
   - Phase 2：逐步启用 Guardian 集合
   - 当前处于测试网阶段

区分方法：
   1. 检查部署文件/合约升级历史（git blame）
   2. 追踪主网部署时间表
   3. 确认测试网标签是否显式标注
```

#### 4. Guardian 集合管理审计清单

```move
// ⚠️ 危险模式：单一 admin 控制
public fun update_guardian_set(
    admin: &signer,
    new_guardians: vector<address>
) acquires GuardianState {
    assert!(signer::address_of(admin) == @admin, E_UNAUTHORIZED); // ❌ 单点
    let state = borrow_global_mut<GuardianState>(@bridge);
    state.guardians = new_guardians;
}

// ✅ 安全模式：多签 + 时间锁
public fun propose_guardian_update(
    proposer: &signer,
    new_guardians: vector<address>
) acquires GovernanceState {
    let state = borrow_global_mut<GovernanceState>(@bridge);
    vector::push_back(&mut state.proposals, GuardianProposal {
        new_guardians,
        execute_at: timestamp::now_seconds() + TIMELOCK_DURATION, // 24-48h
        approvals: vector::empty(),
    });
}

public fun execute_guardian_update(proposal_id: u64) acquires GovernanceState {
    let state = borrow_global_mut<GovernanceState>(@bridge);
    let proposal = vector::borrow(&state.proposals, proposal_id);

    // 验证时间锁
    assert!(timestamp::now_seconds() >= proposal.execute_at, E_TIMELOCK_ACTIVE);

    // 验证多签阈值
    assert!(
        vector::length(&proposal.approvals) >= state.quorum,
        E_INSUFFICIENT_APPROVALS
    );

    // 执行更新
    borrow_global_mut<GuardianState>(@bridge).guardians = proposal.new_guardians;
}
```

#### 5. 重放攻击防护检查

```move
// ❌ 缺陷：无 nonce 或 sequence number
public fun process_mint(hash: vector<u8>, amount: u64) { ... }

// ✅ 安全：使用 nonce 防重放
public fun process_mint(
    hash: vector<u8>,
    amount: u64,
    sequence: u64  // 递增序列号
) acquires Bridge {
    let state = borrow_global_mut<Bridge>(@bridge);

    // 防重放检查
    assert!(sequence > state.last_sequence, E_REPLAY_ATTACK);
    state.last_sequence = sequence;

    // ✅ 或使用 Table 记录已处理
    assert!(!table::contains(&state.processed, &hash), E_ALREADY_PROCESSED);
    table::add(&mut state.processed, hash, true);

    coin::mint_to<BridgedToken>(user, amount);
}
```

### Classify

### ✅ 确认为漏洞
- 跨链铸造/解锁函数**完全缺失**证明验证逻辑
- 仅依赖中继器的 `signer` 权限而无额外密码学验证
- 验证函数存在但**永不调用**或可被绕过
- Guardian 集合由单一 admin 控制且无时间锁
- 无重放防护（sequence/nonce），同一消息可多次执行

### ⚠️ 潜在误报
- 系统使用**链下验证 + 链上签名检查**模式（需确认签名算法 + Guardian 可信度）
- 使用**乐观验证 + 挑战期**方案（需确认欺诈证明完整 + 挑战期足够长）
- 验证逻辑在**前置模块**已完成（需完整追踪调用链，确认非外部可绕过）
- 测试网代码标注为 `TODO: add verification`（需确认主网有完整实现）

### 🟡 代码异味
- 验证存在但阈值过低（如 1/3 多签，应为 2/3 以上）
- Guardian 更新频率过高（<24h），应有时间锁
- 使用自定义哈希而非标准 Keccak256/SHA3
- Guardian 集合修改权限未托管至多链治理

## Low risk

### 降级为 Low 的场景
1. **沙盒环境**：跨链桥仅处理测试代币，无真实经济价值
2. **严格白名单**：仅 Guardian 地址可调用，且 Guardian 由多链多签控制
3. **金额上限**：单笔 < $1000 且日累计 < $10000
4. **有效监控**：存在链下监控系统可在 5 分钟内暂停桥合约
5. **完善回滚机制**：支持挑战期 + 欺诈证明的乐观验证方案

### 仍需关注
即使降级为 Low，仍需在报告中标注：
- Guardian 集中化风险（需披露节点运营商）
- 乐观验证的挑战期长度（< 7天视为不足）
- 紧急暂停权限是否去中心化
