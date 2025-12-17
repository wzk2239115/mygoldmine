# Vyper - 不安全的 ecrecover 使用

## 成因

Vyper 中 `ecrecover()` 内建函数在签名无效或参数非法时返回零地址(`0x0000...0000`)，而非回退交易。若直接使用返回值而未校验零地址，攻击者可构造无效签名绕过身份验证，伪造任意用户授权。

## Details

**代码示例：**

```vyper
@external
def withdraw_with_permit(amount: uint256, v: uint256, r: bytes32, s: bytes32):
    message_hash: bytes32 = keccak256(concat(convert(msg.sender, bytes32), convert(amount, bytes32)))
    signer: address = ecrecover(message_hash, v, r, s)  # ❌ 未验证返回值
    assert self.allowance[signer][msg.sender] >= amount
    self.balances[signer] -= amount
    send(msg.sender, amount)
```

**快速定位核心操作（L2-跳读）：**
- 搜索关键词：`ecrecover(`、`recover(`
- 跳读函数调用链：检查 ecrecover 返回值是否直接用于权限判断、映射查询、余额操作
- 关注模式：`signer: address = ecrecover(...)` 后直接使用 `signer` 而无校验

**快速定位保护机制（L3-逐行读）：**
- 确认是否存在零地址检查：`assert signer != empty(address)` 或 `assert signer != ZERO_ADDRESS`
- 验证是否使用安全封装：`_verify_signature()` 等包含零地址校验的内部函数
- 检查是否使用 EIP-712 标准化哈希及 nonce 机制防重放
- 确认 `v` 值范围校验：`assert v == 27 or v == 28`

## Classify

**确认为漏洞：**
- ecrecover 返回值直接用于权限验证（如映射键、所有者判断），且无零地址校验
- 可构造 payload 使 ecrecover 返回零地址，且零地址在业务逻辑中有意义（如默认映射值非零）

**判定为误报：**
- 零地址已在业务逻辑中被隐式屏蔽（如余额映射为空无法通过后续 assert）
- ecrecover 调用前后存在其他等效验证（如白名单校验、严格的前置条件）
- 返回值仅用于事件记录或非关键性查询

**识别为代码异味：**
- 存在零地址校验但位置不当（如在多个分支后校验，存在遗漏路径风险）
- 校验逻辑分散在多处，缺乏统一封装，增加遗漏概率

## Low risk

**场景判定：**
- 零地址在映射中对应的值为零或空（如 `self.balances[ZERO_ADDRESS] == 0`），且后续逻辑有有效性检查（如 `assert balance >= amount`），实际无法利用
- ecrecover 使用在只读函数或 view 函数中，不触发状态变更
- 签名仅用于审计日志或链下验证参考，非链上权限控制
- 存在多重验证机制，即使 ecrecover 返回零地址，其他验证逻辑仍可阻止攻击（需确认所有路径）

## 审计专业技巧

### 真实漏洞的典型特征

**特征1：零地址可被有效利用**
```vyper
# ❌ 真实漏洞示例
@external
def execute_with_signature(recipient: address, amount: uint256, v: uint256, r: bytes32, s: bytes32):
    signer: address = ecrecover(keccak256(concat(...)), v, r, s)
    # 攻击者传入无效签名，signer = 0x0
    self.approved[signer] = True  # 零地址被标记为已授权
    self._transfer(recipient, amount)  # 任意地址可受益
```
**审计要点：** 必须追踪零地址在后续业务逻辑中的实际影响。零地址能否绕过关键检查、是否被用作有效的授权方、是否能触发价值转移或状态篡改。

**特征2：多条件验证中缺漏必要检查**
```vyper
# ❌ 看似安全但存在路径漏洞
@internal
def _verify_and_execute(data: bytes32, v: uint256, r: bytes32, s: bytes32) -> bool:
    if ecrecover(data, v, r, s) == self.owner:  # 仅在此分支检查
        return True
    # 其他分支可能直接返回或跳过校验
    if self.fallback_mode:
        return True  # 零地址攻击绕过主路径
```
**审计要点：** 不能仅看单个分支，必须遍历所有执行路径。ecrecover 返回值的校验必须在所有可能使用它的地方执行。

**特征3：签名验证未遵循 EIP-712 标准**
```vyper
# ❌ 容易重放的签名方案
def permit(spender: address, amount: uint256, deadline: uint256, v: uint256, r: bytes32, s: bytes32):
    message_hash: bytes32 = keccak256(concat(convert(spender, bytes32), convert(amount, bytes32)))
    # 缺少 nonce、chainId、contractAddress 等防重放要素
    signer: address = ecrecover(message_hash, v, r, s)
    assert signer != empty(address)  # 即使检查零地址，也可被跨链重放
```
**审计要点：** 标准化签名消息需包含：nonce、chainId、合约地址、函数选择器。缺少任何一项都可能导致重放或混淆攻击。

### 常见误报的识别方式

**误报1：过度保守的零地址检查**
```vyper
# ✅ 安全的实现示例
@internal
def _verify_signature(message: bytes32, v: uint256, r: bytes32, s: bytes32) -> address:
    signer: address = ecrecover(message, v, r, s)
    assert signer != empty(address), "Invalid signature"  # 明确校验
    assert signer in self.authorized_signers, "Unauthorized"  # 额外的白名单检查
    return signer
```
这不是漏洞，因为零地址永远无法出现在 `authorized_signers` 中（映射初始值为 False）。

**误报2：只读上下文中的 ecrecover**
```vyper
@view
def verify_signature(message: bytes32, v: uint256, r: bytes32, s: bytes32) -> address:
    return ecrecover(message, v, r, s)  # view 函数无法修改状态
    # 即使返回零地址，也无法执行状态变更攻击
```

**误报3：后置的隐式验证**
```vyper
# ✅ 虽然零地址未显式检查，但被隐式阻止
def claim_reward(amount: uint256, v: uint256, r: bytes32, s: bytes32):
    signer: address = ecrecover(..., v, r, s)
    reward: uint256 = self.earned_rewards[signer]  # 零地址对应的 reward = 0（映射初始值）
    assert reward >= amount, "Insufficient rewards"  # 隐式防护：零地址无法通过
    self.earned_rewards[signer] -= amount
    send(signer, amount)
```
**关键判断：** 零地址的初始余额/权限为零，且 require 逻辑必须通过，才能称为隐式防护。需验证映射初始化规则。

### 审计检查清单（按优先级）

1. **P0 - 必检项**
   - [ ] 所有 ecrecover 调用都有零地址检查吗？位置是否在使用前？
   - [ ] 是否存在跳过校验的代码路径？（使用控制流图分析）
   - [ ] 签名消息是否包含 chainId、nonce 等重放防护？

2. **P1 - 高优先级**
   - [ ] 零地址在业务逻辑中的影响范围？能否用于权限提升或资金转移？
   - [ ] ecrecover 的参数来源是否可控？（msg.data、function arguments）
   - [ ] 是否存在多个 ecrecover 调用？返回值处理是否一致？

3. **P2 - 中优先级**
   - [ ] 签名验证是否遵循 EIP-191 或 EIP-712？
   - [ ] 是否使用了已知的安全库（如 OpenZeppelin）？
   - [ ] 是否有测试用例覆盖无效签名场景？

### 实际案例对比

| 特征 | 真实漏洞 | 误报 |
|------|--------|------|
| 零地址检查 | 无或位置错误 | 存在且位置正确 |
| 利用难度 | 易于构造无效签名 | 零地址无实际权限 |
| 影响范围 | 可绕过多个安全检查 | 仅在理论上存在风险 |
| 业务逻辑 | 未考虑零地址情况 | 隐式或显式防护 |
| 重放防护 | 缺少或不完整 | 完整的 nonce/chainId 机制 |
