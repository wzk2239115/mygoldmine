**Vyper - 非规范化签名（Non-Canonical Signature）**  

常出现在 DeFi 协议的链下授权、限价单签署、批量交易等业务逻辑实现中。由于 ECDSA 签名的可塑性，同一消息的有效签名可通过翻转 s 值（s' = secp256k1_order - s）构造出等价签名，导致签名重放、nonce 绕过等安全问题。

## Details

**代码示例：**
```vyper
@external
def execute_permit(hash: bytes32, v: uint8, r: bytes32, s: bytes32):
    signer: address = ecrecover(hash, v, r, s)  # 未检查 s 值规范性
    assert signer == self.authorized_signer
    self.execute_action()
```

**快速定位核心操作（L2-跳读）：**  
- 直接搜索 `ecrecover` 调用点，检查其参数来源与返回值用途
- 关注接受外部签名参数（v, r, s）的 `@external` ��数
- 追踪签名是否用于一次性授权、nonce 管理、状态变更等关键操作

**快速定位保护机制（L3-逐行读）：**  
- 检查 `s` 值是否有上界限制：`assert convert(s, uint256) <= 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0`
- 查找是否使用签名哈希（keccak256(concat(r, s, v))）作为唯一性标识存储
- 确认是否有 nonce 机制且 nonce 在签名验证后立即递增

## Classify

**漏洞确认条件：**  
- 签名验证后执行不可逆操作（转账、铸币、权限变更）且缺少 nonce 或仅记录单一签名参数（如仅记录 r）
- 系统依赖签名唯一性进行重放保护，但未对 s 值做规范性校验

**误报识别：**  
- 签名仅用于只读查询或日志记录，无状态变更
- 已通过 `used_signatures` 映射存储完整签名哈希（包含 v/r/s 全部参数）

**代码异味：**  
- 签名验证逻辑分散在多个函数，难以统一添加规范性检查
- 使用自定义签名结构但未文档化规范性要求

## Low risk

**适用场景：**
- 签名仅用于临时会话令牌，有效期极短（< 10 分钟）且单次验证后立即失效
- 系统已实现完整的 nonce + deadline 双重保护，且 nonce 与签名者地址强绑定
- 业务场景允许同一授权意图多次执行（如无限授权的 approve 操作）
- 已通过链下服务对签名进行预处理，确保上链前 s 值规范化

## 审计专业技巧

### 1. 真实漏洞识别三角法

**漏洞成立的三个必要条件缺一不可：**

① **签名可塑性** - 同一消息存在两个有效签名
```vyper
# 检查点：是否存在 s 值规范化校验
MAX_S = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0
assert convert(s, uint256) <= MAX_S, "Non-canonical signature"
```
缺失此检查时，`(v, r, s)` 和 `(v', r, s')` 都能通过 ecrecover 验证。

② **重放利用路径** - 攻击者可驱动非预期代码执行
真实场景（漏洞）：
```vyper
def permit(owner: address, v: uint8, r: bytes32, s: bytes32):
    # 无 nonce，仅验证签名权限 → 可无限重放
    signer = ecrecover(keccak256(owner), v, r, s)
    assert signer == owner
    self.balances[owner] += 1000  # 无限增发
```

误报场景（安全）：
```vyper
def permit(owner: address, nonce: uint256, v: uint8, r: bytes32, s: bytes32):
    # 虽无 s 校验，但 nonce 被包含在签名哈希中
    msg_hash = keccak256(concat(owner, convert(nonce, bytes32)))
    signer = ecrecover(msg_hash, v, r, s)
    assert signer == owner
    assert self.nonces[owner] == nonce  # 强制递增
    self.nonces[owner] += 1  # 立即消费
```
第二个例子中，即使 s 非规范，攻击者无法重放因为 nonce 已消费。

③ **状态不可逆** - 被重放操作对系统产生永久影响
- ✅ 漏洞：转账、铸币、权限变更
- ❌ 误报：只读查询、条件检查、日志事件

### 2. 常见误报陷阱

**陷阱 A：误认为 Nonce 检查无效**
```vyper
@internal
def _check_signature(msg: bytes32, nonce: uint256, v: uint8, r: bytes32, s: bytes32):
    signer = ecrecover(msg, v, r, s)
    # ❌ 错误认知：这里检查了 nonce 就安全了
    assert self.nonces[signer] == nonce

@external
def swap(amount: uint256, nonce: uint256, v: uint8, r: bytes32, s: bytes32):
    msg_hash = keccak256(concat(convert(amount, bytes32), convert(nonce, bytes32)))
    self._check_signature(msg_hash, nonce, v, r, s)
    # ✅ 关键：nonce 是否包含在签名哈希中？
    # 若签名哈希中 nonce 是常量，则签名与特定 nonce 无绑定 → 真漏洞
```

**陷阱 B：忽视签名杂凑中的业务参数**
```vyper
# 场景：允许用户签署多笔交易
msg_hash = keccak256(concat(msg, nonce, to_address, amount))  # ✅ 安全
# vs
msg_hash = keccak256(concat(msg, nonce))  # ❌ 漏洞（amount/to 可篡改）
```

**陷阱 C：存储签名哈希但检查不完整**
```vyper
used_signatures: HashMap[address, DynArray[bytes32, 1000]] = {}

def verify_permit(sig_hash: bytes32, v: uint8, r: bytes32, s: bytes32):
    # ❌ 误报：仅比较 r 值
    assert not used_signatures[msg.sender].contains(r)
    # ✅ 应该比较完整签名（v, r, s）或其哈希
    full_sig_hash = keccak256(concat(v, r, s))
    assert full_sig_hash not in used_signatures[msg.sender]
```

### 3. 审计决策树

```
发现 ecrecover 调用
  ├─ 检查 s 值是否有上界限制
  │  ├─ YES → 低风险（s 已规范化）
  │  └─ NO → 继续第二步
  │
  ├─ 检查签名是否用于关键操作（转账、铸币、权限）
  │  ├─ NO（仅日志/查询） → 误报
  │  └─ YES → 继续第三步
  │
  └─ 检查重放保护机制
     ├─ nonce/deadline 包含在签名哈希中 + 原子消费 → 安全
     ├─ 签名哈希存储在链上映射 + 完整 sig 比较 → 安全
     ├─ 仅记录 r 值或缺少重放保护 → 真漏洞 ⚠️
     └─ 单次签名、业务允许重复 → 低风险
```

### 4. 实战对比

**真实漏洞（OpenZeppelin ECDSA 2.3 之前）：**
```vyper
# EIP-2612 Permit 不完整实现
def permit(owner: address, spender: address, value: uint256,
           deadline: uint256, v: uint8, r: bytes32, s: bytes32):
    assert block.timestamp <= deadline
    # ❌ 问题：s 未校验 + nonce 处理有漏洞
    digest = keccak256(concat(owner, spender, value, deadline))
    recovered = ecrecover(digest, v, r, s)
    assert recovered == owner
    self.approve(spender, value)  # 可无限重放不同的 (s, s') 对
```

**修复版本：**
```vyper
MAX_S = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0

def permit(owner: address, spender: address, value: uint256,
           deadline: uint256, v: uint8, r: bytes32, s: bytes32):
    assert block.timestamp <= deadline
    assert convert(s, uint256) <= MAX_S  # ✅ s 规范化检查
    assert v in [27, 28]  # ✅ v 值合法性

    nonce = self.nonces[owner]  # ✅ nonce 绑定到签名者
    digest = keccak256(concat(
        owner, spender, convert(value, bytes32),
        convert(deadline, bytes32), convert(nonce, bytes32)
    ))
    recovered = ecrecover(digest, v, r, s)
    assert recovered == owner

    self.nonces[owner] += 1  # ✅ 立即递增，防重放
    self.approve(spender, value)
```

### 5. 检查清单

- [ ] 定位所有 `ecrecover` 调用点
- [ ] 验证 `s` 值是否有 `<= MAX_S` 的断言
- [ ] 确认签名作用：状态变更 vs 只读
- [ ] 追踪签名杂凑中包含的参数：nonce/deadline/amount/to 是否齐全
- [ ] 检查 nonce/deadline 是否在杂凑计算前获取（防时间窗口漏洞）
- [ ] 验证重放保护的原子性：签名消费与状态变更是否原子
- [ ] 查找是否有多个 ecrecover 实现：确保规范化检查一致
