**Vyper - Raw Delegatecall To Untrusted Address**  
常出现在自定义代理或逻辑分发器实现中，使用 `raw_call(..., is_delegate_call=True)` 调用外部地址，且未对目标地址做白名单或完整性校验，允许恶意代码在当前合约上下文中执行。

## Details

**代码示例：**
```vyper
@external
def execute(target: address, data: Bytes[1024]):
    # 危险：直接delegatecall到用户提供的地址
    raw_call(target, data, is_delegate_call=True)
```

**快速定位核心操作（L2-跳读）：**  
- 搜索关键字：`raw_call` + `is_delegate_call=True`
- 定位所有delegatecall调用点，检查目标地址来源
- 关注`@external`/`@public`函数中接收`address`类型参数的情况

**快速定位保护机制（L3-逐行读）：**  
- 检查目标地址是否来自`immutable`/`constant`常量
- 检查是否存在白名单映射：`allowed_implementations: HashMap[address, bool]`
- 检查是否有`assert target in [...]`或`assert self.whitelist[target]`验证逻辑
- 检查是否仅调用已初始化存储的实现地址（如`self.implementation`）

## Classify

**漏洞标准：**  
目标地址可被外部输入直接或间接控制，且无有效验证机制，可导致合约状态被任意篡改或资产被盗。

**误报情况：**  
1. 目标地址为编译时硬编码常量
2. 目标地址仅能由owner/admin通过多签/时间锁设置，且有完整事件日志
3. 目标地址从经审计的注册表合约读取，且注册表有严格准入控制

**代码异味：**  
目标地址虽有验证，但验证逻辑可被绕过（如白名单可被攻击者修改、验证条件不充分），降级为中危或需附加说明。

## Low risk

1. **受限调用者：** 仅owner/特权角色可触发，且角色管理机制完善（多签、时间锁）
2. **只读delegatecall：** 目标合约仅执行查询操作，不修改状态（需人工确认目标合约逻辑）
3. **沙盒环境：** 合约本身无资产、无权限，仅作为测试或转发合约
4. **限定数据范围：** calldata经过严格编码限制，仅允许调用特定函数签名且参数可控

## 审计专业技巧 - 真实漏洞 vs 误报区分

### 关键识别点

**真实漏洞的8大特征：**

1. **地址输入链完全可控** - 用户提供的address参数直接传入raw_call，无任何中间转换
   ```vyper
   # ❌ 真实漏洞
   def proxy_call(impl: address, data: Bytes[1024]):
       raw_call(impl, data, is_delegate_call=True)  # impl完全由caller控制
   ```

2. **验证缺失或逻辑缺陷** - 声称有白名单但：
   - 白名单mapping未初始化（空的）
   - 权限检查在raw_call之后（已执行）
   - 验证条件为`assert len(data) > 0`（只检查长度，无效）

3. **状态变量可被外部修改** - 存储的implementation地址缺乏setter保护：
   ```vyper
   # ❌ 真实漏洞
   implementation: public(address)  # 无权限控制的public变量

   @external
   def set_impl(new_impl: address):
       self.implementation = new_impl  # 任何人都能修改
   ```

4. **事件伪造或缺失** - 虽有事件但：
   - 事件在状态变更后才记录（重排序风险）
   - 事件中缺少timestamp或caller信息
   - 事件为off-chain emit，无法链上验证

5. **多层delegatecall链** - 目标地址再delegatecall到第三方（风险成倍增加）

6. **动态selector生成** - 从input数据动态切片提取function selector：
   ```vyper
   # ❌ 高危
   selector: Bytes[4] = data[:4]  # 未验证
   raw_call(impl, data, is_delegate_call=True)
   ```

7. **代理模式但无EIP-1967标准** - 实现接口不规范，难以溯源

8. **状态值依赖用户input间接确定** - 如：`whitelist[keccak256(user_input)]`

---

### 常见误报陷阱

**误报Case 1: 硬编码常量 ✓ 安全**
```vyper
TRUSTED_LOGIC: constant(address) = 0x1234...

def execute(data: Bytes[1024]):
    raw_call(TRUSTED_LOGIC, data, is_delegate_call=True)
```
**判断标准：** 编译时即确定，无法运行时修改 → 标记为INFO（代码坏味道）而非漏洞

---

**误报Case 2: Owner-only setter + 事件完整 ✓ 降级为低风险**
```vyper
implementation: public(address)
event UpdateImplementation:
    new_impl: indexed(address)
    caller: indexed(address)
    timestamp: uint256

@external
def set_implementation(new_impl: address):
    assert msg.sender == self.owner
    old_impl: address = self.implementation
    self.implementation = new_impl
    log UpdateImplementation(new_impl, msg.sender, block.timestamp)

    # 额外：可选的时间锁（加分项）
    self.impl_update_time = block.timestamp
```
**判断标准：** 多签合约owner + 完整审计链 → 标记为LOW或INFO

---

**误报Case 3: 注册表合约白名单 ✓ 条件安全**
```vyper
REGISTRY: constant(address) = 0x5678...  # 已审计的registry

@external
def delegatecall_to_registered(impl: address, data: Bytes[1024]):
    # 通过常量registry检查
    assert extcall IRegistry(REGISTRY).is_approved(impl)
    raw_call(impl, data, is_delegate_call=True)
```
**判断标准：** Registry本身已审计 + 调用使用extcall而非raw_call + 检查在raw_call前 → 标记为LOW（依赖registry安全性）

---

**误报Case 4: calldata严格限制 ✓ 降级处理**
```vyper
@external
def fixed_delegatecall(impl: address, amount: uint256):
    # 构造固定格式的calldata，防止任意selector
    data: Bytes[68] = concat(
        method_id("transfer(address,uint256)"),
        convert(msg.sender, Bytes[32]),
        convert(amount, Bytes[32])
    )
    raw_call(impl, data, is_delegate_call=True)
```
**判断标准：** Calldata格式强制限制 + selector预定义 → 标记为MEDIUM（取决于impl来源）

---

### 现场审计检查清单

| 检查项 | 真实漏洞信号 | 安全信号 |
|------|------------|--------|
| **目标地址来源** | 函数参数直接输入 | immutable/constant或受权限保护的storage |
| **验证时机** | raw_call后或无验证 | raw_call前，assert语句 |
| **验证强度** | `require(address != 0)` | 白名单mapping + owner验证 |
| **事件追踪** | 无事件或伪造 | 详细的indexed事件 + timestamp |
| **目标合约** | 动态、用户供应 | 编译时已知或注册表管理 |
| **多重调用** | 连续delegatecall链 | 仅一层delegatecall |
| **calldata来源** | 完全由用户构造 | 固定格式/受限参数 |
| **权限管理** | 无限制public | 多签/时间锁 |

---

### 实战误报修正案例

**初始报告（假阳性）：**
```
[HIGH] Raw delegatecall to user-controlled address
Location: contracts/Proxy.vy:42
raw_call(impl, data, is_delegate_call=True)
```

**深度复查发现：**
```vyper
implementation: public(address)
governance: public(address)  # 多签合约
time_lock: uint256

@external
def set_implementation(new_impl: address):
    assert msg.sender == self.governance
    self.implementation = new_impl
    self.time_lock = block.timestamp + LOCK_PERIOD  # 时间锁

@external
def delegatecall_impl(data: Bytes[1024]):
    assert block.timestamp >= self.time_lock  # 时间锁检查
    raw_call(self.implementation, data, is_delegate_call=True)
```

**修正结论：** 降级为LOW/INFO
- ✓ Implementation由多签governance设置（非owner，更安全）
- ✓ 时间锁机制给用户审查时间
- ✓ 链上历史可追溯
- ⚠️ 注意：需验证governance确实是多签，非另一个单人账户

---

### 动态调用vs静态白名单的实战对比

**反面教材（真实漏洞）：**
```vyper
allowed: HashMap[address, bool]

@external
def grant_permission(target: address):
    self.allowed[target] = True  # ❌ 任何人可调用

@external
def execute(target: address, data: Bytes[1024]):
    assert self.allowed[target]
    raw_call(target, data, is_delegate_call=True)
```

**正面教材（设计安全）：**
```vyper
allowed_list: HashMap[address, bool]
owner: public(address)

@external
def grant_permission(target: address):
    assert msg.sender == self.owner  # ✓ 权限检查
    assert extcall ICodeValidator(VALIDATOR).is_safe(target)  # ✓ 外部验证
    self.allowed_list[target] = True
    log PermissionGranted(target, block.timestamp)

@external
def revoke_permission(target: address):
    assert msg.sender == self.owner
    self.allowed_list[target] = False
    log PermissionRevoked(target, block.timestamp)

@external
def execute(target: address, data: Bytes[1024]):
    assert self.allowed_list[target]
    raw_call(target, data, is_delegate_call=True)
```

---

## 优先级判定框架

- **CRITICAL:** 完全可控地址 + 无验证 + 有资产/权限
- **HIGH:** 可控地址 + 伪验证 + 影响合约状态
- **MEDIUM:** 可控地址 + 部分验证 或 固定地址 + 可控calldata
- **LOW:** 受限地址 + 完整验证 + 事件追踪
- **INFO:** 硬编码地址 或 完美的多签/时间锁设计
