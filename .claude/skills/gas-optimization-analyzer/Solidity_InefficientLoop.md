# Solidity 低效循环 (Inefficient Loop)

**漏洞类型**：Gas 优化  
**常见场景**：资产分发、费用收取、用户奖励计算、批量操作、空投发放、白名单验证

## Details

**典型代码示例**：

```solidity
// 场景1：循环中多次读取状态变量 (SLOAD ~2100 gas)
function distribute(address[] memory users) external {
    for(uint i = 0; i < users.length; i++) {
        require(totalSupply > 0, "empty"); // 每次循环读取状态变量
        balances[users[i]] = rewardRate * userStake[users[i]]; // 多次SLOAD
    }
}

// 场景2：循环中重复 require 检查
function batchTransfer(address[] calldata recipients, uint amount) external {
    for(uint i = 0; i < recipients.length; i++) {
        require(!paused, "paused"); // 循环内重复检查
        require(amount > 0, "zero"); // 不变条件重复验证
        _transfer(msg.sender, recipients[i], amount);
    }
}

// 场景3：未缓存数组长度
function processUsers(address[] storage users) internal {
    for(uint i = 0; i < users.length; i++) { // 每次迭代 SLOAD
        _process(users[i]);
    }
}

// 场景4：循环中多次 SSTORE
function updateBalances(address[] calldata users, uint[] calldata amounts) external {
    for(uint i = 0; i < users.length; i++) {
        totalAllocated += amounts[i]; // 每次循环写入状态变量
        balances[users[i]] = amounts[i];
    }
}
```

**快速定位核心操作技巧**（L2-L3：跳读至逐行读）：
- 锁定 `for`/`while` 循环体，重点关注循环变量初始化、条件判断、迭代步长
- 扫描循环内状态变量访问：`storage` 读写、`mapping` 查询、全局变量引用
- 检查循环边界：`array.length`、`i++` vs `++i`、是否缓存长度
- 识别循环依赖：当前迭代是否依赖上次迭代结果（累加器模式）

**快速定位保护机制技巧**（L1-L2：关键词扫描至跳读）：
- 检查循环前置条件：`require(array.length <= MAX_BATCH)` 等上限限制
- 查找局部缓存：`uint len = array.length`、`Type memory temp = stateVar`
- 验证计数器优化：`++i` 代替 `i++`、`unchecked` 块
- 确认存储模式：`memory` vs `storage`、`calldata` 参数类型
- 关注 gas 退款机制：循环中的 `SSTORE` 归零操作

## Classify

**漏洞判定标准**：
1. 循环次数无上限或仅受外部输入控制，存在 DoS 风险 → 中高危漏洞
2. 循环内状态变量访问频率 × 预期迭代次数 > 5000 SLOAD 或导致交易 gas 超区块限制 → 漏洞
3. 核心功能因 Gas 消耗过高而无法正常执行 → 功能性漏洞

**误报识别**：
1. 循环次数由合约内部常量严格控制（如 `< 10` 次），即使未优化也不构成实质风险
2. 状态变量在循环中仅读取 1-2 次且循环上限 < 20
3. 一次性初始化函数（仅 owner 调用且明确说明高 Gas）

**代码异味判定**：
1. 存在优化空间但不影响功能可用性（如小规模批量操作未缓存长度）
2. Gas 节省 < 10% 的微小优化点
3. 可读性与 Gas 效率的权衡场景（团队明确选择可读性优先）

## Low Risk

**低风险评级适用场景**：
1. **循环次数硬编码上限** < 50 且为非核心功能（如管理员批量设置参数）
2. **单次 Gas 成本明确可控**：未优化代码 Gas 消耗 < 500k 且用户明确知晓成本
3. **低频调用路径**：仅在特殊事件触发（如紧急暂停后批量退款，预期一年 < 5 次）
4. **渐进式处理设计**：提供分页/分批接口，用户可拆分大任务为多笔交易
5. **临时状态或测试代码**：明确标注 `// TODO: optimize before mainnet` 且在非生产环境
6. **Gas 节省 < 5%**：优化收益边际，审计资源优先投入高影响问题
7. **已有补偿机制**：协议设计包含 Gas 补贴或链下计算方案作为备选
