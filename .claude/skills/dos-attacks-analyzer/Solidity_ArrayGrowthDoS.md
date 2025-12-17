# Solidity - 数组增长 DoS

数组无限增长但遍历时未分页，导致 Gas 消耗超出区块上限，常见于批量转账、奖励分发、治理投票、清算回调等业务逻辑。

## Details

**典型代码模式：**
```solidity
address[] public users;

function addUser(address user) external {
    users.push(user);  // 无上限增长
}

function distributeRewards() external {
    for (uint i = 0; i < users.length; i++) {  // 遍历全部数组
        token.transfer(users[i], reward);
    }
}
```

**快速定位核心操作（L2-L3）：**
- 关注动态数组的 `push/pop` 操作，追踪数组写入点
- 搜索 `for` 循环中使用 `.length` 作为上界的遍历逻辑
- 识别批量操作函数：`distribute*/batch*/claim*All/refund*` 等命名
- 检查循环内是否包含 `external call`（CALL/DELEGATECALL/STATICCALL）

**快速定位保护机制（L1-L2）：**
- 关键词：`maxLength/limit/cap/pageSize/batchSize/MAX_*`
- `require(array.length <= MAX_)` 在写入前的长度检查
- 分页参数：`startIndex, endIndex, offset, limit, page` 
- 循环上界使用 `min(length, MAX_BATCH)` 或传入参数而非 `.length`
- `gasleft()` 条件退出或计数器限制

## Classify

**确认为漏洞：**
- 数组可被任意用户或多次增长，且无实际上限
- 遍历操作在公开函数中，影响关键业务（分发/结算/投票）
- Gas 消耗可达区块 Gas Limit（实测或静态估算超 1500 万）

**判定为误报：**
- 数组由 `onlyOwner` 或受信角色控制，且治理可信
- 数组有明确业务上限（如固定委员会成员≤20）
- 遍历函数为 `view/pure`，仅供链下查询

**归类为代码异味：**
- 数组理论上可增长但业务场景下实际受限（需额外审查业务逻辑）
- 已有分页但页大小仍过大（如 `batchSize=500`）
- 存在保护机制但实现不完善（如仅检查输入参数未限制数组总长）

## Low risk

- 数组增长速度受经济成本约束（每次 push 需支付高额费用）
- 数组上限由可信多签动态调整，且有监控机制
- 遍历操作仅在紧急状态下由管理员触发，非常规业务流程
- 合约已部署但数组当前长度较小（<50），且业务即将下线/迁移
- 存在替代方案可绕过遍历操作完成核心功能

## 审计专业技巧

### 1. 静态关键词搜索策略
**关键词组合**（需同时出现多个才判定为真漏洞）：
- `users.push()` + `for(uint i; i < users.length)` → **确认漏洞**
- `array.push()` + `onlyOwner` 修饰 + 固定委员会数 → **误报**
- `batch*/claim*All` 函数 + `require(array.length <= MAX_)` → **已修复，需检查 MAX_ 值**

**正反例对比**：
```solidity
// ❌ 真实漏洞
function claimAllRewards() external {
    for(uint i; i < claimants.length; i++) {  // 无限制遍历
        _processReward(claimants[i]);
    }
}

// ✅ 已修复（但仍需验证 MAX_BATCH）
function claimRewardsBatch(uint startIdx, uint endIdx) external {
    require(endIdx - startIdx <= MAX_BATCH, "batch too large");
    for(uint i = startIdx; i < endIdx; i++) {
        _processReward(claimants[i]);
    }
}
```

### 2. 真实漏洞与误报的区分经验

**真实漏洞的三个必备条件**（缺一不可）：
1. **数组可无限增长**：任意用户可调用，或团队无 EOA 操作约束
2. **必须在公开调用路径中遍历**：非 view/pure，影响状态转变或资金流向
3. **Gas 消耗超过区块限制**：每项操作成本 > 20K Gas，数组 > 100 项时必然超 15M Gas limit

**误报常见场景**：
- **场景A**：Voting 合约中 `getVoters()` 返回投票者列表
  - 标记：`view` 函数 → **误报**，仅供链下查询

- **场景B**：Governance 中 `delegateBatch()` 批量转移投票权
  - 标记：`require(delegates.length <= 100)` 已检查 → **需进一步审查**
  - 陷阱：检查值存储在常量 `MAX_DELEGATES`，但没有在 `add()` 时同步检查

- **场景C**：Staking 池中 `distributeRewards()` 给所有质押者
  - 标记：奖励分发是周期性的（每周一次），当前质押者 < 1000
  - 陷阱：**忽略未来增长空间**，需评估 12 个月后预期规模

### 3. Gas 成本估算（实战快速判定）

**快速公式**：`总 Gas = (循环体 Gas × 数组长度) + 额外操作`

| 循环体操作 | 单次成本 | 安全数组大小 |
|-----------|--------|-----------|
| `token.transfer()` + 状态写入 | ~50K Gas | < 300 |
| `_processClaim()` 含内部调用 | ~30K Gas | < 500 |
| 纯数据查询 + mapping 更新 | ~5K Gas | > 3000 |
| 外部合约调用（Oracle/DEX） | ~100K+ Gas | < 150 |

**快速验证方法**：
```bash
# 从区块浏览器查询历史 tx，找到类似操作的 Gas 使用记录
# Etherscan: 搜索该合约的 batchDistribute/claimAll 交易
# 如果成功 tx 的 gas used < 14M，且数组当前 < 100，风险等级降低
```

### 4. 代码异味到漏洞的演进路径

**代码异味 (Warning)**
```solidity
address[] public whitelistUsers;  // 未来可能增长
function addWhitelistBatch(address[] calldata newUsers) external onlyOwner {
    for(uint i; i < newUsers.length; i++) {
        whitelistUsers.push(newUsers[i]);
    }
}
// 风险：onlyOwner 限制了写入，但遍历逻辑仍在公开接口中
```

**漏洞演进点**：
- 若出现公开的遍历函数：`getWhitelistLength()` 返回全部成员 → **升级为漏洞**
- 若 Governance 移除 onlyOwner：`whitelistUsers` 的 push 权限开放 → **高危漏洞**

### 5. 审计检查清单

**Phase 1 - 搜索阶段**（5 分钟）
- [ ] 全局搜索 `.push()/pop()` 操作，标记所有动态数组
- [ ] 搜索 `for/while` 循环中的 `.length`，追踪遍历点
- [ ] 关键词：`claim*All, distribute*, batch*` 等风险函数

**Phase 2 - 权限分析**（5-10 分钟）
- [ ] 数组写入操作是否有 `onlyOwner/onlyRole` 等权限限制
- [ ] 数组是否有明确的 `require(array.length <= MAX_)` 检查
- [ ] 权限修饰符是否可被 Governance 移除或更改

**Phase 3 - 业务影响评估**（10-15 分钟）
- [ ] 遍历函数是否为 `public/external`，还是仅 `internal/private`
- [ ] 是否存在备选方案（如 mapping 替代 array，链下计算等）
- [ ] 当前主网部署的数组规模是多少（通过区块浏览器验证）

**Phase 4 - 成本验证**（可选，高风险时执行）
- [ ] 本地 Fork 测试，计算单次完整遍历的实际 Gas 消耗
- [ ] 推算当前数组大小 + 预期增长速度下的 Gas 需求
