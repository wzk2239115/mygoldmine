# Solidity - 资产映射逻辑缺陷（Asset Mapping Logic Flaw）

## Details

**典型代码场景：**
```solidity
// 跨链桥合约中的资产映射
mapping(address => address) public tokenMapping;  // sourceToken => targetToken
mapping(bytes32 => bool) public processedMessages;

function bridgeToken(address token, uint256 amount, bytes calldata proof) external {
    address targetToken = tokenMapping[token];
    _verifyProof(proof);
    IERC20(targetToken).mint(msg.sender, amount);
}
```

**快速定位核心操作（L3 - 逐行读）：**
- 搜索关键函数：`mint`、`burn`、`lock`、`unlock`、`bridgeToken`、`receiveToken`
- 追踪映射结构：`mapping(address => address)`、`mapping(uint256 => uint256)`（链ID或代币映射）
- 检查铸造/解锁时的 token 地址来源：是否直接从用户输入、是否通过映射表转换
- 关注双向映射一致性：`tokenMapping[A] = B` 时是否同步设置 `reverseMapping[B] = A`
- 验证链ID绑定：映射关系是否区分源链ID，避免跨链混淆

**快速定位保护机制（L2 - 跳读）：**
- 映射表管理权限：搜索 `onlyOwner`、`onlyGovernance`、`registerToken`、`setMapping`
- 映射初始化检查：目标 token 是否为零地址 `targetToken != address(0)`
- 映射对称性验证：是否有反向查询并校验一致性的逻辑
- 链ID隔离机制：是否使用 `mapping(uint256 => mapping(address => address))`（chainId => tokenMapping）
- 白名单限制：是否仅允许预先注册的 token 参与跨链

## Classify

**漏洞判定标准：**
- **严重漏洞**：映射关系可被未授权修改、映射未初始化导致零地址铸造、一对多映射导致资产增发、映射不区分链ID造成跨链混淆
- **误报场景**：映射仅用于元数据查询非资产操作、映射在合约部署时已固定且无修改接口、映射不一致但有其他验证机制托底（如默克尔证明中已包含目标 token）
- **代码异味**：映射更新无事件记录、缺少映射查询失败的兜底处理、单向映射设计但业务需要双向查询

**关键研判点：**
1. 映射关系的写入权限是否足够限制
2. 映射的读取是否在资产转移的关键路径上
3. 映射失效（零地址/未设置）时是否有明确的失败处理
4. 多链场景下是否有链ID维度的隔离

## Low risk

**满足以下条件可评为低风险：**
1. **映射不可变性**：token 映射在合约初始化后通过 immutable 或常量定义，运行时无法修改
2. **映射仅影响元数据**：映射错误仅导致事件记录不准确或前端展示问题，不影响实际资产转移的 token 地址
3. **有独立验证机制**：即使映射错误，签名/证明中已包含目标 token 地址，合约会交叉验证两者一致性
4. **白名单 + 映射双重防护**：先检查 token 在白名单内，再通过映射获取目标 token，且白名单与映射由不同角色管理形成制衡
5. **映射不一致仅影响反向操作**：正向跨链逻辑不依赖映射，仅反向撤回时使用，且撤回需要额外的多签或时间锁保护

## 审计专业技巧：真实漏洞 VS 误报区分指南

### 1. 映射未初始化 - 真实漏洞的典型表现

**真实漏洞特征（高危）：**
```solidity
// 真实漏洞示例：零地址铸造
function bridgeToken(address sourceToken, uint256 amount) external {
    address targetToken = tokenMapping[sourceToken];  // 如果未设置，返回 address(0)
    IERC20(targetToken).mint(msg.sender, amount);    // 关键：直接使用未验证的地址
}
```
**判断依据**：
- ✗ 无零地址检查 `require(targetToken != address(0))`
- ✗ 无映射初始化事件记录或注册日志
- ✗ 源链 token 支持用户任意输入，用户可触发未注册 token 的铸造
- ✗ ERC20(address(0)).mint() 不会报错（如果目标是自定义实现），可导致资产损失

**误报表现（实际低风险）：**
```solidity
// 误报示例：映射仅作查询，实际操作有托底
function bridgeToken(address sourceToken, bytes memory proof) external {
    bytes32 targetTokenHash = keccak256(abi.encode(sourceToken));  // 映射作为冗余查询
    address targetToken = tokenMapping[sourceToken];

    // 核心验证来自证明，不是映射！
    (address proofToken, uint256 amount) = _decodeProof(proof);
    require(proofToken == targetToken, "mismatch");
    IERC20(proofToken).mint(msg.sender, amount);  // 使用证明中的 token，非映射
}
```
**判断依据**：
- ✓ 映射值与签名/证明交叉验证
- ✓ 即使映射为零，证明验证会失败，无法进行资产操作
- ✓ 实际铸造的 token 地址由证明决定，映射仅作冗余校验

---

### 2. 跨链 ID 混淆 - 真实漏洞 vs 合理设计

**真实漏洞特征（严重）：**
```solidity
// 真实漏洞：缺失链ID维度隔离
mapping(address => address) public tokenMapping;  // 全局映射，混淆多链

function bridge(address sourceToken, uint256 amount) external {
    address targetToken = tokenMapping[sourceToken];
    // 问题：同一 sourceToken 在不同链上可能需要不同的 targetToken
    // 攻击：Ethereum 上的 USDC -> Polygon USDC
    //      但映射被覆盖为 USDC -> 攻击者的假 token
    IERC20(targetToken).mint(msg.sender, amount);
}
```
**漏洞根本**：缺乏 `chainId` 维度的隔离，跨链资产映射被单一键值淹没。

**合理设计（正常）：**
```solidity
// 合理设计：链ID隔离 + 双向映射
mapping(uint256 => mapping(address => address)) public mappings;  // chainId => sourceToken => targetToken
mapping(uint256 => mapping(address => address)) public reverseMapping;

function registerToken(uint256 sourceChain, address sourceToken, uint256 targetChain, address targetToken) external onlyGovernance {
    mappings[sourceChain][sourceToken] = targetToken;
    reverseMapping[targetChain][targetToken] = sourceToken;
    emit TokenRegistered(sourceChain, sourceToken, targetChain, targetToken);
}

function bridge(uint256 sourceChain, address sourceToken, uint256 amount) external {
    require(sourceChain != block.chainid, "same chain");
    address targetToken = mappings[sourceChain][sourceToken];
    require(targetToken != address(0), "unmapped");
    IERC20(targetToken).mint(msg.sender, amount);
}
```
**为何不是漏洞**：
- ✓ 链ID作为主键的一部分，避免跨链混淆
- ✓ 双向映射支持验证一致性
- ✓ 治理权限管理，映射变更需多签

---

### 3. 权限管理不当 - 审计的关键转折点

**真实漏洞（严重）：**
```solidity
// 真实漏洞：映射可被任意修改
mapping(address => address) public tokenMapping;

function setMapping(address source, address target) external {
    tokenMapping[source] = target;  // 无权限检查！任何人都可调用
}
```
**危害**：攻击者可以将合法 token 的映射指向自己铸造的合约，窃取用户资产。

**正确实现（低风险）：**
```solidity
// 正确：权限管理 + 事件记录 + 时间锁
mapping(address => address) public tokenMapping;
mapping(address => uint256) public mappingUpdateTime;
uint256 constant UPDATE_DELAY = 2 days;

function proposeMappingUpdate(address source, address target) external onlyGovernance {
    require(target != address(0), "zero address");
    _verifyTargetIsValidToken(target);  // 额外验证：目标是否为真实合约
    mappingUpdateTime[source] = block.timestamp + UPDATE_DELAY;
    emit MappingProposed(source, target);
}

function executeMappingUpdate(address source, address target) external onlyGovernance {
    require(block.timestamp >= mappingUpdateTime[source], "time lock");
    tokenMapping[source] = target;
    emit MappingUpdated(source, target);
}
```
**判断依据**：
- ✓ 仅 governance 可修改
- ✓ 时间锁防止闪电贷攻击
- ✓ 事件完整记录，链下可审计

---

### 4. 映射一致性验证 - 误报的常见陷阱

**常见误报情形：**
```solidity
// 表面看似不一致，实际安全
mapping(uint256 => address) public token;
address[] public tokenList;

function registerToken(address _token) external onlyOwner {
    token[tokenList.length] = _token;
    tokenList.push(_token);
}
```
**为什么不是漏洞**：
- ✓ 两个数据结构通过 index 关联，自动保证一致性
- ✓ 仅用于查询和迭代，不影响资产操作
- ✓ 即使数据结构不同步，也不会导致资产损失

**真实漏洞形式：**
```solidity
// 真实漏洞：双向映射不同步
mapping(address => address) forward;  // A => B
mapping(address => address) reverse;  // 应该 B => A

function bridgeAndBurnReverse(address tokenA, address tokenB, uint256 amount) external {
    require(forward[tokenA] == tokenB, "forward mismatch");
    require(reverse[tokenB] == tokenA, "reverse mismatch");  // 问题：reverse 可能未初始化或不同步

    IERC20(tokenA).burnFrom(msg.sender, amount);
    IERC20(tokenB).mint(msg.sender, amount);
}
```
**危害**：reverse 映射与 forward 不同步，导致跨链撤回失败或指向错误的 token。

---

### 5. 审计检查清单与决策树

**快速判定流程：**
```
1. 映射是否直接用于资产转移？
   YES → 进行第2步（高优先级）
   NO  → 检查是否有其他验证机制托底 → 可能为低风险

2. 映射的写入权限是否受限？
   NO  → 高危漏洞，立即报告
   YES → 进行第3步

3. 映射读取前是否验证非零？
   NO  → 中危漏洞（零地址风险）
   YES → 进行第4步

4. 多链场景下是否区分 chainId？
   NO  → 中危（跨链混淆风险）
   YES → 进行第5步

5. 是否存在映射不一致但有交叉验证？
   NO  → 中危（不一致风险）
   YES → 低风险或非漏洞
```

---

### 6. 真实案例对比

**案例 A：真实漏洞（Poly Network 2021）**
- 映射可被任意修改，攻击者覆盖 token 映射
- 结果：6.1 亿美元跨链资产被盗

**案例 B：误报示例**
- 审计报告发现 "tokenMapping 未初始化"
- 实际情况：所有跨链操作都有默认处理或注册检查
- 结论：合理的设计选择，非漏洞
