# Vyper 无限制代理升级

代理合约的升级函数未对调用者身份进行验证，允许任意用户替换逻辑合约地址，导致合约控制权完全丧失。

## Details

**代码示例**

```vyper
# 漏洞示例：缺少权限控制的升级函数
implementation: public(address)

@external
def upgrade(new_implementation: address):
    # ❌ 缺少 msg.sender 权限验证
    self.implementation = new_implementation
    log ImplementationUpgraded(new_implementation)

@external
def _delegate_call():
    raw_call(self.implementation, msg.data, is_delegate_call=True)
```

```vyper
# 安全示例：带权限控制的升级函数
owner: public(address)
implementation: public(address)

@external
def upgrade(new_implementation: address):
    # ✓ 验证调用者权限
    assert msg.sender == self.owner, "Only owner"
    assert new_implementation != empty(address), "Invalid address"
    self.implementation = new_implementation
    log ImplementationUpgraded(new_implementation)
```

**快速定位核心操作（L2-L3）**

- **L1 关键词扫描**：搜索 `implementation`、`upgrade`、`set_implementation`、`delegate_call`、`raw_call` 等关键函数名
- **L2 跳读**：直接跳转到包含地址赋值或状态变更的升级类函数，检查函数签名和首行逻辑
- **L3 逐行读**：确认升级函数内是否存在状态变量的写操作（`self.implementation = ...`）

**快速定位保护机制（L2-L3）**

- **L1 关键词扫描**：在升级函数开头查找 `assert msg.sender`、`self.owner`、`onlyOwner`、`has_role` 等权限校验关键词
- **L2 跳读**：检查函数修饰器或首行是否存在 `assert` 或 `require` 语句，验证是否针对 `msg.sender`
- **L3 逐行读**：确认权限检查逻辑完整性，验证 `owner`/`admin` 的初始化和变更流程是否安全
- **L4 跨模块追踪**：若使用外部权限合约（如 AccessControl），需跟踪角色分配和撤销逻辑

## Classify

**漏洞判定标准**

- ✅ **高危漏洞**：升级函数完全没有 `msg.sender` 验证，或验证逻辑可被绕过（如条件永真、owner 未初始化为零地址）
- ⚠️ **代码异味**：存在权限验证但实现不规范（如硬编码地址、多重签名未生效、时间锁缺失）
- ❌ **误报情况**：
  - 升级函数本身是内部函数（`@internal`）且仅被权限控制的外部函数调用
  - 代理合约采用不可变 implementation（初始化后无升级函数）
  - 已通过构造函数或初始化函数禁用升级能力（implementation 设为空地址且无修改函数）

**关键研判点**

1. 权限验证的**存在性**：是否有 `assert msg.sender == ...` 类似逻辑
2. 权限验证的**有效性**：owner/admin 地址是否正确初始化且不可随意篡改
3. 升级函数的**可达性**：是否存在其他入口绕过权限检查执行升级

## 审计专业技巧与真实漏洞识别

### 一、动态权限验证检测技巧

**真实漏洞场景**

```vyper
# 场景1: Owner 地址从未初始化
owner: public(address)  # 默认值为 empty(address)

@external
def upgrade(new_implementation: address):
    assert msg.sender == self.owner  # 永远失败，函数不可用
    # 实际导致升级无法执行（但如果有 fallback 逻辑可能触发）
    self.implementation = new_implementation

# 场景2: Owner 可被任意用户修改
owner: public(address)

@external
def set_owner(new_owner: address):
    # ❌ 无权限检查，允许任意用户设置 owner
    self.owner = new_owner

@external
def upgrade(new_implementation: address):
    assert msg.sender == self.owner
    self.implementation = new_implementation
```

**审计技巧**：
- 追踪 `owner`/`admin` 状态变量的所有赋值点，确认初始化位置（constructor vs 内联赋值）
- 检查是否存在修改权限角色的函数，若有则递归验证这些函数本身的权限
- 对外部权限合约（AccessControl、Ownable 等）的导入和初始化做深入审计

### 二、真实漏洞 vs 误报的区分经验

**示例1：条件检查与实际权限**

```vyper
# 误报：看似缺乏权限，实际通过修饰符保护
# (Vyper 不支持修饰符，此为演示思路)

# 真实漏洞示例
owner: public(address)
implementation: public(address)

@external
def upgrade(new_implementation: address):
    # 检查点：看是否有任何权限验证语句
    if msg.sender == self.owner:
        self.implementation = new_implementation
    # ❌ 实际上缺少 else 中的 revert，允许任意调用者执行 if-false 分支

# 安全修复
@external
def upgrade(new_implementation: address):
    assert msg.sender == self.owner, "Unauthorized"
    self.implementation = new_implementation
```

**区分技巧**：
- **误报案例**：使用了 `if` 但缺少 `else` 处理 → 需检查 if-true/if-false 两个分支的完整逻辑
- **真实漏洞**：完全缺少任何条件判断 → 直接标记为高危

**示例2：代理合约的多种升级机制**

```vyper
# 误报：代理采用 immutable implementation（无升级功能）
IMPLEMENTATION: immutable(address)

def __init__(impl: address):
    IMPLEMENTATION = impl
    # 初始化后 IMPLEMENTATION 无法修改，升级函数根本不存在

# 真实漏洞：虽然有 immutable，但另有升级入口
IMPLEMENTATION: immutable(address)
backup_impl: public(address)  # ❌ 这才是真正的升级入口

@external
def switch_to_backup():
    # 无权限检查，允许任意升级至备份实现
    raw_call(self.backup_impl, msg.data, is_delegate_call=True)
```

**区分技巧**：
- 扫描合约中所有涉及地址存储和修改的操作，不要被 `immutable` 迷惑
- 追踪所有调用 `raw_call` 和 `delegatecall` 的地址来源

### 三、上下文驱动的漏洞评估

**业务逻辑审计**

```vyper
# 示例：仅影响非关键合约的升级权限缺失
# 上下文决定风险等级

# 场景 A：高风险（代理控制资金）
@external
def upgrade(new_implementation: address):
    # 该代理管理 ERC20 token 或用户存款
    self.implementation = new_implementation
# → 应标记为 Critical，即使缺少简单的 owner 检查

# 场景 B：低风险（代理仅控制辅助功能）
@external
def upgrade(new_implementation: address):
    # 该代理仅管理 logging、oracle 等非资金关键逻辑
    self.implementation = new_implementation
# → 可标记为 Medium/Low，由项目方自行评估
```

**审计技巧**：
- 分析代理实现合约的 storage layout 和关键函数
- 识别代理管理的资产规模和业务影响面
- 结合链上监控、多签保护、时间锁等外层防护评估最终风险

## Low risk

以下场景可评为低风险或非漏洞：

1. **测试合约**：合约明确标注为测试用途（文件名含 `test`/`mock`），或在测试网部署且不涉及真实资产
2. **多重安全层**：虽然单个升级函数权限简单，但外层有时间锁、多签钱包或 DAO 治理控制实际升级权限
3. **有限影响面**：该代理合约仅管理非关键业务逻辑，即使被恶意升级也不影响资金安全（需结合业务上下文判断）
4. **紧急熔断**：存在独立的全局暂停机制，可在发现异常升级后立即冻结合约
5. **监控响应**：项目方有完善的链上监控和事件响应机制，能在恶意升级生效前介入（需在报告中说明风险窗口）

⚠️ 注意：即使存在以上情况，仍应在报告中明确指出权限缺失的事实，由项目方和用户自行评估风险接受度
