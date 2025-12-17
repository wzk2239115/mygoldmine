# Solidity - 可升级代理销毁

**漏洞类型**：代理合约或逻辑合约在升级流程中被 `selfdestruct` 销毁，导致代理失效、资金锁定或系统不可用

## Details

**代码示例特征**：
```solidity
// 危险模式1：逻辑合约中的自毁函数
contract LogicV1 {
    function cleanup() external onlyOwner {
        selfdestruct(payable(owner));  // 销毁后代理 delegatecall 失败
    }
}

// 危险模式2：代理合约自身可被销毁
contract Proxy {
    function destroy() external {
        require(msg.sender == admin);
        selfdestruct(payable(admin));  // 销毁代理导致永久资金锁定
    }
}

// 危险模式3：升级时未检查目标合约状态
function upgradeTo(address newImpl) external {
    implementation = newImpl;  // 未验证 newImpl 是否已被 selfdestruct
}
```

**快速定位核心操作**（L3-逐行读）：
- 定位代理合约：搜索 `delegatecall`、`Proxy`、`Upgradeable` 模式
- 检查逻辑合约：在实现合约中搜索 `selfdestruct` 关键字
- 追踪升级函数：`upgradeTo`、`setImplementation`、`upgradeToAndCall` 等函数逻辑
- 验证初始化锁：逻辑合约是否包含 `initialize` 函数且防重入保护
- 审查销毁权限：谁可以调用含 `selfdestruct` 的函数（owner/任意用户/逻辑漏洞）

**快速定位保护机制**（L4-跨模块追踪）：
- 代理不可毁检查：代理合约是否完全禁止 `selfdestruct` 操作
- 逻辑合约防护：实现合约是否继承保护基类（如 OpenZeppelin 的 `Initializable`）且禁用 `selfdestruct`
- 升级前置校验：`upgradeTo` 是否通过 `extcodesize` 检查目标合约存在性
- 时间锁+多签：升级操作是否受 `TimelockController` 和多签钱包双重保护
- 紧急暂停机制：是否存在 `pause` 函数阻止升级期间的异常操作
- 存储槽冲突检测：使用 EIP-1967 标准存储槽，避免升级时状态覆盖
- 跨合约依赖：追踪调用代理的外部合约，评估销毁影响范围

## Classify

**漏洞等级研判**：
- **严重**：代理合约自身可被销毁且持有用户资金、逻辑合约被毁后代理无降级方案、升级时未检查目标合约有效性导致指向空地址
- **中危**：仅 owner 可销毁逻辑合约但未通知代理更新、存在销毁函数但需多步操作触发、销毁时资金可转移但依赖方失效
- **低危**：有完善的升级前校验和回滚机制、销毁仅影响已废弃的旧版本合约、存在备用代理可自动切换
- **误报**：逻辑合约明确标记为测试版本且仅限测试网、代理架构使用不可变代理（无 `selfdestruct` 代码路径）、已通过形式化验证证明代理不可毁
- **代码异味**：逻辑合约继承了可销毁的基类但实际未使用、升级文档不完善、缺少销毁影响评估测试用例

## Audit Professional Techniques

**真实漏洞特征识别**（区分低风险）：
1. **代理合约的绝对禁忌**：检查代理合约字节码中是否包含 `0xff` 操作码（selfdestruct），使用 `hevm inspect` 或 Certora 形式化验证
2. **逻辑合约初始化漏洞**：逻辑合约未使用 `Initializable` 或自定义初始化锁，允许任意人在部署后直接调用（如 Poly Network 漏洞）
3. **升级路径攻击**：追踪升级函数中 `delegatecall` 的目标地址来源，检查是否可被 TOCTOU（Time-of-Check-Time-of-Use）攻击
4. **存储污染验证**：对比新旧实现合约的存储布局，确保升级不会导致状态覆盖（使用 `Storage Layout Report` 自动扫描）
5. **权限提升路径**：检查升级权限是否可通过 delegatecall 被逻辑合约修改，导致权限侧滑

**审计工具链与脚本**：
```bash
# 1. 检测 selfdestruct 操作码
cast disassemble <ADDRESS> | grep -i "ff"

# 2. 验证 EIP-1967 存储槽
cast storage <PROXY_ADDRESS> 0x360894a13ba1a3210667c828492db98dca3e2848cc3735a19ccfb141b95c713e

# 3. 自动追踪代理调用链（需配置 Etherscan API）
cast call <PROXY> 0x5c60da1b --rpc-url <RPC> | cast --from-bin
```

**误报常见案例**（错误拦截的合理代码）：
- **开发工具类合约**：测试网部署的 `DebugHelper.sol` 包含 `selfdestruct` 但仅在 Goerli 网络激活，主网 ABI 不包含该函数入口
- **过期版本残留**：GitHub 历史提交中存在 `cleanup()` 但已在 v2.0 版本删除，当前部署合约不含该代码
- **虚假警告信号**：检测到 `delegatecall` 就判定为代理，实际是事件路由中间件（EventRouter），不涉及逻辑合约替换
- **存储槽冲突误判**：不同合约使用相同变量名，但实际采用 EIP-1967 标准槽位隔离，不存在污染风险

## Real World Vulnerability Case Study

**真实案例1：Poly Network（2021）跨链漏洞**
```
受影响合约：EthCrossChainManager.sol
漏洞根因：逻辑合约未使用初始化锁，部署后即可被任意人 delegatecall 调用
        攻击者通过 putCurEpochStartHeight() 修改业权所有者，进而调用 selfdestruct 销毁代理
审计要点：即使代理本身不可毁，逻辑合约被毁后 delegatecall 返回空数据导致静默失败
修复方案：强制逻辑合约继承 Initializable，在构造函数锁死初始化
```

**真实案例2：Nomad Bridge（2022）跨链漏洞**
```
受影响合约：UpgradeBeacon.sol
漏洞根因：升级函数缺失权限检查，任意人可将实现指向 0x0 地址或已销毁合约
        后续 delegatecall 被路由至空地址导致调用无效但交易成功（隐性漏洞）
审计要点：使用 EVM 指令级跟踪验证 delegatecall 目标的有效性
修复方案：强制 require(newImpl.code.length > 0)，添加事件监控，实施多签审批
```

## Low risk

**以下情况可评为低风险**：
1. 代理合约采用透明代理或 UUPS 模式且遵循 OpenZeppelin 标准实现，底层代码禁止 `selfdestruct`
2. 逻辑合约通过构造函数 `_disableInitializers()` 锁死初始化，且代码审计确认无 `selfdestruct` 指令
3. 升级函数强制执行 `require(newImpl.code.length > 0)` 校验，防止指向已销毁合约
4. 采用多签+48小时时间锁+链上治理三重审批，升级前需社区公示并完成代码审计
5. 存在代理注册表（ProxyRegistry）统一管理，销毁旧合约前自动迁移所有依赖方至新代理
6. 已部署不可变备用代理（ImmutableProxy），当主代理失效时用户可通过备用入口提取资金
7. 实现紧急提款功能（EmergencyWithdraw），即使代理失效用户也可直接从存储合约取回资产
8. 仅销毁测试合约或已公告废弃的旧版本，主网生产合约已迁移至新架构
9. 通过 Certora 或 Mythril 形式化验证证明代理合约所有代码路径都不执行 selfdestruct 指令
10. 存储合约与逻辑合约完全分离（Proxy 不存储用户资金），即使代理失效资金也不受影响

## Advanced Audit Checklist

**部署前代码审计检查清单**：
- [ ] 验证代理合约字节码中不存在 `0xff` 操作码（使用 `cast disassemble` 逐行检查）
- [ ] 确认所有升级函数在修改 implementation 前执行 `require(newImpl.code.length > 0)` 检查
- [ ] 审计逻辑合约是否继承 `Initializable` 且在构造函数调用 `_disableInitializers()`
- [ ] 跨对比新旧实现合约的存储布局，使用 Slither 的 `storage-layout` 插件自动检测冲突
- [ ] 检查升级权限是否集中在单个地址或受多签+时间锁保护
- [ ] 验证代理 fallback 函数是否正确处理无匹配函数的调用（不应 revert）
- [ ] 评估销毁旧逻辑合约对已有交易的影响，确认不存在待确认交易依赖旧实现
- [ ] 审计紧急提款或资金恢复机制的有效性，测试在代理失效后的可执行性

**部署后监控与应急**：
- [ ] 部署 ProxyBeacon 监听事件，监控所有 `ImplementationUpgrade` 事件异常
- [ ] 配置告警规则：升级函数被调用时立即通知多签管理员进行验证
- [ ] 准备回滚脚本：能在 15 分钟内恢复到上一个稳定版本的逻辑合约
- [ ] 维护降级清单：记录每次升级前的旧实现地址，以便紧急回滚

**误报排除流程**：
1. 检查合约是否为测试网部署，跨验证 Mainnet/Testnet 部署地址差异
2. 通过 GitHub 版本历史确认 selfdestruct 是否已在最新发布版本中移除
3. 使用 Etherscan 对比部署的字节码与源代码编译结果（检查是否一致）
4. 分析 delegatecall 上下文：确认不是动态路由（Event Router）而是真实代理模式
5. 若存储冲突告警，验证合约是否遵循 EIP-1967 标准槽位（0x360894a13ba...）

## Key Risk Differentiators

**致命漏洞 vs 低风险的关键差别**：

| 维度 | 致命漏洞 | 低风险 |
|------|--------|--------|
| **代理可毁** | 代理字节码包含 selfdestruct 指令 | 代理字节码明确禁用 selfdestruct，通过形式化验证 |
| **初始化保护** | 逻辑合约无初始化锁或 initialize 可重入 | 使用 OpenZeppelin Initializable + _disableInitializers |
| **升级检查** | 升级前无任何校验，可指向 0x0 或任意地址 | 强制 require(newImpl.code.length > 0) + 事件日志 |
| **权限模型** | 单签升级，owner 可被合约修改 | 多签 + 时间锁 + 无法通过 delegatecall 篡改 |
| **回滚机制** | 不存在历史版本记录或无法恢复 | 保留至少 3 个历史版本，具备自动降级方案 |
| **资金隔离** | 代理同时存储资金和逻辑 | 资金在独立存储合约，代理仅转发调用 |

**真实审计发现示例**：
- **CRIT-001**：Timelock 权限在升级前被 delegatecall 提升，导致任意人可修改 implementation（Compound Governor 漏洞模式）
- **HIGH-002**：逻辑合约构造函数缺失 `_disableInitializers()`，允许攻击者部署后主动调用 initialize 修改状态
- **MEDIUM-003**：存在备用代理但无自动切换机制，主代理失效时用户需手动迁移（社工风险）
- **INFO-004**：升级事件日志不完整，缺少 oldImplementation 字段，无法追踪升级历史（可审计性问题）
