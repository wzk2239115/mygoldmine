**Vyper - 无限制密钥函数 (Unrestricted Key Function)**

密钥管理函数缺乏访问控制，允许任意用户调用并修改关键密钥材料，常见于多签钱包、密钥轮换机制、预言机公钥管理等场景。

## Details

**代码示例：**
```vyper
# 漏洞示例：公钥更新函数无权限限制
oracle_pubkey: public(bytes32)

@external
def updateOracleKey(new_key: bytes32):  # 任何人可调用
    self.oracle_pubkey = new_key

# 漏洞示例：签名者地址更新无保护
authorized_signer: public(address)

@external
def setSigner(new_signer: address):
    self.authorized_signer = new_signer  # 缺少 assert msg.sender == self.owner
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词扫描：`set*`、`update*`、`change*`、`rotate*`、`register*` 等函数名配合 `key`、`signer`、`pubkey`、`verifier`
- 状态变量追踪：查找类型为 `address`、`bytes32`、`bytes[64]` 的公开状态变量，回溯其写入点
- 特征组合：`@external` + 密钥相关状态变量修改 + 无 `assert` 语句

**快速定位保护机制技巧（L2-L3）：**
- **Owner检查（L2）：** 查找 `msg.sender == self.owner` 或 `assert self.owner == msg.sender`
- **角色验证（L2）：** 检查 `self.admins[msg.sender]` 或 `self.hasRole[msg.sender][ADMIN_ROLE]` 等映射访问
- **内部调用（L1）：** 函数声明为 `@internal` 而非 `@external`
- **时间锁/多签（L3）：** 查找 `self.pending_*` 状态变量、`timelock` 模式、或调用外部多签合约
- **不可变设置（L2）：** 检查是否在 `__init__` 中设置后再无修改函数

## Classify

**判定为漏洞：**
- 密钥管理函数可被任意地址调用，且无业务逻辑限制（如需支付高额费用）
- 权限检查逻辑存在但实现错误（如 `!=` 误写为 `==`、使用 `tx.origin` 而非 `msg.sender`）
- 仅在初始化后短期内锁定，后续通过其他无限制函数可重置保护状态

**判定为误报：**
- 函数虽公开但操作的是调用者自己的密钥材料（如 `self.user_keys[msg.sender] = new_key`）
- 存在经济惩罚机制使恶意调用成本远超收益（需结合业务评估）
- 密钥为临时性质且不影响资产安全（如前端显示偏好的公钥昵称）

**判定为代码异味：**
- 密钥修改需通过复杂外部合约调用链验证权限，但缺少本地防御性检查
- 权限检查依赖预言机或跨链数据，存在时间差窗口但概率极低

## Low risk

**以下场景可降低风险等级：**
- 合约为代理合约或工厂合约，每个用户部署独立实例且仅管理自身密钥
- 密钥修改触发明显事件日志，配合链下监控可及时响应（需确认有监控实施）
- 密钥仅用于只读验证场景，且错误密钥仅导致功能不可用而非资产损失
- 合约处于测试网或已明确标注为实验性质，实际资产价值可忽略
- 存在链下社会共识恢复机制（如DAO投票可回滚）且响应时间短于攻击获利周期

## 审计专业技巧与经验

### 真实漏洞特征模式

**模式1：跨合约密钥篡改攻击**
```vyper
# 真实漏洞案例：Wintermute Hacks(多个项目)
# 特征：更新密钥的函数对调用者身份零校验，且密钥用于签名验证
token_issuer: public(address)

@external
def updateIssuer(new_issuer: address):
    self.token_issuer = new_issuer  # 真实漏洞：无 msg.sender 检查
    log TokenIssuerUpdated(new_issuer)
```
**识别技巧：** 追踪密钥的使用位置，若在 `require signature == recover(message, key)` 等签名验证中被使用，直接构成HIGH严重程度。

**模式2：权限检查绕过变种**
```vyper
# 误导式权限检查：仅校验初始化状态
is_initialized: bool
owner: address

@external
def setOwner(new_owner: address):
    assert not self.is_initialized  # 真实漏洞：只要初始化一次，后续无人能修改
    self.owner = new_owner
    self.is_initialized = True
```
**识别技巧：** 搜索 `assert` 语句后是否同时修改了状态变量。真实漏洞往往在权限检查与状态修改间存在逻辑不一致。

**模式3：多签模拟而非真正多签**
```vyper
# 真实误报发现：项目方声称多签，实际伪实现
signers: DynArray[address, 3]

@external
def updateSigners(new_signers: DynArray[address, 3]):
    # 仅检查是否由现有签者之一调用
    assert msg.sender in self.signers  # 足够安全的权限模型，非漏洞
    self.signers = new_signers
```
**识别技巧：** 审查"多签"是否真正要求 M-of-N 签名，或仅需单个授权方批准。后者若权限检查无误则不是漏洞。

### 常见误报案例与反思

**误报案例1：用户自管理密钥被误报为全局漏洞**
```vyper
# 此类被频繁误报为漏洞
user_pubkeys: public(HashMap[address, bytes32])

@external
def setPubkey(pubkey: bytes32):
    self.user_pubkeys[msg.sender] = pubkey  # 正确：每用户独立管理
```
**教训：** 检查修改的状态变量是否以 `msg.sender` 为索引。若为 `self.user_pubkeys[msg.sender]`，则用户只能修改自己的密钥，无漏洞。

**误报案例2：工厂合约中的权限继承**
```vyper
# 工厂模式中常被误报
child_contracts: public(DynArray[address, 1000])

@external
def deployChild(owner: address):
    child = create_from_blueprint(CHILD_BLUEPRINT, owner, code_offset=0)
    self.child_contracts.append(child)
    # 每个child独立，在child内部owner可修改密钥，主合约不可，无漏洞
```
**教训：** 区分主合约与子合约的权限边界。工厂模式下，即使主合约无权限检查，子合约内的密钥修改若受保护也无漏洞。

**误报案例3：代码异味 vs 真实漏洞**
```vyper
# 此类被判为"代码异味"的案例
verifier_contract: public(address)

@external
def updateVerifier(new_verifier: address):
    # 权限在外部合约中检查，本地无assert
    assert extcall IAccessControl(self.access_control).hasRole(
        msg.sender, ADMIN_ROLE
    )  # 跨合约权限检查有风险但非必然漏洞
    self.verifier_contract = new_verifier
```
**教训：** 跨合约权限检查虽有风险（重入、预言机依赖），但若访问控制合约本身安全、权限检查正确实施，则应评为MEDIUM风险而非HIGH。

### 审计决策树

```
发现密钥修改函数 @external
    ↓
Step1: 是否有 assert/require 权限检查？
    ├─ 无 → 99%确定是漏洞（除非是用户自管理）
    ├─ 有：检查检查逻辑
        ├─ msg.sender == owner 或 msg.sender in admins → 权限模型清晰，检查实现
        │   ├─ 实现正确 → 无漏洞
        │   └─ 实现错误（如 != 误写 ==） → 高危漏洞
        ├─ extcall 跨合约检查 → 记为MEDIUM（重入风险），需验证被调方
        └─ 时间锁/多签 → 检查是否真正实施（M-of-N）

Step2: 检查修改目标
    ├─ self.global_key (全局密钥) → 若无权限 → 严重漏洞
    ├─ self.user_keys[msg.sender] (用户自管理) → 即使无权限也可能无漏洞
    └─ self.pending_key (待确认状态) → 检查最终确认机制

Step3: 检查密钥用途
    ├─ 签名验证 → 若无权限 → 直接漏洞，可伪造交易
    ├─ 加密/解密 → 若无权限 → 隐私泄露或业务中断
    └─ 只读验证 → 若无权限 → 可能仅导致功能异常，风险降低
```

### 真实审计经验总结

1. **权限检查的 4 层验证清单**
   - L1: 本地 assert 检查 (msg.sender)
   - L2: 映射查询验证 (roles/admins 映射)
   - L3: 时间锁延迟验证 (pending 状态 + delay)
   - L4: 多签/DAO验证 (需 M-of-N 签名或投票)
   - 真实项目应至少实施 L1+L2 或 L3+L4 的组合

2. **密钥生命周期上下文**
   - 初始化密钥 > 周期性轮换 > 紧急撤销
   - 仅 `__init__` 可修改 = 最安全
   - 修改函数受权限保护 = 安全（若权限实现正确）
   - 无限制修改 = 漏洞（除非是用户自管理）

3. **事件日志的辅助价值**
   - 若函数发出 `log KeyUpdated(old_key, new_key, caller)` → 帮助链下监控，但不替代权限检查
   - 无日志 + 无权限 = 隐蔽漏洞，风险更高
