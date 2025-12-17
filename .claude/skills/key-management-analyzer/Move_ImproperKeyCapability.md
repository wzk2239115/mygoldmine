**Move**  
常出现在账户密钥管理、能力（capability）绑定、资源访问控制等逻辑中，包括但不限于通过公开函数暴露密钥句柄、在结构体中不加保护地存储密钥引用、错误地将密钥作为可复制资源处理等方式：  
- 不当密钥 Capability：密钥相关的 Capability 对象设计不当，可被复制或非授权获取

## Details

**典型代码模式：**
```move
// 危险：Capability 具有 copy 能力
struct AdminCap has key, store, copy {
    owner: address
}

// 危险：公开函数返回 Capability 引用
public fun get_admin_cap(addr: address): &AdminCap acquires AdminCap {
    borrow_global<AdminCap>(addr)
}

// 危险：Capability 存储在可公开访问的资源中
struct Vault has key {
    cap: SignerCapability  // 未封装保护
}
```

**快速定位核心操作（L2: 跳读）：**
- 搜索 `struct` 定义，检查 Capability 类型（名称含 `Cap`/`Capability`/`Auth`/`Signer`）的 abilities 声明
- 定位 `has copy` 组合：密钥类 Capability 不应具备 `copy` 能力
- 扫描 `public fun` 返回值类型为 Capability 引用（`&Cap` / `&mut Cap`）或直接返回值
- 检查 `move_to` / `move_from` 操作中 Capability 的流转逻辑

**快速定位保护机制（L3: 逐行读）：**
- 验证 Capability 是否仅具有 `key` 或 `key + store` abilities（无 `copy` / `drop`）
- 检查函数可见性：`public` 函数是否暴露敏感引用，是否限定 `public(friend)` 或 `entry`
- 追踪 `signer` 参数验证：操作 Capability 的函数是否验证 `signer::address_of(&account) == expected_owner`
- 确认嵌套封装：Capability 是否封装在带访问控制的 wrapper 资源中
- 检查 `acquires` 声明与 `borrow_global` 配对，确认访问路径受控

## Classify

**漏洞确认：**
- Capability 具有 `copy` 能力，可被任意复制传播
- 公开函数无访问控制直接返回可变引用 `&mut Cap`，允许外部修改或移动
- Capability 存储在无保护的共享资源（如 Table/Vector）中，可被枚举遍历
- `move_from` 操作未验证调用者身份，任意地址可提取他人 Capability

**误报排除：**
- Capability 具有 `store` 用于模块间传递，但接收方已实施严格访问控制
- 返回不可变引用 `&Cap` 仅用于只读查询（需确认引用不可用于后续攻击）
- 测试模块（`#[test]` / `#[test_only]`）中的宽松权限设计

**代码异味：**
- Capability 设计过于复杂，嵌套多层间接访问但无明确安全边界
- 同一模块中多种 Capability 混用，权限粒度不清晰

## Audit Professional Techniques

**真实漏洞特征（高置信度）：**
1. **Copy Ability 组合漏洞**：Capability 声明含 `copy` 时，立即标记为真漏洞。即使框架理论上限制传递，实际 Move 编译器允许任意复制，无例外。案例：Aptos 早期框架漏洞中 `AdminCapability` 被声明为 `copy`，导致所有副本等权，无法撤销。
2. **公开无限制返回**：`public fun get_cap()` 直接返回 `&mut Cap` 或 `Cap` 值，调用者可修改甚至销毁。与 `public(friend)` 对比：后者已有模块边界保护，风险等级差 5 倍。
3. **动态存储结构泄露**：Capability 存储在 `Vector<Cap>` 或 `Table<K, Cap>` 中且无 accessor 检查，外部可循环遍历提取。此模式比单 `move_to` 资源更危险，因涉及多条访问路径。

**误报常见陷阱（需排除）：**
1. **`store` 能力假阳性**：Capability 具有 `store` 能力时，易误判为复制风险。实际区别：`store` 仅允许嵌入其他资源，不允许复制。正确审计需检查 `copy` 能力的具体声明，而非仅看 `store`。案例区分：
   ```move
   // 真漏洞：copy 能力
   struct Cap has key, copy { }

   // 误报：store 仅用于资源组合，无 copy
   struct Cap has key, store { }
   ```
2. **测试代码混淆**：`#[test_only]` 模块中的宽松权限（如 `public` 函数返回 Capability）不应计入生产审计。需确认编译器配置确实排除测试代码进入主网字节码。
3. **单向引用只读查询**：返回不可变引用 `&Cap` 用于查询字段时，需深度验证引用不被转换为可变引用或作为参数传入不可信函数。大多数情况为安全，但需确认整个调用链的只读性。

**现场审计检查清单：**
- **Step 1：快速扫描** - 用 `grep -n "has.*copy"` 定位所有 `copy` 声明，优先审计含 Capability/Cap/Auth 的结构体
- **Step 2：可见性分析** - 统计 `public fun`/`public(friend)`/`entry` 的函数数量与风险权重，public 返回 Capability 直接升级为 P1 漏洞
- **Step 3：权限验证链路** - 追踪操作 Capability 的函数是否都含 `signer` 参数验证，任何一个公开函数跳过验证即为漏洞
- **Step 4：跨模块流转** - 检查 Capability 在 `friend` 模块间流转时的约束条件，friend 关系未验证时应按 public 处理
- **Step 5：销毁路径确认** - 追踪 Capability 全生命周期，确认存在显式销毁逻辑或设计保证无法二次使用

**真实与误报的区分经验：**
- Capability 漏洞必须满足"可达性 + 可利用性"条件。仅有权限接口泄露但有访问控制层时为中风险；权限接口泄露且访问控制缺失时为高风险。
- 时间锁、多签或撤销机制存在时，单次泄露的实际危害降级，但应确认机制本身无 bypass 漏洞。
- Resource Account + SignerCapability 组合中，若初始化后立即 `move_from` 销毁外部访问路径，则为正确实现，非漏洞。关键在于"销毁时机"—— 必须在所有公开调用前完成。

**误报避免的三个关键问题：**
1. 这个 Capability 被复制后，第二个副本是否等权？（no = 可能误报）
2. 这个 Capability 是否经过至少一层访问控制？（yes = 需深度验证控制逻辑是否完整）
3. 这个 Capability 被盗取后，攻击者能立即执行什么操作？（无立即操作 = 低风险）

**实战审计案例对比：**

**案例 1：真漏洞 - Aptos Framework 早期 SignerCapability**
```move
// 危险：公开函数直接返回 SignerCapability 的可变引用
public fun create_signer_with_cap(account_address: address): (signer, SignerCapability) acquires SignerCapability {
    let cap = move_from<SignerCapability>(account_address);
    (create_signer_with_capability(&cap), cap)  // cap 可被多方持有
}
```
**判断标准**：
- 漏洞证据：`SignerCapability` 可被多方同时持有，允许并发修改账户状态
- 误报排除：否，此为真漏洞，无例外情况

**案例 2：误报 - 仅具有 store 能力的 Capability**
```move
// 安全：store 仅用于资源嵌入，无 copy 声明
struct MintCap has key, store {
    total: u64
}

// 安全：访问控制完整
public fun get_mint_cap(account: &signer): &MintCap acquires MintCap {
    assert!(signer::address_of(account) == @admin, ERR_NOT_ADMIN);
    borrow_global<MintCap>(@admin)
}
```
**判断标准**：
- 误报排除原因：虽有 `store` 声明，但无 `copy`，且访问控制完整
- 如何区分：仅看 ability 声明而不看 copy 的审计员会误报，需同时检查函数守卫

**案例 3：中等风险 - Resource Account 模式不完整**
```move
// 风险：SignerCapability 未完全销毁外部访问路径
public fun init_resource_account(): SignerCapability {
    let (_, cap) = account::create_resource_account(signer, seed);
    cap  // 返回给调用者，但调用者可能不销毁
}
```
**判断标准**：
- 风险等级：中等（取决于调用方的处理）
- 改进方案：确认所有调用方都在返回后立即销毁 cap，或改为 `entry` 入口限制可见性

**不同审计阶段的重点：**
1. **白盒审计** - 重点追踪 Capability 全生命周期、权限验证链路完整性、销毁逻辑是否存在
2. **灰盒审计** - 检查字节码中是否存在不在源码中的 ability 声明（编译器优化）
3. **黑盒审计** - 通过链上状态变化反推 Capability 是否泄露（如多次 withdraw 成功）

**常见的审计误区：**
- ❌ 误区 1：看到 `public` 函数即判定漏洞，未检查函数本身是否有 signer 验证
- ❌ 误区 2：Capability 存储在 Table 中就认为风险，未检查 key 是否可枚举或需授权
- ❌ 误区 3：`friend` 修饰符视为安全，未验证 friend 模块本身是否已审计
- ✅ 正确做法：综合考虑可达性、可利用性、防护层数、时间锁等多维度因素

## Low risk

- Capability 仅在 `friend` 模块间流转，且 friend 模块均已审计确认安全
- Capability 绑定时间锁或多签验证，单点泄露不直接导致资金损失
- Capability 权限范围极小（如仅控制 UI 展示配置），不涉及资产操作
- 使用 Resource Account 模式，SignerCapability 在初始化后立即销毁外部访问路径
- Capability 失效机制完善（如过期时间戳、可撤销标志位），泄露后影响可控
