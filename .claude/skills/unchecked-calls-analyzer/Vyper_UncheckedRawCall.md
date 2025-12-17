# Vyper - Unchecked Raw Call

**漏洞描述**  
使用 `raw_call` 进行动态调用外部合约时，未检查返回的成功标志（success）或返回值，导致调用失败被静默忽略，可能引发状态不一致、资金损失或逻辑中断。

---

## Details

**代码示例：**
```vyper
# 危险写法：未检查返回值
@external
def bridge_transfer(target: address, data: Bytes[1024]):
    raw_call(target, data)  # 忽略返回值
    self.balance_synced = True  # 错误假设调用成功

# 正确写法示例（仅供对比）
@external
def safe_bridge_transfer(target: address, data: Bytes[1024]):
    success: bool = raw_call(target, data, revert_on_failure=False)
    assert success, "Bridge call failed"
```

**快速定位核心操作** **(L1-L2)**：
- **L1 关键词扫描**：`raw_call(`、`send(`、`selfdestruct(`
- **L2 跳读**：检查调用语句是否有变量接收返回值，或是否设置 `revert_on_failure=True`（默认 False）

**快速定位保护机制** **(L2-L3)**：
- **L2 跳读**：查找调用后是否有 `assert`、`if success`、`revert` 语句
- **L3 逐行读**：确认 `raw_call` 参数是否包含 `revert_on_failure=True`，检查后续逻辑是否依赖调用成功假设
- **关键判定**：若既无返回值检查，又未设置自动回滚，则为高风险

---

## Classify

**漏洞判定：**
- 调用结果影响资金流、权限变更、关键状态（如余额同步、所有权转移），且无返回值检查 → **Critical/High 漏洞**
- 调用失败时状态已变更（如先转账后通知外部合约），形成不可逆操作 → **High 漏洞**

**误报判定：**
- 调用为纯通知型（fire-and-forget），明确业务逻辑允许失败且不影响核心功能（需结合业务文档确认）
- 外部调用对象为可信系统合约，且协议设计已在其他层面保证调用成功（如链级别的强制执行）

**代码异味：**
- 非关键日志记录或事件触发调用失败，但缺乏注释说明忽略原因 → 建议添加 `# intentionally ignore failure` 注释
- 调用对象可控且为低风险操作（如查询类调用），但仍应遵循防御性编程原则

---

## Low risk

**以下情况可评为 Low：**
1. **无状态依赖**：调用失败不影响当前合约状态，且后续逻辑有独立验证机制（如通过事件监听补偿）
2. **受限调用范围**：目标地址为白名单且经过多重治理审核，调用数据为静态已知值
3. **冗余保护**：存在外部监控系统或定时任务可检测并修复调用失败后果
4. **非关键路径**：调用仅用于辅助功能（如价格预言机备用源），主路径已有失败降级方案

**注意**：即使评为 Low，审计报告中仍需指出缺陷，并建议添加显式检查或注释说明设计意图。

---

## 真实漏洞 vs 误报区分指南

### 高危真实漏洞标志

1. **资金流依赖性**（Critical）
   - 示例：`raw_call(recipient, data)` 后直接执行 `self.balances[recipient] += amount`
   - 风险：调用失败但状态已更新，导致资金重复转账或泄露
   - 识别：检查调用前后是否有 `self.balances`、`self.total_supply` 等财务相关变量修改
   - 真实案例：跨链桥接合约，调用失败导致锁定资金在原链而接收方无法获得映射资产

2. **权限/所有权变更** （High）
   - 示例：`raw_call(admin_update_contract)` 后，`self.owner = new_owner`
   - 风险：权限变更不可逆，调用失败但权限已转移
   - 识别：检查是否涉及 `owner`、`admin`、`minter` 等关键角色变更

3. **状态不一致窗口**（High）
   - 示例：合约记录 `self.synced = True`，实际外部系统可能同步失败
   - 风险：后续交互基于错误的同步状态进行
   - 识别：检查是否存在 `synced`、`initialized`、`status` 等同步状态标志

### 常见误报模式及正确处理

**模式 1：事件日志记录调用**
```vyper
# 常被误报为漏洞，实际可能是低风险
raw_call(logger, log_data)
log EventLogged(...)

# 真实漏洞表现：EventLogged 事件是后续业务依赖的核心数据源
# 审计技巧：查看此事件是否被链外监听器或其他合约作为核心业务逻辑的输入
```

**模式 2：通知型调用（Fire-and-Forget）**
```vyper
# 被误报场景：调用第三方通知服务
raw_call(notification_service, encode_notification())

# 区分关键：此调用是否影响用户核心权益？
# - 若只是日志/UI通知 → Low 风险
# - 若后续费用计算依赖此通知成功 → High 风险
```

**模式 3：已设防的调用**
```vyper
# 被误报为未检查，实际有隐性保护
try:
    success: bool = raw_call(...)
except:
    pass
# Vyper 无 try-catch，但可通过 revert_on_failure 实现检查

# 审计技巧：需确认是否显式设置 revert_on_failure=True
raw_call(target, data, revert_on_failure=True)  # 实际上是受保护的
```

### 审计工作流实践经验

**第 1 层扫描（快速判定）**
- 搜索 `raw_call` 、`send`，立即检查下一行是否有变量赋值
- 若无赋值 → 进入第 2 层；若有赋值 → 检查是否使用了返回值

**第 2 层数据流追踪（区分真伪）**
- 跟踪调用目标 `target` 的来源：是白名单常量、参数还是动态地址？
- 跟踪返回值使用：是否有 `assert`、分支判断、或被忽略？
- 记录调用所在函数是否为 `external`（有用户输入）还是 `internal`（受控上下文）

**第 3 层业务关联性（确定严重性）**
```vyper
# 示例：判定是否为真实漏洞的完整流程
@external
def complex_operation(recipient: address, amount: uint256):
    # Step 1: 调用外部合约进行检查
    success: bool = raw_call(checker_contract, method_selector)
    # ↑ 有返回值，但未检查

    # Step 2: 状态更新
    self.user_balance[recipient] -= amount  # 先减少

    # Step 3: 外部转账
    raw_call(recipient, transfer_data)  # 再转账
    # ↑ 调用失败时，状态已改变 → 真实漏洞
```

### 真实案例借鉴

- **Wormhole Bridge (2022)**：跨链验证 `raw_call` 失败未检查，导致 3.25 亿美元损失
  - 教训：跨链操作的状态同步检查必须显式且冗余

- **Compound 治理调用**：管理员操作 `raw_call` 涉及权限变更
  - 教训：权限相关操作不能有任何沉默失败的可能性

### 审计报告建议模板

```
漏洞：Unchecked Raw Call at [function_name, line_X]
判定流程：
1. 调用对象：[描述目标地址特性]
2. 返回值检查：[有/无]
3. 后续状态依赖：[列举受影响的状态变量]
4. 失败影响范围：[资金/权限/状态一致性]
→ 评级：[Critical/High/Medium/Low]

建议：
- 添加显式检查：assert success 或 revert_on_failure=True
- 若确认为低风险操作，补充设计文档说明为何可忽略
```
