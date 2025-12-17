# Vyper Raw Call 重入漏洞

## Details

**代码示例特征：**
```vyper
# 典型漏洞模式
@external
def withdraw(amount: uint256):
    balance: uint256 = self.balances[msg.sender]
    # 状态未先更新
    raw_call(msg.sender, b"", value=amount)  # 外部调用
    self.balances[msg.sender] -= amount      # 状态后更新
```

**快速定位核心操作（L2-跳读）：**
- 搜索 `raw_call`、`send`、`create_forwarder_to` 等外部调用原语
- 关注函数内是否存在 `value=` 参数（以太币转账触发 fallback）
- 检查 `raw_call` 的 `reentrant=` 参数，未设置默认允许重入
- 优先审计 withdraw、claim、redeem、swap 等资产流出函数

**快速定位保护机制（L1-关键词扫描 → L3-逐行读）：**
- L1：搜索 `@nonreentrant` 装饰器、`self.locked` 等重入锁变量
- L3：验证状态更新顺序（CEI 模式：Checks-Effects-Interactions）
  - 状态变更是否在 `raw_call` **之前**完成
  - 余额扣减、映射更新、计数器修改等关键状态的时序
- L3：检查 `raw_call` 是否设置 `reentrant=False` 参数
- L4：若调用外部合约接口（非 raw_call），需追踪被调用合约是否可能回调

## Classify

**漏洞判定：**
- 外部调用前未完成状态更新 + 无重入保护 → 确认漏洞
- 可通过构造恶意 fallback/receive 函数重复提取资金或篡改状态

**误报排除：**
- 外部调用为只读视图函数（view/pure）且无状态修改
- 调用目标为可信白名单合约（需二次确认合约逻辑）
- 虽违反 CEI 但后续有不可绕过的唯一性检查（如 nonce 递增）

**代码异味：**
- 状态更新在外部调用后，但该函数被 `@nonreentrant` 保护 → 建议优化顺序
- 使用 `send` 而非 `raw_call(..., reentrant=False)` → 功能等价但语义不清

## Low risk

**低风险场景：**
- 外部调用目标为 EOA 地址（通过 `extcodesize` 检查），无合约代码则无重入可能
- 调用目标为经过审计的官方合约（如 WETH），且仅执行标准转账
- 重入虽可能但无经济价值提取路径（如仅触发事件日志）
- 状态更新虽后置但配合时间锁或多签机制限制单次调用影响
- Vyper 版本 ≥ 0.3.4 且显式使用 `default_return_value=False` 防止返回值污染（与重入相关联风险）

## 审计专业技巧

### 1. **多层次代码追踪法**

**真实漏洞特征识别：**
```vyper
# 漏洞案例1：奖励分配中的重入
@external
def claim_rewards(user: address, amount: uint256):
    assert self.claimed[user] == False
    # 状态更新缺失
    raw_call(user, b"", value=amount, reentrant=True)
    self.claimed[user] = True  # ❌ 状态修改在转账后
    # 攻击者可在receive中再次调用claim_rewards
```

**审计要点：**
- 追踪状态变量被修改的全部路径，不仅限于直接赋值
- 检查是否存在 require/assert 依赖外部可控制状态（如余额、总供应量）
- 对比 CEI 顺序与实际代码执行路径的差异

### 2. **真实漏洞 vs 误报的区分经验**

**常见误报场景（扫描工具容易触发）：**
| 场景 | 为何是误报 | 鉴别方法 |
|------|----------|--------|
| `raw_call` 返回值未使用 | 转账失败不会让状态改变 | 检查是否 assert/require 返回值 |
| 转账到已知非合约账户 | EOA 地址无 fallback/receive | `extcodesize` 验证或官方公钥检查 |
| 配合 `@nonreentrant` 保护 | 互斥锁完全阻止重入 | 逐个函数检查装饰器 |
| 转账后紧跟 `assert` 检查 | 某些原子性操作本身无风险 | 分析该 assert 是否涵盖所有重入场景 |

**真实漏洞的模式识别：**
1. **漏洞基础条件（必须全部满足）**
   - 存在 `raw_call`、`send` 或合约调用且带 value 转账
   - 无 `@nonreentrant` 或 `reentrant=False` 参数
   - 状态更新（余额、映射、计数器）在交互**之后**

2. **攻击可行性验证**
   - 是否存在无限循环的重入触发路径
   - 攻击者构造的恶意合约能否执行回调
   - 重入后的业务逻辑是否存在不一致状态

**实战案例拆解：**
```vyper
# 案例：Vyper 智能合约取款函数
@external
def withdraw(amount: uint256) -> bool:
    assert self.balances[msg.sender] >= amount
    # 高风险点：此时 balances[msg.sender] 仍为旧值
    raw_call(msg.sender, b"", value=amount)  # 触发 fallback
    self.balances[msg.sender] -= amount      # 状态后改
    return True

# 攻击合约的 receive 函数
@external
def __default__():
    # 重入检测：此时 balances[attacker] 未扣减
    if self.target.balance >= amount:
        self.target.withdraw(amount)  # 再次调用
```

### 3. **工具与人工审计的协同策略**

**使用静态分析工具的陷阱：**
- 工具检测 `raw_call` 且无 `@nonreentrant` → 不一定有漏洞（需验证状态顺序）
- 误报率高达 40%~60%（取决于工具与链的版本差异）
- **必须人工确认**：调用链路、状态依赖关系、访问控制

**高效的人工审计流程：**
1. 快速过滤：搜索所有资产流出函数（withdraw/claim/swap/burn）
2. 状态检查：对每个函数绘制状态修改时间线
3. 保护机制验证：检查装饰器、互斥量、访问控制
4. 攻击可行性模拟：想象恶意 fallback 的调用序列
5. 边界测试：测试合约地址与 EOA 地址的行为差异

### 4. **版本与环境特定的风险**

**Vyper 版本差异：**
- v0.2.x：`raw_call` 默认 `reentrant=True`，高风险
- v0.3.0~0.3.3：添加 `@nonreentrant` 但仍需显式使用
- v0.3.4+：引入更严格的默认行为，建议使用 `reentrant=False`

**链特定因素：**
- Ethereum L1：EVM 标准重入，需重点防护
- Arbitrum/Optimism：某些操作原子性保证不同
- zkSync/Starknet：不同虚拟机，重入模型可能变化

### 5. **审计检查清单**

- [ ] 所有 `raw_call` 是否有 `reentrant=False` 或 `@nonreentrant` 保护
- [ ] CEI 模式是否严格遵循（状态 → 交互）
- [ ] 外部调用目标是否信任或验证
- [ ] 是否存在条件分支导致的部分状态更新遗漏
- [ ] 重入后的二次调用是否能绕过访问控制（如 `msg.sender` 检查）
- [ ] 整数溢出与重入的联合利用风险
- [ ] 是否使用 pull over push 模式（用户自己提取 vs 合约推送）
