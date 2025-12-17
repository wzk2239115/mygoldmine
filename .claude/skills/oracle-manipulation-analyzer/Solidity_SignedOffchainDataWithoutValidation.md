# Solidity_SignedOffchainDataWithoutValidation

**漏洞类型：** Oracle Manipulation - 未验证的链下签名数据

**场景：** 价格预言机、借贷利率计算、清算阈值判定、跨链消息验证等接受链下签名数据的业务逻辑

## Details

**典型代码模式：**
```solidity
function updatePrice(uint256 price, bytes memory signature) external {
    // 漏洞：直接使用价格数据，未验证签名者身份
    oraclePrice = price;
    emit PriceUpdated(price);
}

function updatePriceWithSig(uint256 price, uint256 timestamp, bytes memory signature) external {
    bytes32 hash = keccak256(abi.encodePacked(price, timestamp));
    address signer = ECDSA.recover(hash, signature);
    // 漏洞：验证了签名但未校验签名者是否为授权预言机
    // 漏洞：未检查 timestamp 时效性，可能重放旧数据
    oraclePrice = price;
}
```

**快速定位核心操作（L2：跳读）：**
- 搜索关键函数：`updatePrice`、`setPrice`、`feedData`、`submitData`、`postData`
- 关注参数类型：`bytes memory signature`、`uint8 v, bytes32 r, bytes32 s`
- 定位数据存储：直接修改状态变量 `price`、`rate`、`data` 的赋值语句
- 检查 `ecrecover`、`ECDSA.recover` 调用点及其返回值使用

**快速定位保护机制（L3：逐行读）：**
- 签名者白名单：`mapping(address => bool) public authorizedSigners`、`require(isTrustedOracle[signer])`
- 时效性检查：`require(block.timestamp - timestamp < validityWindow)`、`require(timestamp > lastUpdate)`
- 重放保护：`mapping(bytes32 => bool) public usedHashes`、`nonce` 递增机制
- 多签验证：`require(signatures.length >= threshold)`、聚合签名验证
- 价格偏差保护：`require(abs(newPrice - oldPrice) < maxDeviation)`

**审计等级标注：**
- L2：初筛阶段，跳读所有 `external/public` 函数寻找签名参数
- L3：核心操作逐行读，确认每个 `ecrecover` 后是否有身份校验和时间校验
- L4：跨模块追踪，检查授权管理逻辑、时间戳来源、价格使用方是否有二次校验

## Classify

**归类为高危漏洞的条件：**
- 完全缺失签名验证逻辑，任意地址可提交数据
- 验证签名但未检查签名者身份，任意用户自签数据可通过
- 缺失时效性检查，历史签名数据可无限期重放攻击
- 在金融敏感场景（借贷清算、DEX定价、合成资产铸造）中使用未验证数据

**归类为误报的条件：**
- 数据提交函数限制 `onlyOwner`/`onlyRole` 且权限管理健全，签名仅作额外日志用途
- 该数据源仅用于非关键展示功能（如UI统计），不影响资金安全
- 存在完整的白名单 + 时效性 + nonce/重放保护三重机制
- 数据使用方有独立验证层（如链上 Chainlink 作为最终仲裁）

**归类为代码异味的条件：**
- 签名验证逻辑存在但过于宽松（如 validityWindow = 1 year）
- 使用低熵字段构造哈希（如仅 `keccak256(price)` 缺失 timestamp）
- 多签阈值配置不合理（如 3/10 中仅需 1 个签名）
- 缺乏紧急暂停机制应对预言机被攻破场景

## Low risk

**低风险评级适用场景：**
- 该预言机数据仅用于非金融功能（游戏积分、声誉评分、活动排名等），即使被操纵损失可控
- 存在多层防御：数据使用方实施严格的价格偏差检查、熔断机制、时间加权平均
- 链下签名者为中心化可信实体（如项目方控制的后端服务），且用户明确知晓信任假设
- 合约处于测试阶段或沙盒环境，明确标注为非生产版本
- 存在补偿机制：如价格异常时有保险池覆盖、可通过治理回滚状态

**注意：** 即使评为低风险，仍需在审计报告中明确指出缺陷，并建议添加完整验证逻辑作为最佳实践。

## 审计专业技巧与真实漏洞区分

### 技巧 1：签名者身份核验的深度追踪

**真实漏洞案例（高危）：**
```solidity
// 问题：虽然使用了 ECDSA.recover，但未校验签名者身份
function submitPrice(uint256 price, bytes calldata signature) external {
    bytes32 hash = keccak256(abi.encodePacked(price, block.chainid));
    address signer = ECDSA.recover(hash, signature);
    // 任何人都可以自签一个价格，只要格式正确
    lastPrice = price;
    lastSigner = signer;  // 记录了签名者但从未校验其身份
}
```
**审计方法：** 搜索 `ecrecover` 或 `ECDSA.recover` 的返回值使用，跟踪 `signer` 变量是否进入了 `require()` 语句与授权白名单比较。若只是记录而无身份校验，必是漏洞。

**误报陷阱：** 如果该 `signer` 后续在复杂的访问控制体系中被验证（如通过 `_checkAuthorization(signer)` 函数），需深入追踪该函数实现，确保真正进行了白名单核验。

---

### 技巧 2：时效性检查的细粒度识别

**真实漏洞案例（高危）：**
```solidity
// 问题：时间检查存在但范围过大，实际等同于无保护
function updateRateWithExpiry(
    uint256 rate,
    uint256 timestamp,
    bytes calldata sig
) external {
    require(block.timestamp - timestamp < 365 days, "Too old");  // 一年内都可用！
    // 攻击者可以重放数周前的旧汇率数据
    exchangeRate = rate;
}
```
**审计方法：** 检查 `validityWindow` 或时间差值检查的具体数字。单位为 `days` 的应该 ≤ 1，单位为 `hours` 的应该 ≤ 24。如果是 `weeks` 或 `years`，直接标记为高危。

**误报区分：** 某些场景（如资产借贷合约的利率更新）的时效窗口可以相对宽松（如 7 天），但前提是：
1. 有明确的业务说明文档
2. 数据提交方限制为可信角色（`onlyOwner`、`onlyRole`）
3. 存在独立的价格偏差熔断机制

---

### 技巧 3：重放攻击防护的模式识别

**真实漏洞案例（高危）：**
```solidity
// 问题：缺少 nonce 或使用过的签名记录
function feedMultiplePrices(
    uint256[] calldata prices,
    uint256[] calldata timestamps,
    bytes[] calldata signatures
) external {
    for (uint i = 0; i < prices.length; i++) {
        bytes32 hash = keccak256(abi.encodePacked(prices[i], timestamps[i]));
        address signer = ECDSA.recover(hash, signatures[i]);
        require(trustedOracles[signer], "Untrusted");
        // 漏洞：同一个 hash 可以无限次提交！
        prices[i] = prices[i];
    }
}
```
**审计方法：** 寻找以下重放防护机制：
- `nonce` 映射：`mapping(address => uint256) public nonces`
- 哈希记录：`mapping(bytes32 => bool) public usedSignatures`
- 时间戳递增：`require(timestamp > lastUpdateTime[oracle])`

如果完全缺失，直接标记高危。

**误报区分：** 某些设计中，如果签名包含链 ID、合约地址、以及可递增的批次号（batch ID），并且批次号严格单调，可视为具备隐式重放保护。但这需要逐行验证实现。

---

### 技巧 4：链下数据构造的完整性检验

**真实漏洞案例（高危）：**
```solidity
// 问题：签名的消息结构不完整，缺少上下文信息
function setPriceV1(uint256 price, bytes calldata sig) external {
    bytes32 hash = keccak256(abi.encodePacked(price));  // 仅价格！
    address signer = ECDSA.recover(hash, sig);
    require(authorizedSigner == signer, "Bad sig");
    currentPrice = price;
}
```
此时攻击者可以：
1. 从不同合约/链获取相同价格的有效签名
2. 重新使用到此合约（跨合约重放）

**审计方法：** 检查 `keccak256` 的输入是否包含：
- 合约地址（`address(this)`）
- 链 ID（`block.chainid`）
- 函数选择器或业务上下文标识
- 时间戳或递增 nonce

缺少其中任何一项，在跨链或多合约场景中都有重放风险。

**误报区分：** 单链应用、功能隔离明确的合约，即使缺少链 ID 也可能不是实际威胁，但仍应在报告中标注为"代码异味"并建议改进。

---

### 技巧 5：授权白名单的完整性验证

**真实漏洞案例（高危）：**
```solidity
// 问题：白名单声明但未正确初始化
address public authorizedSigner;

function setPriceAuthority(address newSigner) external onlyOwner {
    authorizedSigner = newSigner;  // 可修改，但修改逻辑有缺陷
}

function updatePrice(uint256 price, bytes calldata sig) external {
    bytes32 hash = keccak256(abi.encodePacked(price, block.chainid));
    require(ECDSA.recover(hash, sig) == authorizedSigner, "Bad signer");
    currentPrice = price;
}
// 问题：authorizedSigner 初始值为 0x0，在初始化前任何人都可以伪造签名
```

**审计方法：** 检查授权字段的初始化：
- 在 `constructor` 中是否明确设置
- 是否存在"默认值"的风险（address(0)、0、false）
- 权限修改函数是否有事件日志（便于链上审计）
- 是否存在"紧急冻结"机制（如 `pauseOracle()` 函数）

**误报区分：** 如果白名单由可信的 DAO 或多签管理，白名单初始化在 proxy 合约的 `initialize` 函数中明确执行，可视为低风险。

---

### 技巧 6：多数据源聚合的验证完整性

**真实漏洞案例（中危）：**
```solidity
// 问题：多签阈值设置不合理
function updatePriceMultiSig(
    uint256 price,
    uint256 timestamp,
    bytes[] calldata signatures
) external {
    require(signatures.length >= 3, "Need 3+ sigs");  // 看起来合理
    // 但如果只有 5 个授权签名者，3/5 的阈值还是太低
    // 特别是如果有 2 个签名者被攻破，攻击者需要再获取 1 个就能操纵价格

    bytes32 hash = keccak256(abi.encodePacked(price, timestamp));
    uint256 validSigs = 0;
    for (uint i = 0; i < signatures.length; i++) {
        address signer = ECDSA.recover(hash, signatures[i]);
        if (trustedOracles[signer]) validSigs++;
    }
    require(validSigs >= 3, "Insufficient valid sigs");
    currentPrice = price;
}
```

**审计方法：** 计算比率：`threshold / total_signers`。健康水平通常为 2/3 以上（如 3/4、4/6、5/7）。如果低于 1/2，直接标记为中危。同时检查：
- 签名者集合是否公开可查
- 单个签名者是否可能被攻破的概率
- 是否存在动态权限变更（新增/删除签名者）的正确处理

**误报区分：** 如果该多签体系并非用于价格输入本身，而是用于"授权参数修改"（如修改白名单、时效窗口等），阈值要求可以相对宽松。

---

### 技巧 7：时间戳来源的信任边界确认

**真实漏洞案例（高危）：**
```solidity
// 问题：时间戳由链下数据决定，矿工/排序器可操纵
function updatePriceWithTimestamp(
    uint256 price,
    uint256 clientTimestamp,  // 完全由调用者控制！
    bytes calldata sig
) external {
    require(block.timestamp - clientTimestamp < 1 hours, "Stale");
    // 矿工可以操纵 block.timestamp，进一步放宽时间限制
    bytes32 hash = keccak256(abi.encodePacked(price, clientTimestamp));
    require(ECDSA.recover(hash, sig) == trustedOracle, "Bad sig");
    currentPrice = price;
}
```

**审计方法：** 区分时间戳来源：
- `block.timestamp`：由矿工控制，可操纵（±15秒精度），在 MEV 场景中风险高
- 链下上报的 `timestamp`：必须严格校验，缺少校验时风险最高
- 时间加权平均（TWAP）：如使用历史区块的累计数据，相对安全

**误报区分：** 如果该时间戳仅用于"日志记录"或"统计分析"，而价格更新本身不依赖其具体值，风险降低。但在金融敏感场景中，即使用于次要逻辑也应明确标注。

---

### 审计工作流总结

| 检查项 | 真实漏洞特征 | 误报特征 | 优先级 |
|--------|-----------|--------|-------|
| 签名验证 | 无 `require()` 校验签名者 | 签名仅用于日志，函数有 `onlyRole` 限制 | P0 |
| 白名单 | 完全缺失或初始为 0x0 | 由 DAO 管理，有 pause 机制 | P0 |
| 时效性 | 缺失或 > 7 days | 业务合理性证明 + 有熔断保护 | P1 |
| 重放防护 | 无 nonce 或 hash 记录 | 批次号严格递增验证 | P1 |
| 多签阈值 | < 1/2 的签名者数量 | 2/3+ 且签名者有多重验证 | P2 |
| 消息结构 | 缺少合约地址/链 ID | 单链应用、功能隔离明确 | P2 |
