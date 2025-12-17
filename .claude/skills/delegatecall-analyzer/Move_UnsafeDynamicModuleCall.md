**Move**  
不安全的动态模块调用 (Unsafe Dynamic Module Call)

常出现在能力委托、模块组合复用或动态资源操作场景中，通过动态分发调用外部模块但未验证模块身份，导致恶意模块在调用者上下文中执行，造成权限提升或资源操纵。

## Details

**代码示例特征：**
```move
// 典型漏洞模式
public fun delegate_call<T>(module_addr: address, func_name: vector<u8>) {
    let module_id = borrow_module(module_addr);  // 动态获取模块
    module_id::dispatch(func_name);  // 直接调用无验证
    // 或使用 vector<u8> 作为函数签名动态分发
}
```

**快速定位核心操作（审计等级：L2）：**
- 关键字：`borrow_module`, `dispatch`, `call_function`, `module_id`, `dynamic_call`
- 查找模式：函数参数包含 `address` + `vector<u8>`（模块地址+函数名）组合
- 重点关注：`move_to`, `move_from`, `borrow_global_mut` 等资源操作出现在动态调用链路中
- 扫描函数签名：参数中出现 `&signer` 与 `address` 同时传递给下层调用

**快速定位保护机制（审计等级：L3-L4）：**
- 白名单检查：`assert!(vector::contains(&ALLOWED_MODULES, &module_addr))`
- 能力约束：`acquires` 声明显式限制，模块间 `friend` 声明
- 签名者验证：`assert!(signer::address_of(&caller) == @admin)`
- 类型约束：泛型参数 `<T: key + store>` 限制资源类型范围
- 追踪流程：需跨模块追踪 `module_addr` 来源，判断是否为用户可控输入

## Classify

**漏洞判定标准：**
- 模块地址由外部输入决定（函数参数/用户提交）且无白名单验证
- 调用上下文包含特权能力（Capability）或签名者权限（&signer）
- 可访问/修改调用者模块的全局资源（global storage）

**误报排除条件：**
- 模块地址硬编码或从受信任的注册表（registry）获取
- 动态调用仅限 `friend` 声明的模块间互操作
- 调用函数仅执行 `view` 操作（无状态变更）

**代码异味信号：**
- 使用字符串拼接构造模块路径
- 缺少 `acquires` 声明但访问全局资源
- 动态调用函数返回泛型数据但未做类型校验

## Low risk

**以下场景可降级为低风险：**
- 动态调用限定在同一包（package）内的模块，且包部署需多重签名
- 仅调用 `public` 标记的纯函数（无资源读写），不传递 `&signer`
- 调用目标模块经过链上治理投票白名单审核
- 存在调用深度限制（depth check）防止递归滥用
- 调用前对模块字节码哈希进行验证（module hash check）
- 业务场景仅为只读查询聚合，无价值转移或权限变更逻辑

## 审计专业技巧

### 真实漏洞的关键线索

**1. 权限链路追踪**
- 检查调用者身份是否被正确验证：被调函数能否在调用者模块上下文中访问其私有资源？
- 追踪 `&signer` 传递链路：如果 `signer` 直接传给动态调用的外部模块，威胁度+2
- 验证权限边界：动态调用是否能突破 `acquires` 边界访问应被隔离的资源？
- **实例**：Aptos某DEX中，validator 通过 `delegation` 调用用户提供的模块地址，未验证模块身份，导致恶意模块可盗取用户资产

**2. 资源转移的隐藏链路**
- 重点关注 `move_from<T>` 和 `move_to<T>` 出现在泛型约束松散的动态调用中
- 追踪全局资源的所有权变更：谁能发起转移？转移目标可控吗？
- 检查 `borrow_global_mut<T>` 是否存在状态前后不一致（TOCTOU风险）
- **误报案例**：函数使用 `vector<T>` 并在动态调用中传递，但 `T` 的泛型上界为 `key + drop`，资源无法被盗取

**3. 递归与状态爆炸检测**
- 扫描动态调用中是否包含向量迭代：`for (item in items)`，如果迭代长度由用户控制，易导致栈溢出
- 检查嵌套动态调用深度：A调B，B再调C，C的调用目标也由外部输入决定，形成反射危险
- 追踪借用生命周期：动态调用返回的引用是否被缓存在全局状态，导致悬垂指针风险？
- **实例**：某链上AMM合约允许通过 `delegatecall` 执行任意模块，用户可构造递归调用耗尽合约gas上限

### 常见误报的排除方法

**1. "动态调用"的名义欺骗**
- 看似动态但实际上是 `match` 分支：将多个模块地址硬编码在 `if-else` 中，虽然逻辑分发是动态的，但调用目标固定
  ```move
  // 不是真正的动态调用——只是分发逻辑动态
  if (module_type == TYPE_A) { module_a::process() }
  else { module_b::process() }
  ```
- 使用常量枚举而非用户输入：`const ALLOWED: vector<u8> = vector[x"01", x"02"]`，参数仅选择索引，无法指定任意地址

**2. 白名单验证的隐蔽实现**
- 白名单可能在上游函数中验证，向下传递的已是安全集合
  ```move
  // 上游验证
  fun public_entry(addr: address) {
      assert!(is_whitelisted(addr), ERROR);
      internal_delegate(addr);  // 此时 addr 已被验证
  }
  ```
- 使用映射表而非直接参数：`table::borrow(&REGISTRY, module_addr)` 确保地址必须存在于受控表中
- 检查 `friend` 声明是否有效限制了调用者身份

**3. 资源访问的完全隔离**
- 虽然调用目标动态，但资源类型被泛型上界硬锁定：`<T: key>` 不足，但 `<T: key + store>` 且 `T` 来自模块常量可能是安全的
- 检查 `acquires` 声明是否精确列出所有可访问资源，若列表不包含全局变量则外部调用无法访问
- 动态调用被沙箱隔离在子事务中（某些链的特性），失败不回溯主事务

### 审计检查清单

| 项目 | 真实漏洞特征 | 排除误报方法 |
|------|----------|----------|
| **模块地址来源** | 直接函数参数、外部存储查询 | 硬编码、常量表、治理白名单 |
| **签名者传递** | `&signer` 直接转发给动态调用 | 仅验证后使用，或完全不传递 |
| **资源修改权限** | 动态调用可写入任意 `move_to<T>` | `T` 类型由调用者模块定义且受限 |
| **调用深度** | 存在自指或交叉递归可能性 | 硬编码最大深度限制或无递归设计 |
| **返回值校验** | 动态调用返回泛型数据无类型检查 | 返回值立即转换为固定类型或无返回 |

### 实战案例分析

**案例1：真实漏洞（Curve漏洞变种）**
```move
// 高风险：任意模块地址 + signer + 资源修改
public fun swap<CoinIn, CoinOut>(
    user: &signer,
    pool_module: address,  // 用户控制
    amount_in: u64
) {
    let coin = coin::withdraw<CoinIn>(user, amount_in);  // 从用户账户取币
    let result = call_module(pool_module, b"swap", coin);  // 调用任意模块
    // 恶意模块可在此处转向用户资产到攻击者地址
}
```

**案例2：误报排除**
```move
// 低风险：虽然地址动态，但白名单 + view 操作
public fun query_pool_info(pool_addr: address): u64 {
    assert!(table::contains(&REGISTERED_POOLS, &pool_addr), ERR_NOT_REGISTERED);
    let pool = table::borrow(&REGISTERED_POOLS, pool_addr);
    pool::get_tvl(pool)  // 仅查询，无状态变更
}
```
