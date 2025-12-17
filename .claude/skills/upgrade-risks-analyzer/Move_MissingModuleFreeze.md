# Move_MissingModuleFreeze

**漏洞类型**: 升级风险 - 缺失模块冻结  
**影响范围**: Move 生态链（Aptos、Sui等）  
**风险等级**: High

## 概述

模块部署后未启用冻结机制，导致核心业务逻辑可在生产环境被任意修改，破坏代码不可变性和链上状态一致性。常见于使用 `code::publish_package_txn` 或自定义升级框架但缺失权限限制的场景。

## Details

**代码示例特征**：
```move
// 危险：模块发布后无冻结保护
module deployer::vault {
    use aptos_framework::account;
    
    // 缺少 #[view] 或冻结验证的公开入口
    public entry fun upgrade_module(admin: &signer, code: vector<u8>) {
        // 直接允许代码更新，无冻结检查
        code::publish_package_txn(admin, code, vector::empty());
    }
}

// 缺少以下冻结标志：
// - 未调用 aptos_framework::code::freeze_code_object()
// - 未在 Move.toml 中设置 freeze_on_publish = true
// - ResourceAccount 未撤销 SignerCapability
```

**快速定位核心操作** (L2:跳读)：  
扫描模块入口函数，关注 `code::publish_package_txn`、`package::publish`、`signer::address_of` 配合资源修改的模式。检查是否存在动态代码加载或模块替换逻辑，特别是带 `public entry` 标记的管理函数。

**快速定位保护机制** (L3:逐行读)：  
- 搜索 `code::freeze_code_object` 或 `SignerCapability` 销毁调用
- 检查 `Move.toml` 配置项 `freeze_on_publish` 或 `immutable`
- 验证 ResourceAccount 创建后是否保留了 signer 权限
- 追踪管理员权限 `AdminCap` 或 `UpgradeCap` 资源的生命周期
- 确认是否有 `assert!(code::is_frozen(...))` 防护检查

## Classify

**归类为漏洞**：
- 主合约/金库/代币模块可通过接口动态替换，且无时间锁或多签限制
- ResourceAccount 保留 SignerCapability 且可被单点控制
- 生产环境存在 `upgrade_module` 类函数但无 DAO 治理

**归类为代码异味**：
- 有冻结调用但在初始化函数外存在备用升级路径
- 多签/时间锁配置但阈值过低（如 1/3）
- 测试网环境保留升级权限但主网计划冻结

**归类为误报**：
- 明确的治理模块通过 Voting 机制管控升级
- 仅 script 函数可更新，核心资源结构已冻结
- 使用链原生升级框架（如 Aptos 的 aptos_framework::code）且配置合理

## Low Risk

以下场景可降级为低风险：
- 升级权限由 2/3 以上多签控制，且签名者公开透明
- 存在 48 小时以上时间锁，允许用户提前迁移资产
- 仅外围辅助模块可升级，核心资产逻辑已通过 `freeze_code_object` 锁定
- 升级需链上治理投票，且参与率/通过率阈值合理（>30% 参与，>60% 同意）
- 代码托管在链上已验证的不可变 ObjectAddress

## 审计专业技巧

### 1. 深度追踪权限链路

**技巧**: 不仅检查直接的 `freeze_code_object` 调用，更要追踪权限来源的完整链路。
- 验证 `AdminCap` 或 `UpgradeCap` 的创建、销毁、转移全过程
- 检查是否存在权限升级路径：例如低级权限可通过特定函数提升为高级权限
- 在 ResourceAccount 场景下，追踪 `SignerCapability` 是否真的销毁，还是仅被封存在某个资源中

**实战案例**：
```move
// 真实漏洞：权限未真正销毁
public fun init_module(signer: &signer) {
    let cap = create_signer_capability(signer);
    // 问题：cap 被存放在全局资源中，后续可通过 borrow_global_mut 恢复
    move_to(signer, AdminCapStorage { cap });
}
```

### 2. 时间维度分析

**技巧**: 关键是对比 **部署时间** vs **冻结时间**，以及 **升级权限持有时间**。
- 检查从部署到冻结的时间间隔：>1 个月表示存在风险窗口
- 验证 TimeLocker 是否被正确初始化，init 函数中是否无误触发冻结
- 查看历史升级记录，若在权限限制前已执行多次升级，说明权限体系薄弱

**区分标志**：
- 真实漏洞：部署 3 个月后仍未冻结，且持续产生大额交易
- 误报：部署当天即冻结，或者测试网部署但主网已冻结

### 3. 代码替换边界识别

**技巧**: 识别 Move 框架中哪些操作真的会"替换"代码，哪些只是参数变更。
- `code::publish_package_txn` + `code::remove_hash_entry` = 可替换代码
- `code::update_module_sources` 仅更新源码记录，不改变字节码 = 相对安全
- 自定义 `upgrade_code` 若仅修改模块全局变量，并非真实代码替换 = 降级考虑

**检查方法**：
```bash
# 搜索涉及字节码修改的关键词
grep -E "publish_package|remove_hash|code_object" contract.move
# 排除仅涉及元数据的操作
grep -v "source\|metadata\|config" | grep publish
```

### 4. 多签与治理的细节陷阱

**技巧**: 多签不等于安全，需深度验证：
- 验证多签的实现库：是否基于标准的 aptos_framework::multisig 或自定义实现
- 检查签名者身份：若 2/3 签名者为同一团队/交易所，治理权中心化程度高
- 确认投票权重分布：应查看链上治理合约的实际参与者列表，而非文档声称

**真实案例对比**：
```
漏洞场景：合约声称"2/3 多签"，但链上核实发现签名者均为同一地址的衍生账户
误报场景：多签确实分散在 3 个独立团队，且投票历史公开透明，从未被单方面绕过
```

### 5. 初始化函数的隐性风险

**技巧**: `init_module` 往往被遗忘为攻击面，需重点审视其他初始化路径。
- 检查是否存在 `init_module_v2`、`initialize` 等替代初始化函数
- 验证模块初始化后是否允许重复初始化（某些框架允许在特定条件下重新触发）
- 追踪是否通过 `module_event` 或其他异步机制延迟初始化

**代码陷阱示例**：
```move
// 危险：存在备用初始化入口
public entry fun init_module(signer: &signer) {
    // 冻结逻辑...
}

public entry fun emergency_init(admin: &signer) {
    // 未冻结！存在备用升级路径
    setup_admin_cap(admin);
}
```

### 6. 跨模块依赖链分析

**技巧**: 单个模块冻结不代表安全，需检查它依赖的上游模块。
- 若模块 A 冻结，但依赖的库模块 B 可升级，则 B 的更新会影响 A 的行为
- 检查是否存在 "bridge 模块" 用于权限中继或调用转发
- 在多个合约部署的场景，验证它们之间的调用链是否形成环路

**判别方法**：
```move
// 追踪 use 声明
use library::upgradeable_module;  // 风险！
use framework::frozen_module;     // 安全

// 检查权限来源
if (upgradeable_module::can_upgrade()) {  // 需要沿链追踪
    // ...
}
```

### 7. 测试网与主网的不一致性检查

**技巧**: 项目在测试网激进但在主网保守的行为暗示治理体系的双重标准。
- 对比测试网与主网的 freeze 配置、升级权限、多签成员
- 检查主网是否真的部署了更安全的版本，而非仅更改了文档
- 追踪版本号与部署时间：若主网版本低于测试网，可能存在部署延迟或审计修复

**识别误报信号**：
- 若主网明确冻结，测试网保留升级权限 = 正常的开发流程，非漏洞
- 若两者配置完全相同且都未冻结 = 红旗信号，可能忽视了主网安全
