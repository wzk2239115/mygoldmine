# Solidity_MissingCalldata

**成因**：external/public函数的复杂类型参数（数组、结构体、字符串）使用memory而非calldata，导致EVM将调用数据从calldata区域复制到memory区域，产生额外的gas消耗和内存分配开销。

**典型场景**：批量转账、多签验证、白名单校验、元数据更新、批量mint/burn、数据聚合查询等需要传递数组或结构体的external函数。

## Details

**代码示例**：
```solidity
// ❌ Gas浪费
function batchTransfer(address[] memory recipients, uint256[] memory amounts) external {
    for(uint i = 0; i < recipients.length; i++) {
        _transfer(msg.sender, recipients[i], amounts[i]);
    }
}

// ✓ 优化后
function batchTransfer(address[] calldata recipients, uint256[] calldata amounts) external {
    for(uint i = 0; i < recipients.length; i++) {
        _transfer(msg.sender, recipients[i], amounts[i]);
    }
}
```

**定位核心操作技巧**（L2-跳读）：
- 扫描所有external/public函数签名
- 重点关注参数类型：`memory`关键字 + 复杂类型（`[]`数组、`struct`、`string`、`bytes`）
- 优先审查高频调用函数：batch类、multicall类、批量查询类
- 忽略internal/private函数（必须使用memory）

**定位保护机制技巧**（L0-快速跳过）：
- 该问题无安全风险，纯gas优化项
- 无需检查access control、reentrancy guard等防护
- 函数逻辑正确性不受影响，可快速标记后继续

## Classify

**漏洞判定标准**：
- ✓ 漏洞：external函数 + memory修饰的引用类型 + 函数内仅读取不修改参数
- ✗ 误报：函数需要修改参数内容（calldata只读），或参数需要传递给internal函数（会强制转换）
- △ 代码异味：public函数使用memory（可能被internal调用，需结合调用链判断）

**特殊场景**：
- 如果参数需要传递给要求memory类型的库函数/接口，则为误报
- 如果函数体内对参数进行赋值/修改操作，则为误报
- 如果Solidity版本 < 0.6.9（calldata支持不完善），建议降级为代码异味

## Low risk

**低风险评级场景**：
- 函数调用频率极低（仅初始化时调用一次）
- 参数数组长度固定且很小（≤3个元素）
- 合约已部署且gas消耗在可接受范围内
- 代码可读性/维护性考虑优先于gas优化（团队明确决策）
- 存在框架/接口强制要求使用memory的情况

## 审计专业技巧

### 1. 隐蔽的类型转换陷阱

**真实漏洞示例**：
```solidity
// ✓ 真正的漏洞：calldata可以改进
function submitBids(Bid[] calldata bids) external {
    for(uint i = 0; i < bids.length; i++) {
        processBid(bids[i]); // 函数接收struct值，自动拷贝
    }
}

// ❌ 常见误报：需要传给memory友好的库
function submitBids(bytes[] memory data) external {
    for(uint i = 0; i < data.length; i++) {
        keccak256(data[i]); // 某些版本库函数需要memory
    }
}
```

**审计技巧**：追踪参数在函数体内的使用方式
- 参数仅用于 **读取** 和 **直接传递** → 改为calldata
- 参数传给要求memory的库/接口 → 保持memory（文档记录原因）
- 参数需要 **修改/编辑** → memory是必须的

### 2. public函数的多路调用链分析

**高危遗漏场景**：
```solidity
contract VulnerableMultisig {
    // ❌ 误报案例：看起来是漏洞，其实不是
    function executeTransactions(Transaction[] memory txs) public onlyOwner {
        for(uint i = 0; i < txs.length; i++) {
            _execute(txs[i]); // 内部函数接收参数
        }
    }

    // internal函数接收memory类型，caller可能是public
    function _execute(Transaction memory tx) internal {
        (bool success, ) = tx.target.call(tx.data);
        require(success);
    }
}
```

**正确判断方法**：
- 跟踪所有调用该public函数的路径（包括internal链）
- 如果存在internal函数强制要求memory → 保持memory
- 如果internal函数也可以改为calldata → 两层都改进

### 3. 数组长度验证的"实际消耗"陷阱

**常见的成本-收益错估**：
```solidity
// ❌ 大数组场景下，calldata优化明显
function batchVerifySignatures(bytes[] calldata sigs) external {
    // 100个签名时：calldata节省约3000-5000 gas
    require(sigs.length <= 100);
    for(uint i = 0; i < sigs.length; i++) {
        verifySig(sigs[i]);
    }
}

// ✓ 但以下情况memory反而是对的
function batchVerifySignatures(bytes[] memory sigs) external {
    // 原因：sigs需要在internal函数中被修改/过滤
    filterAndSort(sigs); // 此函数修改入参
}
```

**审计规则**：
- 参数数组>20个元素 AND 仅读取 → 强烈推荐改为calldata
- 参数数组<5个元素 → 考虑维护成本，可接受保持memory
- 嵌套struct数组 → calldata优化收益最大（10000+ gas）

### 4. 版本兼容性与部署后分析

**真实的"误报检测器误报"场景**：
```solidity
pragma solidity ^0.6.0; // ❌ Solidity 0.6.x对calldata struct支持有限

// Solidity 0.6.0-0.6.8：不支持 struct calldata
function swap(SwapData memory data) external {
    // 在这个版本，改为calldata会编译失败！
}

// Solidity 0.6.9+：完全支持
function swap(SwapData calldata data) external {
    // 现在可以安全使用calldata
}
```

**审计清单**：
- [ ] 检查pragma solidity版本
- [ ] 若版本<0.6.9，struct calldata标记为"升级后可优化"
- [ ] 若已是0.7.0+，struct calldata是明确的漏洞

### 5. 合约升级与代理模式的陷阱

**真实的审计失分案例**：
```solidity
// UUPS代理合约中，external函数被upgradeable logic调用
contract LogicV1 {
    // ❌ 看起来是漏洞，但在代理环境中可能有特殊原因
    function setConfig(Config[] memory configs) external onlyAdmin {
        // 某些ABI兼容性要求必须是memory
    }
}
```

**防止误报的检查**：
- [ ] 合约是否使用了Proxy模式？
- [ ] 是否有接口/ABI兼容性约束？
- [ ] external函数是否被其他合约硬编码调用？
- 如果有以上任何一个，改calldata需要深入协议分析

### 6. 成本-收益量化评估表

| 场景 | 数组类型 | 元素数 | 预期节省Gas | 优先级 | 风险 |
|------|---------|--------|----------|--------|------|
| batch转账 | address[] | 50+ | 4000-8000 | 🔴高 | 低 |
| 数据聚合 | struct[] | 20+ | 3000-6000 | 🔴高 | 低 |
| 白名单查证 | bytes32[] | 10+ | 1500-3000 | 🟡中 | 低 |
| 权限检查 | address[] | <5 | <500 | 🟢低 | 低 |
| 初始化函数 | 任意 | 1-3 | 100-300 | 🟢低 | 低 |

### 7. 常见的"智能分析工具"的误判

**工具可能报错的真实案例**：
```solidity
// 自动化工具会标记为漏洞，但需要人工确认
function delegateCall(bytes[] memory data) external {
    // 工具不知道：delegatecall的入参处理有特殊规则
    for(uint i = 0; i < data.length; i++) {
        (bool success, ) = address(this).delegatecall(data[i]);
        require(success);
    }
}
```

**人工审查步骤**：
1. 运行自动化扫描器 → 获得候选列表
2. 逐一检查 → 验证参数是否真的只读
3. 检查代理/升级 → 确认无兼容性问题
4. 估算收益 → 仅对高频大数据函数优化
5. 记录决策 → 为什么保持/改进（可追溯性）

## 总结决策树

```
发现memory参数
├─ internal/private函数？ → 跳过（必须memory）
├─ <0.6.9版本 + struct类型？ → 代码异味（升级后优化）
├─ 调用链包含memory约束？ → 保持memory（记录原因）
├─ 参数被修改/赋值？ → 保持memory
├─ 数组长度<5 + 低频调用？ → 低优先级（可选）
└─ 数组长度>20 + 仅读取？ → 🔴明确漏洞（改calldata）
```
