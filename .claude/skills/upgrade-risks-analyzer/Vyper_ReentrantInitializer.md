# Vyper - 可重入初始化器 (Reentrant Initializer)

**漏洞概述**  
在基于代理的可升级合约中，初始化函数未设置重入保护，攻击者可在初始化过程中通过外部调用重入，导致状态覆盖、权限篡改或多次初始化。

---

## Details

**代码示例（存在漏洞）：**

```vyper
# 代理合约的逻辑实现
owner: public(address)
initialized: public(bool)
token: ERC20  # 外部合约引用

@external
def initialize(_owner: address, _token: address):
    assert not self.initialized, "Already initialized"
    self.owner = _owner
    self.token = ERC20(_token)  # 外部调用，可能触发重入
    self.initialized = True
    # 如果 _token 是恶意合约，在上面的调用中可重入 initialize
```

**快速定位核心操作（L2-L3）：**
- **关注点**：`initialize`、`__init__`、`setup` 等初始化函数名
- **扫描模式**：搜索包含状态变量赋值（如 `self.owner =`）的外部可调用函数
- **跳读技巧**：定位 `@external` 装饰器后，检查函数内是否有：外部合约调用（`ERC20()`、`.transfer()`）、委托调用、`send()` 等
- **审计等级**：L2（跳读函数签名和外部交互）→ L3（逐行检查状态变量赋值顺序）

**快速定位保护机制（L1-L2）：**
- **关键词扫描（L1）**：
  - `@nonreentrant` 装饰器（Vyper 原生支持）
  - `initialized` 或 `_initialized` 标志位在首行检查
  - `initializer` modifier 引用（如果引入 OpenZeppelin 风格）
- **保护模式识别（L2）**：
  - **检查-生效-交互模式**（CEI）：`assert not initialized` → `self.initialized = True`（标志位设置）→ 外部调用
  - **锁机制**：是否在函数开头设置 `self.lock = True`，结尾恢复
- **审计等级**：L1（关键词扫描 `@nonreentrant`）→ L2（跳读检查标志位设置时机）

---

## Classify

**漏洞判定标准：**
1. **确认漏洞**：初始化函数中，标志位设置在外部调用之后，且无 `@nonreentrant` 保护 → 高危重入漏洞
2. **误报情况**：
   - 标志位在首行立即设置：`self.initialized = True`（第一条语句），后续外部调用无法重入
   - 已使用 `@nonreentrant` 装饰器
   - 初始化函数仅内部调用（`@internal`），且调用链无外部交互
3. **代码异味**：
   - 标志位设置位置靠后但外部调用为纯查询（`view`/`pure` 函数）→ 理论风险但难以利用
   - 使用自定义锁但实现不规范（如忘记在异常分支恢复锁状态）

**关键判定点：**  
- 外部调用发生时，`initialized` 标志是否已为 `True`
- 是否存在可控的外部合约地址参数

---

## Low Risk

**低风险评级场景：**

1. **受限外部调用**：
   - 外部调用对象为硬编码的可信合约（如官方 USDT 合约地址）
   - 仅调用标准 ERC20 的 `view` 函数（如 `balanceOf`、`decimals`）

2. **部分状态隔离**：
   - 重入仅能覆盖非关键状态（如统计变量），无法影响权限或资产

3. **初始化函数访问受限**：
   - 初始化函数通过工厂合约的原子调用完成，且工厂合约逻辑安全
   - 区块链平台级别的原子初始化保证（如通过 `create2` + constructor 模式）

4. **经济成本约束**：
   - 初始化需质押大量资产且不可取回，攻击成本远高于收益

**注意**：即使评为低风险，仍建议添加 `@nonreentrant` 作为纵深防御。
