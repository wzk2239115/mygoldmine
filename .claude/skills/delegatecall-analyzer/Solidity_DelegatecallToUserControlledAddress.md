# Solidity - Delegatecall 调用用户可控地址

**漏洞类型**：Delegatecall to User-Controlled Address  
**风险等级**：Critical  
**常见场景**：可升级合约、中心化逻辑路由器、插件化治理模块、UUPS 代理升级、自定义 fallback 转发器、权限委托执行器

---

## Details

**代码示例**：
```solidity
contract VulnerableProxy {
    address public implementation;
    
    // 漏洞：用户输入的地址直接用于 delegatecall
    function execute(address target, bytes calldata data) external {
        (bool success,) = target.delegatecall(data);
        require(success);
    }
    
    // 漏洞：未验证的状态变量用于 delegatecall
    function setImplementation(address _impl) external {
        implementation = _impl;
    }
    
    fallback() external payable {
        address impl = implementation;
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }
}
```

**快速定位核心操作（L1: 关键词扫描）**：
- 全局搜索 `delegatecall(` 关键字
- 检查 `assembly` 块中的 `delegatecall` 指令
- 关注 `fallback()` 和 `receive()` 函数中的转发逻辑
- 搜索 `Proxy`、`Router`、`Dispatcher` 等命名模式
- 扫描 UUPS 模式中的 `upgradeTo` 相关函数

**快速定位保护机制（L3: 逐行读）**：
- **访问控制**：检查 delegatecall 前是否有 `onlyOwner`、`onlyAdmin` 等修饰符
- **白名单验证**：目标地址是否通过 `mapping(address => bool) public allowedImplementations` 验证
- **不可变地址**：delegatecall 目标是否为 `immutable` 或仅在构造函数中设置的常量
- **代理模式完整性**：在 UUPS/Transparent 代理中，检查 `_authorizeUpgrade` 是否正确实现
- **时间锁保护**：升级操作是否经过 timelock 延迟
- **事件日志**：关键操作是否有 `emit ImplementationUpgraded` 等审计日志
- **重入保护**：delegatecall 前后是否有 `nonReentrant` 或状态锁

---

## Classify

**确认为漏洞的条件**：
1. delegatecall 目标地址来自外部输入（函数参数、msg.data 解析）且无白名单验证
2. delegatecall 目标地址来自可被非特权用户修改的状态变量
3. 合约持有资产（ETH、ERC20）或具有特权操作能力，攻击者可通过注入恶意逻辑完全控制合约

**误报情况**：
1. delegatecall 目标地址为硬编码常量或 immutable 变量
2. 目标地址修改需要多签批准 + 时间锁，且多签成员为可信第三方
3. 合约为纯计算工具，不持有资产且无特权操作（但需额外检查调用者上下文）

**代码异味（需进一步审查）**：
1. delegatecall 有访问控制但权限过于中心化（单一 owner）
2. 白名单机制存在但白名单添加过程不透明
3. 虽有保护但逻辑复杂，可能存在绕过路径（如通过其他函数间接修改目标地址）
4. 代理合约与实现合约的存储布局不一致可能导致存储碰撞

---

## Low risk

**降级为低风险的场景**：
1. **有限权限上下文**：delegatecall 目标虽可控，但合约本身无资产、无特权操作，仅用于纯计算或视图函数聚合
2. **多重防御机制**：同时满足以下条件
   - 多签 + 时间锁保护（≥3/5 多签，≥48h timelock）
   - 链上治理投票机制（需社区共识）
   - 紧急暂停开关由独立监控方控制
3. **临时测试环境**：合约标注为测试版本，且明确声明风险，未在生产环境使用
4. **沙箱隔离**：delegatecall 在独立的子合约中执行，父合约通过 `staticcall` 或只读方式与其交互，无法影响主合约状态
5. **资产量微小**：合约锁定资产价值低于预警阈值（需结合项目规模判断），且有每日提现上限

**注意**：即使降级为低风险，仍需在审计报告中详细说明潜在风险和中心化假设，建议客户在文档中向用户披露该设计决策。
