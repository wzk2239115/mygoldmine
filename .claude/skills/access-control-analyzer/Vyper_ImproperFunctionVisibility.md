# Vyper 函数可见性设置不当

常出现在金库操作、参数配置、紧急暂停等业务逻辑实现中，敏感内部函数未标记为 `@internal`，导致外部可直接调用，绕过访问控制逻辑。

## Details

**代码示例：**
```vyper
# 漏洞：敏感函数缺少 @internal 标记
def _mint(to: address, amount: uint256):
    self.balances[to] += amount
    self.totalSupply += amount

# 漏洞：配置函数缺少可见性控制
def updateFeeRate(newRate: uint256):
    self.feeRate = newRate

# 漏洞：提款函数无权限校验
def emergencyWithdraw(amount: uint256):
    send(msg.sender, amount)
```

**快速定位核心操作（L2-跳读）：**
- 扫描状态变更函数：`balances[]`、`totalSupply`、`owner`、`paused` 等关键变量的写操作
- 定位资金流转点：`send()`、`raw_call()`、`selfdestruct()`、余额增减操作
- 识别配置类函数：含 `update`、`set`、`configure`、`change` 前缀的函数
- 关注特权操作：`_mint`、`_burn`、`_pause`、`_unpause`、`_withdraw` 等下划线前缀函数

**快速定位保护机制（L1-关键词扫描）：**
- 检查可见性修饰符：函数定义是否含 `@internal` 或 `@external` 标记
- 验证权限断言：`assert msg.sender == self.owner`、`assert self.authorized[msg.sender]`
- 确认角色检查：`assert self.hasRole[msg.sender][ADMIN_ROLE]`
- 审查调用路径：是否仅通过受保护的 `@external` 函数间接调用

## Classify

**漏洞研判标准：**
- **确认漏洞**：敏感函数（资金操作/状态变更/权限配置）缺少 `@internal` 且无 `msg.sender` 校验，可被任意外部调用
- **误报情况**：函数虽无装饰器但已在业务逻辑中校验 `msg.sender`，或函数设计为公开调用（如 `transfer`、`approve`）
- **代码异味**：辅助只读函数（view/pure 逻辑）缺少 `@internal`，虽无安全风险但不符合最小权限原则

**核心判别点：**
1. 函数是否修改关键状态变量（owner、余额、授权映射）
2. 是否存在资金流出路径（send、raw_call）
3. 函数调用者是否需要受信任身份
4. 是否存在其他防御层（如时间锁、多签）

## Low risk

**降级为低风险的情形：**
- 函数虽可外部调用，但操作对象为调用者自身资产（如用户提取自己的质押）
- 状态变更需依赖链上预言机数据或多步交互，单次调用无法完成攻击
- 函数受全局状态限制（如 `paused` 标志）且紧急开关由可信方控制
- 操作影响范围有严格上限（如单笔金额 < 1 wei 的精度调整）
- 仅影响非关键业务指标（如统计计数、日志索引）

**需综合评估：**
- 函数调用频次限制（冷却期、区块间隔）
- 经济成本门槛（需质押代币、支付高额 gas）
- 影响范围隔离（仅影响调用者的子账户）
- 业务场景合理性（DeFi 中的公开清算函数）

## 审计专业技巧

### 真实漏洞特征识别

**案例1：闪电贷风险漏洞**
```vyper
# 实际漏洞：configPool() 无权限检查，攻击者可在闪电贷回调中调用
def configPool(poolId: uint256, newParam: uint256):
    self.pools[poolId].param = newParam  # 直接修改，无权限验证

def flashLoan(amount: uint256) -> bool:
    # 转账后，立即将控制权交给调用者
    send(msg.sender, amount)
    # 此时攻击者可调用 configPool 修改参数
    return True
```
**识别要点**：结合链上交互模式，函数不仅需要权限检查，还需考虑可重入性和状态临界性。

**案例2：代币铸造绕过**
```vyper
# 常见误报：_mint 虽无装饰器但通过 public mint() 调用
def _mint(to: address, amount: uint256):
    self.balances[to] += amount
    self.totalSupply += amount

def mint(to: address, amount: uint256):
    assert msg.sender == self.owner  # 权限在这里
    self._mint(to, amount)

# 真实漏洞：upgradeable 合约中，init() 函数无权限
def __init__():
    self.owner = msg.sender

def reinitialize(newOwner: address):  # 无修饰符，可被任意调用
    self.owner = newOwner
```
**识别要点**：初始化函数即使是内部调用，若无权限检查也成为漏洞。Proxy 模式下特别危险。

### 常见误报场景与规避

**误报1：接口实现函数**
```vyper
# 误报：接口规定必须是 external，不能改为 internal
interface IERC20:
    def transfer(to: address, amount: uint256) -> bool: nonpayable

def transfer(to: address, amount: uint256) -> bool:
    # 这里不能加 @internal，否则违反接口约定
    assert self.balances[msg.sender] >= amount
    self.balances[msg.sender] -= amount
    self.balances[to] += amount
    return True
```
**规避方法**：检查函数是否实现了已发布的接口（ERC20、ERC721 等），这类函数的可见性由接口定义。

**误报2：回调函数**
```vyper
# 误报：回调函数必须是 external，供外部合约调用
def onERC721Received(
    operator: address,
    sender: address,
    tokenId: uint256,
    data: Bytes32
) -> bytes32:
    # NFT 标准要求此函数为 external
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes32)
```
**规避方法**：识别标准回调函数名（onERC*Received、fallback 等），不应改为 internal。

**误报3：链上公共数据查询**
```vyper
# 误报：这是设计的公开接口，不是漏洞
def getReserves() -> (uint256, uint256):
    return self.reserve0, self.reserve1

def balanceOf(account: address) -> uint256:
    return self.balances[account]
```
**规避方法**：函数若只读取数据、不修改状态、符合 DeFi 约定俗成的接口，则非漏洞。

### 审计检查单

**第一阶段：快速筛查**
1. 扫描所有无 `@internal` 的函数定义
2. 识别所有修改关键变量的函数（balances、owner、allowance 等）
3. 列举所有转账操作的函数（send、raw_call、transferFrom）

**第二阶段：权限验证**
- [ ] 检查 `msg.sender` 校验是否存在，位置是否在状态变更前
- [ ] 验证权限逻辑是否可被绕过（条件判断、整数溢出、重入问题）
- [ ] 确认权限变量自身是否可被篡改（owner、roles 等的初始化和更新）

**第三阶段：语境分析**
- [ ] 函数是否属于标准接口（ERC20、ERC721、ERC1155 等）
- [ ] 是否为回调函数，需要外部合约调用
- [ ] 是否在业务流程中已通过其他 external 函数进行权限控制

**第四阶段：风险评估**
- [ ] 函数操作的数据范围（单个用户、全局状态、跨合约）
- [ ] 攻击可重复性（单次可用 vs 持续可用）
- [ ] 经济损失量级（精度调整 vs 完全掏空）

### 真实案例对照

**漏洞确认案例**（2024 实际报告）
```vyper
# Tapioca 的 StargateStrategy，permitToken 函数无权限
def permitToken(token: address):
    self.tokens[token] = True  # 任意人可添加恶意代币，导致冻结风险

# 修复方案：添加访问控制
def permitToken(token: address):
    assert msg.sender == self.owner
    self.tokens[token] = True
```

**误报驳回案例**（正确的现代实现）
```vyper
# OpenZeppelin 的 AccessControl 方案，函数虽然是 external，但权限完整
hasRole: HashMap[bytes32, HashMap[address, bool]]

def grantRole(role: bytes32, account: address):
    assert msg.sender == self.owner or self.hasRole[ADMIN_ROLE][msg.sender]
    self.hasRole[role][account] = True
```
