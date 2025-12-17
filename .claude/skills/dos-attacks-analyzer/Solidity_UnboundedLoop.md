# Solidity 无界循环 DoS

**漏洞场景**：批量转账、奖励分发、治理投票、清算回调等需迭代用户可控数量元素的业务逻辑

**成因**：循环迭代次数无上限约束，导致 Gas 消耗超限使交易失败

## Details

**代码示例特征**：
```solidity
function distributeRewards(address[] memory users) public {
    for (uint i = 0; i < users.length; i++) {
        token.transfer(users[i], amount);
    }
}
```

**定位核心操作** (L2:跳读)：
- 扫描 `for`/`while` 循环语句，重点关注循环边界来源
- 追踪循环变量：`array.length`、`mapping` 动态计数器、函数参数传入的数值
- 识别循环体内高 Gas 操作：`SSTORE`、外部调用 `call`/`transfer`、复杂计算

**定位保护机制** (L1:关键词扫描)：
- 长度限制：`require(users.length <= MAX_BATCH)`
- 分页机制：`(uint start, uint end)` 参数、`offset`/`limit` 模式
- Gas 补偿：`gasleft()` 检查、`try-catch` 包裹循环体
- 提前终止：`break` 条件、累计 Gas 估算

## Classify

**漏洞研判标准**：
1. **确认漏洞**：循环边界完全用户可控 + 无上限检查 + 循环体含高 Gas 操作（外部调用/存储写入）
2. **代码异味**：有软性限制但未强制执行（如文档建议批量大小但代码未校验）、循环体仅读操作但数组可无限增长
3. **误报排除**：循环上限为固定常量、边界受合约内部状态严格控制（如枚举预设角色列表）、循环体 Gas 消耗极低且总量可预测

## Low risk

**降级条件**（满足任一即可降为 Low）：
- 循环仅执行纯计算/读操作，单次迭代 Gas < 3000 且理论最大迭代次数 < 100
- 仅 owner/特权角色可触发，且角色管理机制健全
- 配备链下预估 + 链上实时 `gasleft()` 熔断机制
- 业务场景明确限定输入规模（如已 KYC 白名单用户，最大数量可知且合理）

## 审计专业技巧

### 高级检测方法

**1. Gas 成本精确计量**
- 计算单次迭代最坏情况 Gas 成本：基础循环开销 (~60 Gas) + 循环体业务操作
  - `SSTORE` (20000 Gas冷存储, 2900 Gas热存储) 最危险
  - 外部调用 `call` (21000 Gas) 与 `transfer` 同级
  - 事件发射 `emit` (~1875 Gas)
  - 状态检查 `require` (~22 Gas 每次)
- 乘以循环上限估算总成本，对比当前网络 Gas limit（如 Ethereum 30M）
- 示例：若单次迭代 15000 Gas，数组长度 500，总计 7.5M Gas，仍可执行；若 3000 个元素则风险等级上升

**2. 数组增长路径追踪**
- 不仅检查参数输入，还要追踪数组如何被动态增长
- 关键点：`push()`/`append()` 操作何时触发、触发频率是否可控
  - 真实漏洞：`addUser()` 无限期推送新地址到数组，后续批量处理函数遍历整个数组
  - 误报案例：虽有 `push()`，但数组长度由合约初始化时设定，后续不变
- 检查是否存在数组清空/截断操作（`delete array` 或重置指针），若无则风险升高

**3. 测试场景模拟**
- 构造边界测试用例：
  - 空数组 (0 元素) - 验证是否会导致意外行为
  - 最大允许大小临界值 (如设置 Max=100 时，传入 99/100/101)
  - 超大数组 (1000/10000 元素) - 观察 Gas 消耗曲线
- 在本地测试网 (Hardhat/Foundry) 实际计量各场景 Gas 消耗，记录数据

### 真实漏洞与误报区分

**真实漏洞的三要素**（缺一不可）：
1. **循环边界完全外部可控**
   - ✓ 函数参数直接传入：`function batch(address[] calldata users)`
   - ✓ 数组通过 `call` 动态构造，调用者决定规模
   - ✗ 数组受 `require(array.length <= 50)` 约束 → 误报
   - ✗ 边界为 `mapping.length`，而 mapping 由预设数据初始化，大小固定 → 误报

2. **循环体包含高 Gas 操作且无提前终止**
   - ✓ 逐一调用 ERC-20 `transfer()` (每次 ~5000 Gas)
   - ✓ 每次迭代修改状态：`userBalance[users[i]] += amount`
   - ✗ 仅读取 `SLOAD` 并累加到本地变量 (~100 Gas 总计) → 误报
   - ✓ 有 `try-catch` 但 `catch` 块为空，仍会失败 → 不是真正的防护

3. **无可靠防护或防护易绕过**
   - ✓ 缺少长度检查，文档说"建议不超过100"但代码未强制
   - ✓ `gasleft() > 50000` 熔断，但 50000 Gas 不足完成单次高成本操作
   - ✗ `require(users.length <= MAX_BATCH, "too many users")` 明确检查 → 已修复，非漏洞
   - ✗ 批次处理：`(uint start, uint end)` 参数且 `require(end - start <= 100)` → 已缓解

**案例对比**：

| 代码片段 | 判定 | 理由 |
|---------|------|------|
| `for(uint i=0; i<users.length; i++) token.transfer(users[i], 1 wei)` | **High** | 无限制，存在转账操作 (5000 Gas/次) |
| 同上 + `require(users.length <= 100)` 在函数开头 | **不是漏洞** | 边界受明确限制，用户最多100个转账 |
| `for(uint i=0; i<validatorCount; i++) balances[validators[i]]++` | **Low/Medium** | 边界固定 (validatorCount 由初始化设定)，仅 SSTORE 操作 |
| `for(uint i=0; i<array.length; i++)` + `if(gasleft() < 100000) break` | **Low** | 虽无显式限制但有运行时熔断，实际可执行 |
| `function claimRewards(uint[] calldata indexes, uint[] calldata amounts)` + 循环遍历 indexes | **Medium** | 边界外控但调用合约内部状态(如 holder 列表)受控，需评估实际上限 |

### 报告撰写建议

- **明确指出具体风险点**：不能笼统说"有循环就是风险"，要定量：例如 "传入 500 个地址时，每个 transfer 5000 Gas，总计 2.5M Gas，当前区块 Gas limit 30M，执行成功但消耗可观"
- **提供修复方案优先级**：
  1. 加硬性限制 (首选) - 成本最低
  2. 分页处理 (可接受) - 业务改动小
  3. 权限降级 (次选) - 功能受限
  4. 单向链表/缓冲池 (复杂) - 仅在必要时
- **区分业务意图**：是否故意限制用户数量（如参与者众筹不超过 500 人），若是，则根本不是 DoS 风险

### 进阶审计技巧

**1. 动态长度分析**
- 使用静态分析工具 (Slither, Mythril) 自动追踪数组增长
- 手工审计时，重点关注以下模式：
  - `mapping(address => bool) registered` + `address[] public users` 组合：当 mapping 无上限时，users 数组也无限增长
  - `push()` 在 `if` 条件分支中：需判断分支是否总会执行（如 require 无条件限制）
  - 跨函数状态累积：A 函数 push，B 函数遍历整个数组

**2. Gas 成本按操作分级**
```
超高成本 (>10000 Gas/次): delegatecall, 创建新合约, 跨链通信
高成本 (5000-10000 Gas/次): transfer, 冷存储 SSTORE, 动态数组增长
中等成本 (1000-5000 Gas/次): 普通 SSTORE, event emit
低成本 (<1000 Gas/次): SLOAD, 本地变量操作, 算术运算
```
- 循环体若包含超高或高成本操作，即使受限于 100 次，也应标记为风险

**3. 防护机制有效性评估**
- `require(length <= X)` 类强制检查：✓ 有效，但要验证 X 值是否合理 (应 ≤ Gas_limit / avg_cost_per_iteration)
- `gasleft() > threshold` 熔断：⚠ 风险，threshold 可能设置过低，实际 tx 失败率高
- 权限限制 (onlyOwner)：◐ 部分有效，但若 Owner 是多签且签名方不同步，仍可被利用
- 链下 DAO 治理审批：✗ 无效，链上合约仍可被任意调用

**4. 污点分析 (Taint Analysis)**
- 追踪用户输入从入口到循环边界的传播路径
  - 直接污点：`function f(uint[] calldata data)` 直接用 data.length
  - 间接污点：`data.length` 赋值给 `len` 局部变量，然后循环用 `len`
  - 隐式污点：`array = userProvidedData`，之后 `loop < array.length`
- 若存在任何清理操作（如 `len = Math.min(len, MAX)`），则污点被净化，风险降低

### 常见误报陷阱与规避

**陷阱 1: 过度敏感的自动化工具**
- Slither 默认会标记所有 for 循环，需手工复核
- 关注 Slither 输出中的 `impact` 字段，区分 Medium/High/Critical
- 若输出是 "loop variable may be dynamic"，需进一步验证控制流

**陷阱 2: 错误评估 Gas limit**
- 不同链的 Gas limit 差异大：Ethereum (30M) vs Arbitrum (32M) vs Polygon (200M+)
- 若合约跨链部署，需为最严苛环境（Ethereum）进行评估
- 别忘记当前网络的实际 Gas 价格与转账成本（部分链 transfer 成本更低）

**陷阱 3: 忽视预条件检查**
- `require(users.length > 0)` 虽然检查了非空，但不能限制上限
- `require(data.length == expectedLength)` 只校验固定长度，无保护作用
- 只有 `require(x <= MAX)` 这样的上界检查才有效

**陷阱 4: 混淆权限与安全性**
- "仅 owner 可调" ≠ 不是漏洞，应在报告中标记为 Medium 而非 High
- Owner 权力过大本身就是风险，需评估 owner 治理的去中心化程度
- 如 owner 是单个 EOA，漏洞等级应维持 High；如是完全去中心化 DAO，可降级

**陷阱 5: 忽视竞争条件**
- 单个交易内循环是原子的，无竞争问题
- 但若涉及跨函数的数组操作（A 增长数组，B 遍历），可能存在时间窗口
- 评估是否存在排序依赖或调用顺序约束

### 实战检查清单

- [ ] 定位所有 `for`/`while` 循环及其边界变量
- [ ] 追踪循环变量的数据来源（参数/状态/计算结果）
- [ ] 计算单次迭代的 Gas 消耗并标记关键操作
- [ ] 搜索边界相关的 require/assert 检查语句
- [ ] 验证权限控制的真实强制执行（代码级，非文档级）
- [ ] 在 Hardhat/Foundry 中编写 PoC 测试边界情况
- [ ] 评估是否存在数组增长的潜在路径（不仅当前函数）
- [ ] 查看是否有分页、批次、或累积 Gas 熔断的实现
- [ ] 对比类似成熟项目（如 Uniswap、Aave）的处理方式
- [ ] 得出最终判定并说明理由
