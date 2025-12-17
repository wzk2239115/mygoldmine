# Vyper_MissingOwnerCheck

**漏洞描述**  
关键状态变更函数（金库提款、参数配置、紧急暂停等）未验证 `msg.sender` 是否为合约 owner，导致任意用户可执行特权操作。

## Details

**代码示例**
```vyper
owner: public(address)

@external
def withdrawAll():
    # ❌ 缺失 owner 检查
    send(self.owner, self.balance)

@external
def setFee(_fee: uint256):
    # ❌ 缺失 owner 检查
    self.fee = _fee

@external
def pause():
    # ❌ 缺失 owner 检查
    self.paused = True
```

**快速定位核心操作（L1-L2）**
- **L1关键词扫描**：搜索状态变更函数 `@external def`，优先关注 `withdraw`、`transfer`、`set*`、`update*`、`pause`、`emergency`、`migrate` 等特权操作命名
- **L2跳读验证**：检查函数体首行是否存在 `assert msg.sender == self.owner` 或调用 `self._onlyOwner()` 类似检查

**快速定位保护机制（L2-L3）**
- **L2跳读定位**：在 `@external` 函数前3行内查找 `assert msg.sender == self.owner/admin/authority`
- **L3逐行读取**：追踪 `self.owner` 初始化位置（`__init__` 或 `initialize`），确认是否存在多签/时锁等额外防护
- **L3逐行读取**：检查是否使用装饰器模式（如 `@only_owner`）或内部函数封装权限检查（需追踪 `_onlyOwner()` 实现）

## Classify

**漏洞判定**  
- 函数修改关键状态（余额、费率、白名单、暂停标志）且缺失任何 owner/admin 验证
- 缺失验证的函数可被非授权地址直接调用成功

**误报排除**  
- 函数仅读取状态或计算结果，不修改存储变量
- 函数已通过内部函数（如 `self._checkOwner()`）间接验证，但需确认内部函数实现正确
- 函数通过事件驱动或回调机制触发，且调用链路上有权限验证（需 L4 跨模块追踪）

**代码异味**  
- owner 检查位于函数中段或尾部（应置于首行）
- 多个特权函数重复写 `assert` 而未抽象复用
- 使用 `tx.origin` 替代 `msg.sender` 进行验证（易受钓鱼攻击）

## Low risk

**降级场景**
- 特权函数仅修改非关键配置（如日志开关、UI参数），不影响资金安全和核心逻辑
- 合约已部署且 owner 地址为已验证的多签/DAO合约，攻击窗口期已关闭
- 函数设置有时锁机制，恶意调用会触发延迟并可被拦截
- 链下监控已覆盖相关函数调用，可及时发现异常并响应（需确认监控有效性）

## Audit Pro Tips（审计专业技巧）

### 1. 快速区分真实漏洞与误报的5步法

**步骤1：权限检查形式多样性识别**
- ❌ 误报风险：仅因看到缺失 `assert msg.sender == self.owner` 就判定为漏洞
- ✅ 正确做法：检查是否存在以下任一等价验证：
  - 装饰器模式：`@only_owner` / `@admin_only` / `@authorized`
  - 修饰符模式：`self._checkOwner()` / `self._checkAuth()` / `self._validateCaller()`
  - Allowlist/角色检查：`self.authorized[msg.sender]` / `self.isAdmin[msg.sender]`
  - 跨合约验证：通过 `AccessControl` 接口（OpenZeppelin 标准）

**步骤2：修改状态范围精准判定**
- ❌ 常见误报：函数体虽长但仅执行计算和事件发射，不涉及 `self.state_var` 修改
- ✅ 关键信号：存在 `self.xxx = yyy` 赋值语句，且修改的是：
  - 直接资金流向（`self.balance`、`self.vault`、`send()`/`raw_call()`）
  - 核心策略参数（`self.fee`、`self.rate`、`self.threshold`）
  - 访问控制状态（`self.paused`、`self.whitelist`、`self.admin`）
  - 治理关键变量（`self.owner`、`self.governance`）
- ⚠️ 低危险修改：修改计数器、临时变量、UI展示参数（需上下文判断）

**步骤3：权限验证位置逻辑校验**
- ❌ 误报陷阱：权限检查存在但位于循环/条件分支内部，仅部分代码路径验证
  ```vyper
  @external
  def batchTransfer(_recipients: DynArray[address, 10]):
      if len(_recipients) > 0:  # ⚠️ 检查位于条件内，空数组调用无验证
          assert msg.sender == self.owner
      for recipient in _recipients:
          send(recipient, 100)  # 仍可通过空数组传入绕过权限
  ```
- ✅ 验证要点：权限检查应为函数执行的第一步且无条件执行

**步骤4：内部函数实现细节深度追踪**
- ❌ 常见漏报：假设 `self._onlyOwner()` 实现正确而不翻查
- ✅ 追踪清单：
  ```vyper
  @internal
  def _onlyOwner():
      assert msg.sender == self.owner  # 检查是否正确比较
      # 检查是否存在潜在的重入风险或绕过逻辑
  ```
- 需验证：内部函数是否有跳过返回、提前返回、异常抑制等情况

**步骤5：跨合约依赖验证**
- ❌ 误报风险：看到 `assert self.accessControl.hasRole(msg.sender, "ADMIN")` 就判定安全，但未验证 AccessControl 实现
- ✅ 追踪：
  - AccessControl 合约来源（官方库、自写、已审计？）
  - 权限初始化过程（部署时是否正确赋予权限、后续是否可被滥用修改）
  - 多签/时锁保护（权限修改是否有额外保护）

### 2. 真实漏洞特征识别（高可信度信号）

**信号1：owner 初始化异常**
```vyper
owner: public(address) = empty(address)  # 默认为空地址

@external
def initialize(_owner: address):
    # ❌ 缺失检查，任何人都能初始化，第一个调用者可成为 owner
    self.owner = _owner
```
- 攻击面：前端部署、无 reinitialize 保护、create2 地址预测

**信号2：owner 更换权限链条断裂**
```vyper
@external
def setOwner(_newOwner: address):
    assert msg.sender == self.owner  # 有 owner 检查，似乎安全
    self.owner = _newOwner

@external
def emergencyWithdraw():
    # ❌ 但如果 owner 被设为恶意地址，此函数将失效
    assert msg.sender == self.owner
    send(self.governance, self.balance)
```
- 判定要点：权限链条完整性（owner 变更后是否控制权已转移或被永久锁定）

**信号3：多权限混淆**
```vyper
owner: public(address)
admin: public(address)

@external
def withdrawFunds():
    assert msg.sender == self.owner  # 仅检查 owner

@external
def setFee(_fee: uint256):
    # ❌ 检查 admin 而非 owner，权限模型不一致
    assert msg.sender == self.admin
```
- 审计要点：梳理权限层级（owner vs admin vs manager），确认每个函数选择正确的权限

### 3. 常见误报场景与排除法

**误报A：View/Pure 函数标记为漏洞**
```vyper
@external
@view
def getBalance() -> uint256:
    # ✅ 虽无权限检查，但为 view 函数，无法修改状态
    return self.balance
```
- 排除：检查函数是否有 `@view` / `@pure` / 字节码分析是否实际写入状态

**误报B：初始化即锁定的不可更改函数**
```vyper
initialized: public(bool) = False

@external
def initialize(_owner: address):
    assert not self.initialized  # 初始化锁定
    assert msg.sender == self.governance  # 通过治理合约调用
    self.owner = _owner
    self.initialized = True

@external
def setOwner(_newOwner: address):
    # ❌ 虽缺 owner 检查，但由于初始化锁定，此函数无法被调用
    assert msg.sender == self.owner
    self.owner = _newOwner
```
- 排除：确认函数前置条件（如 `assert self.initialized`）导致无法执行

**误报C：虽无内部检查，但通过外层合约包裹的权限验证**
```vyper
# vault.vy
@external
def emergencyPause():
    # ❌ 缺失 owner 检查
    self.paused = True

# proxy.vy - 外层包裹合约
@external
def pauseVault():
    assert msg.sender == self.governance  # ✅ 在外层进行权限检查
    self.vault.emergencyPause()
```
- 排除条件：仅当单独调用内层函数无权限验证且无外层保护时，才判定为漏洞

**误报D：常量初始化或无法改变的状态**
```vyper
IMMUTABLE_FEE: constant(uint256) = 30  # 常量，初始化后不可改变

@external
def setImmutableFee(_fee: uint256):
    # ❌ 虽缺权限检查，但由于变量类型为 constant，赋值会编译失败
    self.IMMUTABLE_FEE = _fee
```
- 排除：编译检查（Vyper 类型系统）直接禁止非法修改

### 4. 上下文相关的风险等级划分

**HIGH（直接资金风险）**
- 缺失权限的 `send()/raw_call()` 调用
- 无约束的转账函数（`transferFrom`）
- 关键参数修改（手续费、滑点、抵押率）直接影响金额计算

**MEDIUM（功能完整性风险）**
- 暂停/冻结功能缺权限（影响可用性）
- 白名单/黑名单修改缺权限（影响参与资格）
- 升级权限缺权限（影响合约逻辑）

**LOW（信息完整性风险）**
- 日志参数修改
- UI 展示参数修改
- 非金融关键的计数器修改

### 5. 审计清单（Checklist）

- [ ] 函数是否有 `@external` 修饰且无 `@view/@pure`
- [ ] 函数体中是否存在 `self.xxx = yyy` 赋值
- [ ] 赋值的状态变量是否属于关键业务状态
- [ ] 函数首行是否存在权限检查（任何形式）
- [ ] 若权限检查在内部函数，是否追踪并确认实现正确
- [ ] 权限验证涉及外部合约，是否审计了外部合约源码
- [ ] 函数是否有前置条件（如 `assert initialized`）影响可执行性
- [ ] 权限检查是否无条件执行（不在分支/循环内）
- [ ] 是否存在多权限混淆（owner vs admin vs operator）
