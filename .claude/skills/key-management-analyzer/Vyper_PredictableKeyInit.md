# Vyper 可预测密钥初始化

使用 `block.timestamp`、`block.number`、`block.prevhash` 等链上可预测值作为密钥种子或初始化参数，导致密钥可被提前计算或重放。常见于签名验证、权限控制、预言机适配器等模块。

## Details

**典型代码模式：**
```vyper
# 危险：使用 block.timestamp 作为密钥种子
nonce: public(uint256)

@external
def generate_session_key() -> bytes32:
    self.nonce += 1
    return keccak256(concat(convert(block.timestamp, bytes32), convert(self.nonce, bytes32)))

# 危险：使用 block 属性初始化签名盐值
signing_salt: bytes32

@external
def __init__():
    self.signing_salt = convert(block.number, bytes32)
```

**快速定位核心操作（L2-L3）：**
- 扫描 `keccak256()`、`sha256()` 等哈希函数调用，检查输入源是否包含 `block.*` 属性
- 关注 `@external/@internal` 函数中涉及 `key`、`seed`、`nonce`、`salt`、`secret` 命名的变量初始化
- 追踪 `__init__()` 构造函数及 `@external` 初始化函数中的随机数生成逻辑
- 检查状态变量赋值语句右侧是否直接引用可预测链上数据

**快速定位保护机制（L1-L2）：**
- 搜索 `block.difficulty`（Vyper 0.3.x 后已废弃）、`prevrandao`（新版本随机源）的使用
- 检查是否调用外部预言机（`raw_call`、`staticcall`）获取链外熵源
- 确认是否存在 `tx.origin` 或 `msg.sender` 与链上数据的组合增强不可预测性
- 验证是否有时间窗口限制或最小延迟机制（`assert block.timestamp > last_update + MIN_DELAY`）

## Classify

**漏洞判定：**
- 密钥/种子**完全依赖**可预测链上数据，且用于加密、签名验证、权限控制等安全关键场景
- 攻击者可提前模拟执行或监听 mempool 计算出密钥值，造成实际安全影响

**误报排除：**
- 可预测值仅用于非安全场景（如 UI 展示、日志标识）
- 链上数据与高熵外部输入（用户签名、预言机随机数）混合使用，且外部输入不可控
- 代码中存在后续的密钥派生步骤，将可预测值与私密状态再次哈希

**代码异味：**
- 虽然混合了 `msg.sender`，但在多签或代理合约场景下 `msg.sender` 可被预测
- 使用了 `prevrandao`，但未考虑验证者操纵风险（Pos 链）

## Low risk

- **有限使用场景**：密钥仅用于临时会话标识，泄露不影响资金或核心权限
- **时效性防护**：密钥每次生成后立即失效，且存在严格的重放保护（如递增 nonce + 签名验证）
- **经济激励不足**：预测密钥的成本（如需贿赂验证者操纵 prevrandao）远高于攻击收益
- **冗余保护层**：即使密钥被预测，仍需通过多重签名、时间锁或白名单等额外验证

## 审计专业技巧

### 1. 真实漏洞案例特征

**案例1：Entropy 不足导致的会话劫持（Realworld Issue）**
```vyper
# 真实漏洞：用户 session_id 完全可预测
user_sessions: public(HashMap[bytes32, User])

@external
def create_session(username: String[50]) -> bytes32:
    session_id = keccak256(concat(convert(block.timestamp, bytes32),
                                  convert(msg.sender, bytes32)))
    self.user_sessions[session_id] = User(username=username, balance=0)
    return session_id
```
**漏洞确认点**：
- 攻击者可在交易进入 mempool 时监听，读取 `block.timestamp`（块被生成时已知）
- 批量枚举 `msg.sender` 地址（或使用目标地址），提前计算出合法用户的 session_id
- 在用户未察觉的情况下伪造会话，盗取资金或修改配置
- **审计关键：** 该密钥直接用于权限控制（`user_sessions` 字典的访问键），存在直接安全影响

**案例2：签名盐值可被重放（DeFi Audit Finding）**
```vyper
# 真实漏洞：EIP-712 签名验证中盐值与块号绑定
nonce_salt: HashMap[address, bytes32]

@external
def execute_with_signature(target: address, data: Bytes32, signature: bytes65) -> bool:
    # salt 每块只有一个值，attacker 可推导后续块的 salt
    salt = keccak256(concat(convert(block.number, bytes32),
                           convert(target, bytes32)))
    # 验证签名...
    return True
```
**漏洞特征**：
- 同一区块内多笔交易使用相同 salt，不同区块 salt 可线性预测
- 攻击者可在未来块中重放同一签名（块号递增可预测）
- 允许重复执行同一交易，造成重放攻击
- **审计关键：** 使用 `block.number` 作为签名成分直接破坏了签名的唯一性约束

### 2. 常见误报与区分技巧

**误报案例1：用于临时标识的可预测值**
```vyper
# 不是漏洞：仅用于事件日志索引
event SessionCreated:
    session_id: bytes32

@external
def log_session():
    session_id = keccak256(concat(convert(block.timestamp, bytes32),
                                  convert(msg.sender, bytes32)))
    log SessionCreated(session_id)
    # 事件不影响合约逻辑，仅用于前端查询
```
**区分方法**：
- 搜索该变量的所有读取位置（`session_id` 是否被用于状态修改或权限检查？）
- 如果仅在 `log`/`emit` 中使用，通常是误报
- **确认方法：** Grep 检查变量是否出现在条件语句、字典查询、权限检查中

**误报案例2：与高熵值混合的密钥**
```vyper
# 低风险：结合用户签名与块数据
@external
def create_vault(user_signature: bytes65, config_hash: bytes32) -> bytes32:
    vault_key = keccak256(concat(
        convert(block.timestamp, bytes32),
        user_signature,  # 用户签名具有高熵，攻击者无法提前预测
        config_hash      # 用户提供的数据
    ))
    return vault_key
```
**区分方法**：
- 检查输入中是否包含用户签名、预言机输出、链外熵源
- 验证这些高熵值是否由**不可控方**生成（用户、预言机），而非合约本身控制
- 评估攻击者是否有现实手段同时操纵多个高熵源
- **关键问题：** "攻击者能否在交易前同时预测所有输入？"若答案为否，则通常不构成漏洞

**误报案例3：存在有效重放保护的场景**
```vyper
# 低风险：nonce 递增提供重放保护
user_nonce: HashMap[address, uint256]

@external
def execute_action(data: bytes32, signature: bytes65):
    # salt 虽然可预测，但与 nonce 混合使用
    salt = keccak256(concat(
        convert(block.number, bytes32),
        convert(self.user_nonce[msg.sender], bytes32)
    ))
    # 验证签名(salt) 后递增 nonce
    assert self._verify_signature(data, signature, salt)
    self.user_nonce[msg.sender] += 1
```
**区分方法**：
- 检查是否存在 nonce/counter/版本号递增机制
- 验证签名验证是否包含 nonce（防止同一签名多次使用）
- 确认 nonce 更新的原子性（必须在验证后立即更新）
- **审计关键：** 即使 salt 可预测，若 nonce 不可预测且会递增，则不可重放

### 3. 审计检查清单

**第一步：信息收集（扫描 10 分钟）**
- [ ] 使用 `block.timestamp`、`block.number`、`prevrandao` 的所有位置
- [ ] 涉及 `key`、`seed`、`salt`、`nonce` 命名的变量初始化
- [ ] 所有哈希函数（`keccak256`）的入参来源

**第二步：用途分析（关键步骤）**
- [ ] 追踪可预测值的使用位置（HashMap 访问键？权限检查？）
- [ ] 判断该值是否影响资金转移、权限变更、签名验证
- [ ] 确认是否用于安全关键场景（access control, signature validation）

**第三步：防护评估（判断真假）**
- [ ] 是否包含高熵外部输入（用户签名、预言机输出）？
- [ ] 是否存在有效的 nonce/counter 重放保护？
- [ ] 是否存在时间窗口限制或快速失效机制？
- [ ] 攻击者获利成本是否明显高于预期收益？

**第四步：现实可性论证**
- [ ] 在当前网络环境下，attacker 操纵 `block.*` 的成本是多少？
- [ ] 该操纵是否需要成为验证者或控制大量节点？
- [ ] 对于 L2 或 Rollup，centralized sequencer 是否可控制块参数？

### 4. 报告撰写建议

**真实漏洞报告模板**
```
[HIGH] 可预测密钥初始化导致权限绕过

位置：XYZ.vy:42 create_session()
问题：session_id = keccak256(block.timestamp, msg.sender)

影响：
1. 攻击者可通过监听 mempool 提前计算 session_id
2. 在用户交易确认前伪造会话，窃取资金

复现步骤：
1. 监听 mempool 发现用户创建会话交易
2. 读取该交易的 block.timestamp（等于当前块时间）
3. 计算 keccak256(timestamp, attacker_address)
4. 调用 create_session()，覆盖用户会话

修复建议：
- 使用 EIP-4399 prevrandao 作为熵源
- 引入外部预言机（Chainlink VRF）
- 结合不可控的用户签名或零知识证明
```

**误报关闭建议**
```
[INFO] 可预测值用于事件日志，不构成安全风险

位置：XYZ.vy:88
分析：该 session_id 仅在 SessionCreated 事件中使用，
      未被用于权限控制或状态修改。
      事件日志本质上是公开信息，可预测性不影响安全性。

确认：已检查所有 session_id 的读取位置，确认不用于 HashMap 访问或条件检查。
```

### 5. 常见误区与教训

**误区1：过度关注可预测性而忽视使用场景**
- 错误态度：看到 `block.timestamp` 就标记漏洞
- 正确态度：先判断该值如何被使用，再评估风险
- 教训：50% 的 "predictable RNG" 报告都是误报，需验证实际安全影响

**误区2：低估混合策略的安全性**
- 错误态度：因为一个输入可预测就否定整个方案
- 正确态度：多个高熵输入混合的安全性 = 最低熵输入
- 教训：用户签名 + `block.number` 仍然相对安全（签名不可伪造）

**误区3：忽视网络特性的防护能力**
- 错误态度：在 L1 评估 L2 Rollup 的随机性风险
- 正确态度：L2 中 sequencer 完全可控块参数，安全性明显低于 L1
- 教训：同样代码在不同网络的风险评级可能不同
