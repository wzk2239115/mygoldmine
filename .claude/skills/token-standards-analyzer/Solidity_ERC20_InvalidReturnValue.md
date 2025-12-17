# Solidity ERC-20: Invalid Return Value

## Details

### Code Examples

**问题代码示例 1：transfer 返回 void**
```solidity
function transfer(address to, uint256 amount) public {
    balances[msg.sender] -= amount;
    balances[to] += amount;
    // ❌ 缺失返回 bool 值
}
```

**问题代码示例 2：approve 返回 uint256**
```solidity
function approve(address spender, uint256 amount) public returns (uint256) {
    allowances[msg.sender][spender] = amount;
    return amount;  // ❌ 应返回 bool，不是 uint256
}
```

**问题代码示例 3：transferFrom 返回错误类型**
```solidity
function transferFrom(address from, address to, uint256 amount) public returns (uint256) {
    // ❌ 应返回 bool，不是 uint256
    return allowances[from][msg.sender];
}
```

### 核心操作定位技巧
- **L1: 关键词扫描** - 搜索 `function transfer`, `function approve`, `function transferFrom` 三个函数定义
- 检查每个函数的 `returns` 声明，确认返回类型必须是 `(bool)`
- 验证函数体内必须包含显式 `return true;` 或 `return false;` 语句

### 保护机制定位技巧
- **L2: 跳读** - 扫描 ERC-20 接口定义和实现，查看是否有类型转换或包装器处理返回值
- 检查是否在调用 transfer/approve 时对返回值进行了类型强制转换
- **L3: 逐行读** - 对比标准 ERC-20 接口定义，逐行验证返回类型是否严格为 `bool`

### 审计专业技巧

#### 工作流程
1. **接口检查** - 先查看合约是否继承 IERC20 或声明了接口规范，记录预期的返回类型
2. **多点扫描** - 对 transfer、transferFrom、approve、mint、burn 等关键函数分别审计，不依赖于自动工具
3. **路径覆盖** - 在函数体中标记所有条件分支（if/else、try/catch），确保每条路径都有 return 语句
4. **上下文关联** - 查看调用处是否使用了返回值（如 `require(token.transfer(...))`），这暗示返回值必须为 bool

#### 误报识别技巧
- **非标准实现标记** - 注意合约注释中是否声明"非标准 ERC-20"、"自定义 token"，这类合约可能有意改变返回类型
- **包装器合约辨别** - 如果看到代理模式或委托调用，需要追踪目标合约的实现，而非仅检查当前合约壳层
- **类型隐式转换** - 某些 Solidity 编译器版本允许 `return;` 在 `returns (bool)` 中隐式返回 false，不一定是漏洞
- **测试用例交叉验证** - 检查测试文件中是否有对返回值的断言测试，能帮助判断返回值是否被期望使用

#### 难以区分的场景处理
- **Proxy 合约** - 当合约使用 delegatecall 或 ERC-1967 代理模式时，需要检查实现合约而非代理壳
- **多继承链** - 继承多个基类时，需要追踪所有 transfer 实现，确认是否有覆写导致类型不匹配
- **编译器指令影响** - 检查 pragma solidity 版本和 ABIEncoderV2 配置，某些版本对返回值的默认处理不同

---

## Classify

### 漏洞判定标准 (Bug)
- `transfer()` 函数未返回 bool，或返回类型不是 bool
- `approve()` 函数返回类型不是 bool（如返回 uint256、address 等）
- `transferFrom()` 函数返回类型不是 bool
- 函数虽然声明返回 bool，但函数体中某些分支缺少 return 语句，导致返回默认值

### 误报排除标准 (False Positive)
- 内部辅助函数（如 `_transfer`）可以有不同的返回类型，只要公开接口符合标准
- 继承自正确的 ERC-20 基合约且未覆写这些函数的实现
- 函数在接口中声明为 `returns (bool)`，实现中也返回了 bool 值

### 代码异味 (Code Smell)
- transfer/approve 函数实现过于简单，没有错误检查（如检查余额足够、零地址校验）
- 返回值总是 `true`，从不返回 `false`，表明异常处理逻辑缺失
- 缺少对零地址的验证，即使返回类型正确也表明实现不完整

### 真实漏洞案例

#### 案例 1：返回类型完全错误
```solidity
// 真实漏洞：transfer 返回 uint256 而不是 bool
function transfer(address to, uint256 amount) public returns (uint256) {
    require(balances[msg.sender] >= amount, "insufficient balance");
    balances[msg.sender] -= amount;
    balances[to] += amount;
    emit Transfer(msg.sender, to, amount);
    return balances[to];  // ❌ 返回 uint256，违反 ERC-20 标准
}
```
**后果**：调用此函数时 `require(token.transfer(to, 100))` 会失败，因为期望 bool 但收到 uint256，造成交互层级兼容性问题。

#### 案例 2：分支返回不一致
```solidity
// 真实漏洞：某些分支缺少 return
function transferFrom(address from, address to, uint256 amount) public returns (bool) {
    if (allowances[from][msg.sender] < amount) {
        // ❌ 这个分支没有 return 语句，会返回默认的 false
        require(false);
    }
    balances[from] -= amount;
    balances[to] += amount;
    allowances[from][msg.sender] -= amount;
    return true;
}
```
**后果**：revert 语句会中止执行，但如果用 assert 替代 require，某些路径会隐式返回 false。

### 常见误报模式

#### 误报 1：继承自 OpenZeppelin 基类
```solidity
// 这不是漏洞，只是继承实现
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MyToken is ERC20 {
    constructor() ERC20("My Token", "MTK") {}
    // transfer、approve 等函数由 ERC20 基类提供，已正确实现
}
```
**识别方法**：检查父类实现是否正确，如果继承自可信库且未覆写，则无需报告。

#### 误报 2：内部辅助函数与公开接口分离
```solidity
// 正确的做法：公开接口返回 bool，内部函数可以不同
function _safeTransfer(address to, uint256 amount) internal returns (uint256) {
    // 内部辅助函数，返回实际转账金额，这不是漏洞
    return amount;
}

function transfer(address to, uint256 amount) public returns (bool) {
    // 公开接口遵守 ERC-20 标准
    _safeTransfer(to, amount);
    return true;
}
```
**识别方法**：区分公开函数 (public/external) 和内部函数 (internal/private)，只检查前者。

#### 误报 3：明确的非标准声明
```solidity
// @notice This is a non-standard ERC-20 implementation for internal use only
// @dev Custom return values are intentional and documented
contract CustomToken {
    function transfer(address to, uint256 amount) public returns (string memory) {
        // 合约明确声明了非标准实现
        balances[msg.sender] -= amount;
        balances[to] += amount;
        return "transferred";
    }
}
```
**识别方法**：查看合约注释、README、文档中是否明确标注为非标准实现，合约名称是否暗示非标准（如 "CustomToken"、"PrivateToken"）

---

## Low Risk

### 应评为低风险的情况
- 合约是代理合约或包装合约，通过接口委托调用到标准 ERC-20 实现，且目标合约正确实现了返回值
- transfer/approve 虽然缺少返回值，但合约内部方法都通过 require 或 assert 进行了异常处理，不依赖返回值来判断操作成功
- 合约明确标注为非标准 ERC-20 实现（如私有代币、内部使用 token），且返回值处理与业务逻辑一致

### 风险评估微调指南

#### 低风险升级判定
以下情况虽然初看像漏洞，但在实际审计中应降低风险等级：
- **完整的 try/catch 或 require 包装** - 如果合约在所有调用处都使用 `require(token.transfer(to, amt), "failed")`，即使返回值不符合标准也能保证交互安全
- **合约为内部使用，无外部集成** - 私有池、内部治理 token，如果不与 DeFi 协议交互，返回值不一致的风险降低 50%
- **完全不存在调用者检查返回值** - 搜索合约全文，确认没有任何地方进行 `if (result)` 或 `require(result)` 的检查，则返回值的错误影响有限

#### 高风险降级的反面
- **看似有保护但未实际使用** - 如果有 `returns (bool)` 声明但实现未返回 bool，这仍是真实漏洞，不能因为"没人调用"就降级
- **假设编译器会修复** - 不能依赖 Solidity 编译器的隐式行为修复返回值问题，必须显式实现
- **依赖链下验证** - 不能假设交互方会通过链下方式验证，ERC-20 标准存在就是为了建立链上约定
