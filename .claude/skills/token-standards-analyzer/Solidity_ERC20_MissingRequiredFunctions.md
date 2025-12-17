# Solidity ERC-20: Missing Required Functions

## Details

ERC-20 代币标准要求实现 6 个核心函数：`totalSupply`、`balanceOf`、`transfer`、`allowance`、`approve`、`transferFrom`。任何一个函数的缺失都会导致标准不兼容，影响 DEX、钱包、索引器等生态工具的集成。

**代码示例**

```solidity
// ❌ 缺失核心函数的不完整 ERC-20 实现
pragma solidity ^0.8.0;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

contract IncompleteToken is IERC20 {
    mapping(address => uint256) public balances;
    uint256 public supply = 1000000 * 10 ** 18;

    function totalSupply() public view returns (uint256) {
        return supply;
    }

    function balanceOf(address account) public view returns (uint256) {
        return balances[account];
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        balances[msg.sender] -= amount;
        balances[to] += amount;
        return true;
    }

    // ⚠️ 缺失: allowance() 函数
    // ⚠️ 缺失: approve() 函数
    // ⚠️ 缺失: transferFrom() 函数
}
```

**核心操作定位** (L1: 关键词扫描)
- 搜索关键词：`function totalSupply`, `function balanceOf`, `function transfer`, `function allowance`, `function approve`, `function transferFrom`
- 快速判断：在合约中搜索这 6 个函数的 `public` 或 `external` 声明
- 速查技巧：使用 IDE 的"Go to Definition"快速确认每个函数是否存在，检查返回类型是否为 uint256（前 3 个）或 bool（后 3 个）
- 继承检查：搜索 `is IERC20` 或 `implements IERC20` 确认合约声称实现该标准

**保护机制定位** (L2: 跳读)
- 函数签名验证：逐一检查 6 个函数的完整声明，确认参数列表和返回值类型（参数名可不同）
  - totalSupply(): → uint256 ✓
  - balanceOf(address): → uint256 ✓
  - transfer(address, uint256): → bool ✓
  - allowance(address, address): → uint256 ✓
  - approve(address, uint256): → bool ✓
  - transferFrom(address, address, uint256): → bool ✓
- 可见性检查：所有 6 个函数必须为 public 或 external（internal/private 无法满足标准）
- 继承链检查：如果缺失函数，检查父合约（通过继承树追踪）是否包含该函数实现

## Classify

### 判断为漏洞 (Bug)
1. **标准声明明确**：合约代码或文档声称实现 "ERC-20 标准"（通过 `is IERC20` 或 comments 表示）
2. **核心函数缺失**：使用搜索工具无法找到至少一个以上的核心函数定义（或函数存在但仅含 revert）
3. **功能受损**：缺失的函数是关键业务函数（如缺少 `approve` 导致 DEX 无法授权转账）
4. **生产环境**：合约已部署到主网或测试网，且有其他合约依赖调用这些函数 → **确认漏洞**

### 误报排除 (False Positive)
- 合约完全不声称实现 ERC-20（如文档明确说明是自定义代币合约）
- 缺失的函数在父合约中完整实现（需逐级追踪继承链）
- 函数名相似但签名完全不同：`transfer(address)` vs 标准的 `transfer(address, uint256)`
- 代码有明确的 "// TODO: implement approve" 注释且合约处于开发/测试阶段
- 合约仅作为 Mock/Test 用途，不用于生产

### 代码异味 (Code Smell)
- 函数存在但实现为空：`function approve(address, uint256) public returns (bool) { }`
- 函数存在但无条件 revert：`function approve(...) public { revert("Not implemented"); }`
- 缺失 emit 事件：虽然实现了函数但未发出 `Transfer` 或 `Approval` 事件
- 参数不符合标准：`transfer(address, uint256, bytes)` 超出 ERC-20 定义

## Low risk

以下情况应评为低风险 (Info/Low)：
- **部分实现显式声明**：合约文档或代码注释明确说明 "这是 ERC-20 的最小化实现，仅支持转账，不支持授权" → 无 Bug，仅为文档问题
- **扩展标准实现**：合约实现了所有 6 个核心函数，但额外增加了 `mint()`、`burn()` 等非标准函数 → 扩展，非缺失
- **开发阶段合约**：代码中有明确的 TODO 注释（"// TODO: implement transferFrom"）且合约未部署或仅在私有链 → Low Risk
- **代理合约模式**：核心函数的实现在代理合约中，当前合约仅为接口声明（Proxy Pattern）→ 可能为设计选择
- **多版本支持**：合约同时支持 ERC-20 v1 和 v2，通过不同的函数标识区分 → 需验证标准声明清晰度
