# Vyper 治理截止时间绕过 (Governance Deadline Bypass)

## Details

### 代码示例

```vyper
# 易受攻击的治理合约
proposals: public(HashMap[uint256, Proposal])
voting_period: public(uint256)

struct Proposal:
    deadline: uint256
    votes_for: uint256
    votes_against: uint256
    executed: bool

@external
def create_proposal(proposal_id: uint256) -> bool:
    self.proposals[proposal_id].deadline = block.timestamp + self.voting_period
    return True

@external
def vote(proposal_id: uint256, support: bool):
    # 问题点：仅依赖 block.timestamp 判断截止时间
    assert block.timestamp <= self.proposals[proposal_id].deadline, "Voting ended"
    if support:
        self.proposals[proposal_id].votes_for += 1
    else:
        self.proposals[proposal_id].votes_against += 1

@external
def execute_proposal(proposal_id: uint256):
    # 截止判断依赖时间戳
    assert block.timestamp > self.proposals[proposal_id].deadline, "Voting ongoing"
    assert not self.proposals[proposal_id].executed, "Already executed"
    # 执行提案逻辑...
```

### 快速定位核心操作技巧 **【L2:跳读】**

1. **搜索时间戳比较**：定位 `block.timestamp`、`<=`、`>=`、`<`、`>` 组合使用位置
2. **关注状态变更窗口**：查找 `deadline`、`end_time`、`voting_period`、`timelock` 等字段
3. **追踪提案生命周期**：从创建 → 投票 → 执行流程中的时间检查点
4. **检查 struct/HashMap**：治理提案通常存储在结构体中，关注时间相关字段

### 快速定位保护机制技巧 **【L3:逐行读】**

1. **区块号辅助验证**：检查是否同时使用 `block.number` 作为时间锚点
2. **缓冲期设计**：查找 `grace_period`、`buffer_time`、`min_delay` 等缓冲机制
3. **多签确认**：是否要求 `admin`、`multisig`、`quorum` 等权限二次确认
4. **时间容差检查**：是否有 `MAX_TIMESTAMP_DRIFT`、时间合理性验证
5. **事件日志完整性**：关键时间点是否记录 `log` 事件用于链下监控

## Classify

### 漏洞判定标准

- **高危漏洞**：截止时间判断完全依赖 `block.timestamp`，且涉及资金转移、权限变更、协议参数修改等关键操作，矿工可通过 ±900s 时间漂移影响投票结果或提案执行
- **中危漏洞**：虽依赖时间戳但有额外保护（如多签、时间锁），但保护机制可被绕过或失效场景存在
- **低危漏洞**：时间戳依赖存在但影响有限（如仅影响非关键功能），或窗口期足够长（>24小时）使得漂移影响可忽略

### 误报场景

- 时间戳仅用于记录而非逻辑判断（如 `created_at` 字段仅用于前端显示）
- 已有区块号双重验证机制确保时序正确性
- 时间窗口极长（>7天）且截止后无即时执行逻辑

### 代码异味

- 使用 `block.timestamp` 但未配套合理性检查（如防止时间回退）
- 缓冲期设置过短（<1小时）
- 截止判断使用 `==` 而非 `<=` / `>=`（可能因时间戳跳过导致永久卡死）

## Low risk

### 低风险评级场景

1. **超长投票周期**：`voting_period` > 7天，900s 漂移对总体投票期影响 <0.15%
2. **仅记录用途**：时间戳仅用于 `log` 事件或前端展示，不影响合约逻辑分支
3. **非关键治理**：提案仅涉及参数微调（如费率 0.1% → 0.2%），非核心权限变更
4. **紧急暂停机制**：存在 `pause()` 功能可由多签立即冻结异常提案
5. **链下监控补偿**：配套完善的链下监控系统可及时发现时间异常并触发应急响应
6. **时间锁叠加**：除截止时间外，提案执行还需等待固定区块数（如 `block.number + 100`）
