# Move 密钥资源误用 (Key Resource Misuse)

**漏洞概述**  
密钥作为资源存储但未正确限制访问或转移权限，常见于账户密钥管理、能力（capability）绑定、资源访问控制等逻辑中。包括公开函数暴露密钥句柄、结构体中不加保护地存储密钥引用、错误地将密钥作为可复制资源处理等场景。

## Details

**典型代码特征：**
```move
module admin::key_manager {
    struct AdminKey has key, store { power: u64 }  // ❌ 添加 store 能力
    
    public fun get_admin_key(account: &signer): AdminKey {  // ❌ 直接返回密钥资源
        move_from<AdminKey>(signer::address_of(account))
    }
    
    struct KeyHolder has key {
        admin_key: AdminKey,  // ❌ 未封装在 capability 内
        ref: &AdminKey        // ❌ 裸露的引用存储
    }
}
```

**快速定位核心操作技巧（L2：跳读）：**
- 扫描 `struct` 定义中带 `has key` 且名称含 `Key/Cap/Auth/Admin` 的资源
- 检索 `public fun` 返回类型为密钥资源或其引用的函数
- 查找 `move_from`、`move_to`、`borrow_global` 等资源操作的调用点
- 关注 `transfer::transfer` 或 `transfer::public_transfer` 的参数类型

**快速定位保护机制技巧（L3：逐行读）：**
- 验证密钥资源是否缺少 `store` 能力（正确：`has key`，错误：`has key, store`）
- 检查函数可见性：密钥操作应为 `entry`、`friend` 或私有，避免 `public`
- 确认是否使用 Capability 模式封装（如 `struct AdminCap has key { id: UID }`）
- 追踪 `acquires` 声明，验证资源借用是否限制在模块内部
- 检查 `assert!` 权限检查是否在密钥操作前执行（如 `assert!(signer::address_of(account) == @admin, ENOT_AUTHORIZED)`）

## Classify

**漏洞判定标准：**
- 密钥资源具有 `store` 能力且可通过 `transfer` 系函数任意转移 → **高危漏洞**
- 公开函数直接返回密钥资源或可变引用（`&mut`） → **高危漏洞**
- 密钥资源存储在其他可公开访问的结构体字段中 → **中危漏洞**

**误报识别：**
- 密钥作为 `entry fun` 参数但立即销毁或转移给验证过的地址 → **安全模式**
- 使用 `friend` 模块配合明确的权限检查链 → **需评估 friend 范围**
- Object 模型中密钥通过 `transfer::freeze_object` 冻结 → **Sui 特定安全模式**

**代码异味：**
- 密钥验证逻辑分散在多个函数，缺乏统一入口 → **重构建议**
- 测试代码中存在 `public fun` 暴露密钥但生产环境已移除 → **清理建议**

## Low risk

**以下场景可评为低风险：**
- 密钥仅用于链下签名验证，不控制链上资产转移（如消息签名）
- 密钥作用域限制在单用户资源内，无跨账户影响（如个人配置密钥）
- 系统设计允许多方持有相同权限密钥且无资产损失风险（如公共读取权限）
- 密钥生命周期短暂，在单笔交易内创建并销毁（如临时授权 token）
- 测试网或沙箱环境专用密钥，且代码已清晰标注环境限制

## Audit Professional Tips（审计专业技巧）

### 关键特征识别

**密钥资源的四层检查法：**
1. **声明层**：扫描 `struct` 关键字，捕获能力组合（`has key, store` 是红旗）
2. **访问层**：追踪函数可见性，从 `public fun` 开始倒推调用链
3. **操作层**：定位 `move_from`、`borrow_global_mut` 等变更操作的上下文
4. **传输层**：检查 `transfer::transfer` 的参数是否为密钥资源

**代码扫描命令示例（便于批量审计）：**
```bash
# 查找所有带 store 能力的密钥资源
grep -n "has key, store" Move.lock && grep -n "has key, store" sources/**/*.move

# 定位公开密钥返回函数
grep -n "public fun.*Key\|public fun.*Cap" sources/**/*.move

# 追踪 transfer 操作涉及密钥的调用
grep -n "transfer::transfer\|public_transfer" sources/**/*.move
```

### 真实漏洞案例 vs 误报区分

**案例1：Key-Value 存储访问控制**

```move
// 🔴 真实漏洞：权限验证缺失
public fun update_key(account: &signer, new_value: u64) {
    let account_addr = signer::address_of(account);
    let key = borrow_global_mut<AdminKey>(account_addr);  // ❌ 任何地址都能访问
    key.value = new_value;
}

// 🟢 误报排除：存在权限验证
public fun update_key(account: &signer, new_value: u64) acquires AdminKey {
    let account_addr = signer::address_of(account);
    assert!(account_addr == @admin, ENOT_AUTHORIZED);  // ✓ 权限检查
    let key = borrow_global_mut<AdminKey>(account_addr);
    key.value = new_value;
}
```

**案例2：Capability 模式识别**

```move
// 🟢 安全模式：使用 Capability 封装（无 store 能力）
struct AdminCap has key { id: UID }

public fun verify_admin(cap: &AdminCap): bool {
    // 密钥通过引用传递，无法被转移
    true
}

// 🔴 高危：Capability 泄露了 store 能力
struct AdminCap has key, store, copy, drop { id: UID }  // ❌ 可复制可转移
```

**案例3：资源生命周期分析**

```move
// 🟢 安全：密钥在函数内创建和销毁
entry fun temporary_operation(account: &signer) {
    let temp_key = AdminKey { power: 100 };
    perform_action(&temp_key);
    // 函数结束自动销毁，无法外泄
}

// 🔴 漏洞：密钥存储到全局状态
entry fun store_key(account: &signer) {
    let key = AdminKey { power: 100 };
    move_to(account, key);  // ❌ 持久化存储风险
}
```

### 审计决策树

**逐步判定流程：**

1. **密钥资源定义检查**
   - 问题1：是否包含 `store` 能力？ → **高危信号**
   - 问题2：是否包含 `copy` 或 `drop` 能力？ → **极高危**

2. **函数可见性检查**
   - 问题3：是否存在返回密钥资源的 `public fun`？ → **高危**
   - 问题4：函数是否为 `entry` 且带权限检查？ → **继续评估**

3. **权限验证检查**
   - 问题5：密钥操作前是否执行 `assert!` 检查？ → **继续评估**
   - 问题6：验证逻辑是否依赖 `signer::address_of()` 而非可伪造参数？ → **安全指标**

4. **资源作用域检查**
   - 问题7：密钥是否只在模块内使用（`acquires` 仅在 `self` 上使用）？ → **安全**
   - 问题8：是否通过 Capability 或 Event 向外暴露权限？ → **评估信任链**

### 常见误报陷阱

**误报1：friend 模块的权限分析失误**
```move
public(friend) fun admin_operation(key: AdminKey) {
    // ❌ 易误判为低风险，但实际风险取决于 friend 列表规模
    // ✓ 正确做法：验证 friend 模块数量（≤3 个为安全），检查 friend 代码质量
}
```

**误报2：Generic 类型的权限继承判断**
```move
struct Vault<Key> has key {
    key: Key,  // ❌ 如果 Key 有 store，整个 Vault 也有泄露风险
}
// 正确做法：追踪 Vault<AdminKey> 的具体实例化，不能只看泛型定义
```

**误报3：Event 日志的权限含义过度解读**
```move
public fun operation(key: AdminKey) {
    emit(KeyUsedEvent { user: tx_context::sender() });
    // ❌ 不要将 Event 作为访问控制的替代品
}
```

### 审计效率技巧

**优先级排序（按风险和审计成本）：**
- **P0**：`public fun` 直接返回 `has key, store` 资源（1分钟判定）
- **P1**：`borrow_global_mut` 外加缺失权限检查（5分钟追踪）
- **P2**：Capability 模式下的 friend 模块权限链（10-15分钟评估）
- **P3**：Generic 参数传递链导致的隐式权限泄露（20分钟分析）

**批量审计检查清单：**
- [ ] 所有密钥资源 是否缺少 `store` 能力
- [ ] 所有密钥返回的 `public fun` 是否存在
- [ ] 所有 `borrow_global_mut` 操作是否带 `assert!` 权限检查
- [ ] 是否使用了 `acquires` 且范围合理
- [ ] 测试文件中是否存在泄露的权限函数未在生产代码中移除
