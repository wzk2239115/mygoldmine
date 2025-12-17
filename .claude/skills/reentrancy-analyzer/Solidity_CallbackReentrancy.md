# Solidity 回调重入漏洞

**漏洞场景**：使用回调机制（ERC777 hooks、ERC721/ERC1155 接收钩子、自定义回调）时未防护重入，允许接收方在回调中再次调用合约函数。

**常见位置**：token 转账、NFT 铸造/转移、支付分发、拍卖结算等涉及外部合约回调的场景。

---

## Details

**代码示例：**

```solidity
contract Vault {
    mapping(address => uint256) public balances;
    
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount);
        IERC777(token).send(msg.sender, amount, "");  // 触发 tokensReceived 回调
        balances[msg.sender] -= amount;  // 状态更新滞后
    }
}
```

**（L3）快速定位核心操作技巧：**
- 扫描 `ERC777.send/transfer`、`ERC721.safeTransferFrom`、`ERC1155.safeTransferFrom`、自定义 `callback/hook` 调用
- 关注回调点之后是否存在状态变更：余额修改、计数器递增、状态标记等
- 检查回调前是否完成所有状态快照（如：转账前记录 totalSupply）

**（L2）快速定位保护机制技巧：**
- **检查互斥锁**：`nonReentrant` modifier、自定义 `locked` 状态变量
- **CEI 模式**：Check-Effects-Interactions，状态变更是否在外部调用前完成
- **Pull over Push**：是否改为 `claimable` 模式而非主动推送
- **信任列表**：回调目标是否限定为可信合约（白名单）

---

## Classify

**漏洞判定条件（满足全部）：**
1. 存在外部调用触发不受控回调（ERC777/721/1155、delegatecall、自定义回调）
2. 回调点之后存在关键状态变更（余额、权限、计数器等）
3. 无有效重入防护（无锁、状态更新顺序错误）
4. 攻击者可通过重入获取不当利益（资金、权限、逻辑绕过）

**误报识别：**
- 回调对象为可信合约（代理合约、官方工厂合约）
- 回调后无状态变更或变更不影响重入逻辑（如：仅发送事件）
- 存在全局锁或函数级锁保护
- 重入后无法通过 `require` 检查（如：已标记为已处理）

**代码异味：**
- 虽有保护但逻辑复杂，多层调用链难以追踪重入路径
- 依赖外部合约行为假设（如：假定 ERC20 不触发回调）
- CEI 模式部分遵守但存在隐蔽的状态读取（如：通过 view 函数读取旧状态）

---

## Low risk

**可降级为低风险的场景：**

1. **经济不可行**：重入攻击成本高于收益（gas 费超过可窃取金额、需抵押大量资产）
2. **权限受限**：仅白名单地址可触发回调路径，且白名单管理安全
3. **金额可控**：单次回调涉及金额存在硬编码上限（如：`min(amount, MAX_PER_TX)`）
4. **只读重入**：回调仅触发 view 函数，不修改状态（需验证 view 函数无隐蔽状态修改）
5. **时间锁保护**：回调操作需等待时间窗口，无法连续重入
6. **降级影响**：重入仅导致事件重复发送或非关键状态混乱，不涉及资金/权限

---

## 审计专业技巧与真实经验

### 1. 真实漏洞 vs 误报区分手册

**真实漏洞特征（高保真）：**
- ✅ 回调点在 `balances[msg.sender] -= amount` 之前，攻击者可无限递归调用
- ✅ 无任何重入保护机制（无 nonReentrant、无状态标记）
- ✅ 触发回调的 token 合约可被攻击者控制（恶意 ERC777）或是标准 token（如 Uniswap V3 USDC 的 hooks）
- ✅ 重入路径明确：`withdraw` → `send` → `tokensReceived` → `withdraw`（形成完整环路）

**常见误报陷阱（需要识别但实际安全）：**
- ❌ ERC721/1155 的 `safeTransferFrom` + `onERC721Received` hook，但回调后没有更新状态（仅转移所有权）
- ❌ 使用了 `Checks-Effects-Interactions` 的标准实现，虽然看起来存在回调，但状态已更新
- ❌ 回调发送给受信任的合约（如 WETH，USDC 等官方标准实现）且不存在实际重入路径
- ❌ 两层 CEI 嵌套但第二层被注释掉了，导致警告，但实际代码不可达

### 2. 真实案例分析

**案例 1：Uniswap V3 Flash Loans（安全）**
```solidity
function flash(address recipient, uint256 amount0, uint256 amount1, bytes calldata data) {
    // 1. Check：验证池子余额充足
    require(balance0Before >= amount0);

    // 2. Effect：转账前记录余额快照
    uint256 balance0Before = balanceOf(token0);

    // 3. Interaction：转账触发 flashLoan 回调
    IERC20(token0).transfer(recipient, amount0);
    IFlashBorrower(recipient).uniswapV3FlashCallback(...);

    // 4. Check：验证还款完成（防护）
    require(balanceOf(token0) >= balance0Before + fee);
}
```
**为什么安全**：虽有回调，但在回调前已完成关键检查，回调后再验证余额满足条件，形成"快照检查"模式。

**案例 2：UniswapX Router（真实漏洞，已修复）**
```solidity
// 易受攻击的旧版本
function execute(bytes calldata commands, bytes[] calldata inputs) external {
    for (uint i = 0; i < commands.length; i++) {
        if (commands[i] == EXECUTE_SUB_PLAN) {
            // 可能触发的回调
            (success, ) = address(target).call(encoded);
            // 状态更新在后，重入可绕过权限检查
            permitted[msg.sender][...] = true;
        }
    }
}
```
**为什么有漏洞**：回调点在状态修改前，攻击者在回调中再次调用 `execute`，绕过权限检查。

### 3. 审计技巧：四层递进检查法

**第 1 层：快速扫描（5 分钟）**
- 使用关键字搜索：`safeTransferFrom`, `ERC777`, `send`, `call{value`, `delegatecall`
- 标记所有外部调用点

**第 2 层：上下文分析（10 分钟）**
- 对每个外部调用，向上扫 5-10 行确认：是否已完成 Check？
- 向下扫 5-10 行确认：是否存在关键的 Effects？
- 比对顺序：Effect 是否在 Interaction 前？

**第 3 层：重入路径追踪（20 分钟）**
- 列出回调可能触发的所有函数（通过接口定义或文档）
- 从每个回调函数反向追踪：是否能重新进入当前函数？
- 判断重入时状态是否会导致"双花"或权限绕过

**第 4 层：防护验证（15 分钟）**
- 如果存在 `nonReentrant`：验证是否覆盖了所有回调路径
- 如果使用状态标记（如 `locked` flag）：检查设置和清除的位置是否原子性
- 如果依赖 CEI：验证是否存在隐蔽的状态读取

### 4. 常见误判的真实案例

**案例：USDCv2 的"虚假重入"警告**
审计工具可能标记 USDC 的 `transfer` 为有重入风险，因为在传输前调用了 `_approve` 的 hook。但实际上：
- USDC 官方合约中 hook 不存在（`whenNotPaused` 只是 modifier）
- 即使存在，USDC 使用黑名单机制（受信任方式）

**区分方法**：
1. 查阅 token 源码
2. 验证合约部署地址是否匹配官方公告
3. 检查审计报告或 GitHub issue 是否曾报告过重入

### 5. 工具辅助但需人工验证

| 工具输出 | 人工验证 | 最终判定 |
|---------|---------|---------|
| ⚠️ 检出外部调用后有状态修改 | 确认是否为同一函数、重入是否有经济意义 | 真实/误报 |
| ⚠️ 检出 ERC777 transfer | 确认是否为标准 ERC777、有无 nonReentrant | 真实/误报 |
| ✅ 检出 nonReentrant modifier | 验证是否覆盖所有回调路径 | 风险等级 |
| ✅ 检出状态标记模式 | 检查原子性和边界条件 | 风险等级 |
