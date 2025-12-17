# Vyper 治理 MEV 审计指南

## Details

**代码示例特征：**
```vyper
@external
def vote(proposal_id: uint256, support: bool):
    assert self.proposals[proposal_id].deadline > block.timestamp
    assert self.balances[msg.sender] > 0
    
    if support:
        self.proposals[proposal_id].yes_votes += self.balances[msg.sender]
    else:
        self.proposals[proposal_id].no_votes += self.balances[msg.sender]
```

**快速定位核心操作（L2-跳读）：**
- 关注 `vote/cast_vote/submit_vote` 等治理函数
- 检查 `snapshot/checkpoint/delegation` 状态更新逻辑
- 追踪投票权重计算：`balanceOf/getPriorVotes/getVotes`
- 查找 `proposal.forVotes/againstVotes` 累加操作

**快速定位保护机制（L3-逐行读）：**
- 是否存在 `commit-reveal` 模式：`commit_hash/reveal_vote`
- 时间锁检查：`votingDelay/votingPeriod/timelock`
- 快照机制：`snapshot_block/proposalSnapshot`
- 投票私密性：是否使用 `keccak256(vote_data + secret)`
- Gas竞价保护：`maxPriorityFeePerGas` 限制或排序规则

## Classify

**确认为漏洞：**
- 投票结果即时可见且直接影响链上执行（如直接触发资金转移、参数修改）
- 投票权重在投票时才快照，可被抢先增持代币操控
- 临界状态可被单笔交易翻转（如 50.1% vs 49.9%）

**判定为误报：**
- 已实现提案创建时快照（`block.number` 固定）
- 投票结果仅记录不自动执行，需额外 `timelock + queue`
- 使用链下签名聚合（EIP-712）+ 批量上链

**代码异味：**
- 使用 `block.timestamp` 而非 `block.number` 作为截止时间
- 投票结果可通过事件日志实时追踪但有延迟执行
- 缺乏最小提案阈值（`proposalThreshold`）

## Low risk

- **低价值治理：** 仅控制非财务参数（如UI显示、说明文字）
- **高共识场景：** 投票差距 >80% 且单一MEV无法逆转
- **代理投票模式：** 委托关系固定，非即时改变
- **链下治理为主：** Snapshot等链下平台记录，链上仅执行最终结果
- **已设置 Timelock：** 执行延迟 >24小时，社区有反应窗口
- **Quorum过高：** 需要 >67% 参与率才能通过，单一攻击者难以达成

## 审计专业技巧：区分真实漏洞与误报

### 1. 快照检查技巧

**真实漏洞信号：**
```vyper
# 危险：使用当前余额而非历史快照
voting_power: uint256 = self.token.balanceOf(msg.sender)
self.votes[proposal_id][msg.sender] = voting_power

# 问题：攻击者可在投票前flash loan增持，投票后立即还款
# 示例：使用100倍杠杆flash loan，一笔交易内完成增持→投票→还款
```

**误报场景识别：**
```vyper
# 正确：使用历史快照块号
voting_power: uint256 = self.token.balanceOfAt(msg.sender, self.proposal_snapshot_block)

# 审计判断：
# ✓ balanceOfAt 来自 OpenZeppelin ERC20Votes 或 Compound cToken
# ✓ snapshot_block 在 proposal 创建时记录，不可修改
# ✓ 即使当前余额变化，也无法影响投票权重
```

### 2. 时间锁绕过检查清单

| 检查项 | 真漏洞表现 | 误报表现 |
|--------|----------|--------|
| **Timelock Duration** | <2 分钟或无timelock | >6小时且由多签控制 |
| **即时执行路径** | vote→直接transfer/call | vote→queue→delay→execute 需要分别调用 |
| **治理参数修改** | 更改timelock自身延迟 | timelock初始化后不可改 |
| **紧急模式** | 无条件跳过timelock | 需要特定权限（如5位多签同意） |

**实战例子：**
```vyper
# 真漏洞：三层治理绕过
@external
def execute_proposal(proposal_id: uint256):
    # Layer 1: 链上投票（可被sandwich）
    # Layer 2: 仅检查 "投票已结束"，未检查timelock
    # Layer 3: 直接执行（无延迟）
    assert self.proposals[proposal_id].voting_ended
    self._execute(self.proposals[proposal_id].target, self.proposals[proposal_id].data)
```

### 3. 投票权重曲线陷阱

**常见误报原因：** 审计员看到"可修改投票权"就标记为漏洞，但未检查修改的实际效果

**正确审计流程：**
1. **追踪权重读取点** → 找到 `balanceOf/getVotes` 被调用的位置
2. **检查读取时机** → 是否在投票时读取（风险）或早期快照（安全）
3. **验证权重冻结** → 投票后权重变化是否影响该票的统计
4. **测试时间窗口** → 从 proposal 创建到投票结束，权重何时被冻结

**代码对比：**
```vyper
# 误报案例：看起来有漏洞，实际安全
# 担心：投票后 delegate() 可改变权重分配
checkpoint_block: public(uint256)
@external
def cast_vote(proposal_id: uint256):
    # ✓ 使用当前块号快照（虽然名字可能误导）
    votes: uint256 = self.token.balanceOfAt(msg.sender, self.checkpoint_block)

# 实际上 checkpoint_block 在 proposal 创建时确定，不会改变
# 即使投票者后续 delegate，也不影响该 proposal 的统计
```

### 4. 重放攻击与签名验证陷阱

**真漏洞：**
```vyper
# 危险：缺乏 nonce 或 chain_id
@external
def vote_with_signature(proposal_id: uint256, support: bool, v: uint8, r: bytes32, s: bytes32):
    message: bytes32 = keccak256(concat(proposal_id, support))
    # ❌ 缺乏 nonce、chain_id、合约地址
    # 问题：同一投票可在多条链重放，或被同一提案重复使用
    signer: address = ecrecover(message, v, r, s)
    self.votes[proposal_id][signer] = True
```

**正确实现（低风险）：**
```vyper
# EIP-712 标准（安全）
domain_separator: constant(bytes32) = keccak256(...)  # 包含 chain_id
nonce: public(HashMap[address, uint256])

message: bytes32 = keccak256(concat(
    domain_separator,
    proposal_id,
    support,
    nonce[msg.sender],
    deadline
))
nonce[msg.sender] += 1  # 防重放
```

### 5. 边界条件与整数溢出

**实战检查项：**
- 投票累加是否使用 `uint256` 还是更小的类型？→ 检查 `max_votes` 是否可能溢出
- 百分比计算 `(yes_votes * 100) // total_votes` → 检查是否先乘后除（防精度损失）
- 临界状态 `yes_votes == no_votes` → 是否有明确的平局处理规则？

```vyper
# 误报例：看起来有风险，实际无法触发
total_votes: uint256 = MAX_UINT256  # 设定最大值
@external
def vote(...):
    # total_votes 不会超过 MAX_UINT256 吗？
    # ✓ 正确：代币总供应量 < MAX_UINT256，不可能溢出
    total_votes += voter_balance
```

### 6. 审计决策树：3个关键问题

```
攻击成本 > 收益？
├─ YES → 低风险，结束
└─ NO → 继续

投票结果立即执行？
├─ YES（无timelock）→ 高风险
└─ NO（有timelock）→ 继续

攻击需要控制 >50% 代币权重？
├─ YES → 中等风险（取决于代币流动性）
└─ NO → 高风险
```

### 7. 常见误报案例库

| 代码特征 | 初判 | 正确判断 | 原因 |
|---------|------|--------|------|
| `block.timestamp` 作为deadline | ⚠️ 风险 | ✓ 可接受 | 精确度±15秒无损，与gas价格无直接关联 |
| 投票权重可修改 | ❌ 漏洞 | ✓ 安全 | 若在fast-path前快照，后续修改无效 |
| 无commit-reveal | ⚠️ 高风险 | ✓ 低风险 | 链上投票可见但执行需timelock >24h |
| delegatecall 在治理中 | ❌ 严重 | ✓ 常见 | 需验证合约是否initialized、权限检查 |

### 8. Vyper特定的审计注意事项

- **内部函数与外部函数边界** → Vyper 无 `internal` 关键字，默认 `@internal` 需显式检查
- **事件日志完整性** → Vyper 事件定义后自动indexed参数，检查是否遗漏关键变量
- **数值类型安全** → `uint128` 在投票计数中可能溢出（总供应量 >2^128 的token）
