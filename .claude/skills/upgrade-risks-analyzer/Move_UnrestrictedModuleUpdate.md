# Move_UnrestrictedModuleUpdate

**漏洞类型：** 无限制的模块更新  
**语言：** Move  
**风险等级：** Critical/High

## Details

### 代码特征

**存在风险的代码模式：**

```move
module publisher::upgrade_module {
    use std::signer;
    
    // 危险：任何人都可以调用更新模块
    public fun upgrade(account: &signer, new_code: vector<u8>) {
        let addr = signer::address_of(account);
        // 直接发布新代码，无权限检查
        move_to(account, ModuleCode { code: new_code });
    }
}
```

```move
module publisher::package_manager {
    // 危险：使用 public entry 但无权限控制
    public entry fun publish_module(
        sender: &signer,
        metadata: vector<u8>,
        code: vector<u8>
    ) {
        // 缺少 assert!(signer::address_of(sender) == @admin, ERR_UNAUTHORIZED)
        package::publish(sender, metadata, code);
    }
}
```

```move
// 危险：module 发布者字段可被修改
module 0x1::governance {
    struct ModuleOwner has key {
        owner: address  // 可变的 owner 且无 immutable 标记
    }
    
    public fun change_owner(new_owner: address) acquires ModuleOwner {
        // 无权限验证即可更换 owner
        borrow_global_mut<ModuleOwner>(@0x1).owner = new_owner;
    }
}
```

### 快速定位核心操作 (L2-L3)

**关键函数与特征：**
- `package::publish()`, `code::publish_package()`, `module::upgrade()`
- `move_to<ModuleMetadata>()` 配合代码载荷参数 `vector<u8>`
- `public entry` 或 `public` 函数接受 `code/bytecode/metadata` 参数
- `signer` 参数但无 `assert!` 权限校验
- init 函数中赋予的 `AdminCap` / `UpgradeCap` 能力资源

**审计路径 (L2: 跳读扫描)：**
1. 搜索 `publish` / `upgrade` / `update_module` 关键词
2. 检查函数签名：是否为 `public entry` 且接受 `vector<u8>` 代码参数
3. 向函数体内跳读：寻找 `signer::address_of` 后是否紧跟 `assert!` 校验

**审计路径 (L3: 逐行审查)：**
- 追踪 `signer` 参数的地址提取：`let addr = signer::address_of(account);`
- 验证是否存在：`assert!(addr == @admin, ERR_UNAUTHORIZED);`
- 检查硬编码地址常量：`const ADMIN: address = @0x...;`
- 确认条件分支：`if (addr != DEPLOYER) { abort ERR_PERMISSION }`

### 快速定位保护机制 (L1-L4)

**保护机制关键词 (L1: 关键词扫描)：**
- `assert!` 配合 `signer::address_of` / `==` / `!=`
- `has key` 的权限资源：`AdminCap`, `UpgradeCap`, `PublisherCap`
- `exists<AdminCap>(addr)` 校验能力存在性
- `borrow_global<UpgradePolicy>()` 检查策略状态
- `freeze()` / `make_immutable()` / `package::freeze_code_object()`

**防护模式识别 (L2-L3: 跳读+逐行)：**

```move
// 模式1: 能力资源门控
struct UpgradeCap has key, store {}

public entry fun upgrade(cap: &UpgradeCap, code: vector<u8>) {
    // cap 作为参数即为权限证明
}
```

```move
// 模式2: 显式地址校验
const DEPLOYER: address = @0xCAFE;

public fun publish(sender: &signer, code: vector<u8>) {
    assert!(signer::address_of(sender) == DEPLOYER, ERR_UNAUTHORIZED);
}
```

```move
// 模式3: 策略资源检查
struct UpgradePolicy has key {
    frozen: bool,
    allowed_publishers: vector<address>
}

public fun try_upgrade(sender: &signer) acquires UpgradePolicy {
    let policy = borrow_global<UpgradePolicy>(@publisher);
    assert!(!policy.frozen, ERR_FROZEN);
    assert!(vector::contains(&policy.allowed_publishers, &signer::address_of(sender)), ERR_NOT_IN_WHITELIST);
}
```

**跨模块追踪 (L4: 依赖分析)：**
- 检查 `init_module()` 中 `UpgradeCap` 的初始分配：`move_to(sender, UpgradeCap{})`
- 追踪 Cap 转移函数：`public fun transfer_cap(cap: UpgradeCap, to: address)`
- 确认 Cap 销毁点：`public fun revoke_cap(cap: UpgradeCap) { let UpgradeCap{} = cap; }`
- 分析依赖模块：`use aptos_framework::code` 的策略配置

## Classify

**漏洞判定标准：**
- `public`/`public entry` 升级函数 + 无权限验证 → **Critical 漏洞**
- 权限检查可被绕过（如 Cap 可被任意铸造）→ **High 漏洞**
- 升级函数存在但未暴露接口（仅限 `fun` 非 `public`）→ **Low 风险或误报**

**误报场景识别：**
- 测试模块中的升级函数（路径包含 `tests/` 或标注 `#[test_only]`）
- 升级函数仅在 `init_module` 或部署脚本中调用一次后立即 freeze
- 使用硬件签名设备或多签方案管控的升级（需结合文档确认）
- 升级函数已被废弃但未删除（检查是否有 `abort ERR_DEPRECATED`）

**代码异味边界：**
- 权限检查逻辑复杂但最终有效 → 代码异味（建议简化但非漏洞）
- 存在 `friend` 声明的升级函数 → 需追踪 friend 模块的调用链
- 权限通过事件日志检查而非链上断言 → 设计缺陷（事件可伪造）

## Low risk

**可接受的低风险场景：**

1. **时间锁保护：** 升级需先提交 proposal，经过 `timestamp::now_seconds()` 验证的时间窗口期后才可执行
2. **治理投票前置：** 升级调用需传入已通过 DAO 投票的 `ProposalId`，合约内验证投票结果
3. **分级权限：** 升级者仅能更新特定非核心模块（通过白名单模块地址限制）
4. **紧急熔断后的升级：** 合约已进入 paused 状态，升级用于修复而非常规操作
5. **审计豁免场景：** 测试网/开发网部署、私有链场景、已明确声明为可升级的实验性协议

**降级条件：**
- 升级频率受链上参数严格限制（如 `min_upgrade_interval = 30 days`）
- 升级代码哈希需提前公示并由多个独立验证者签名确认
- 存在回滚机制可恢复到前一版本（保留历史代码哈希）
- 升级权限由 multisig 控制且签名阈值 >= 3/5
