# Move_CapabilityDelegationWithoutScopeCheck

**漏洞类型**：无作用域检查的 Capability 委托  
**风险等级**：High  
**常见场景**：权限管理模块、跨模块资源操作、动态能力委托系统

## Details

**典型代码模式**：
```move
// 高风险：直接传递 Capability 给外部模块
public fun delegate_admin(cap: &AdminCapability, target: address) {
    external_module::execute(cap);  // 无作用域限制
}

// 高风险：存储 Capability 引用但未限制调用方
struct DelegatedCap has key {
    cap: AdminCapability  // 全权委托，无时间/操作限制
}
```

**快速定位核心操作**（L3-L4）：  
- 搜索 `public fun` + `&.*Capability` 组合，关注参数传递路径
- 追踪 `move_to<>()` 存储的 Capability 类型结构体，检查字段是否包含裸 Capability
- 识别跨模块调用链：`external_module::*` 且参数含 Capability 引用
- 检查 `borrow_global<Capability>()` 后的使用是否即时回收

**快速定位保护机制**（L2-L3）：  
- 查找时间戳/高度限制字段：`expiry: u64`、`valid_until: u64`
- 查找操作范围限制：`allowed_ops: vector<u8>`、`scope: address`
- 查找调用者验证：`assert!(signer::address_of(&caller) == authorized, E_UNAUTHORIZED)`
- 查找一次性标记：`used: bool` 或 `nonce: u64` 配合 `assert!(!cap.used)`
- 查找 Witness Pattern：能力创建需要 Witness 类型作为前置证明

## Classify

**归类为漏洞**：
- Capability 被传递给外部模块且未验证目标模块可信度（缺少白名单或模块签名校验）
- 存储的 Capability 无时间/次数限制，可被无限期/无限次使用
- 委托函数缺少调用者身份验证（`signer` 参数）
- 能力对象可被任意地址的函数借用（`borrow_global` 无访问控制）

**归类为误报**：
- Capability 传递给同模块内私有函数（`fun` 非 `public`）
- 委托时显式限制了操作类型（通过枚举或位掩码）
- 使用临时 Capability 模式（函数内创建并销毁）
- 委托对象通过 `acquires` 语法明确声明资源依赖

**归类为代码异味**：
- Capability 结构体设计过于宽泛（如 `RootCapability` 包含所有权限）
- 缺少能力降级机制（无法从 AdminCap 派生受限 OperatorCap）
- 未使用 Move 的 `copy` / `drop` 能力控制机制

## Low risk

**以下情况可评低风险**：
- 委托目标为可信系统模块（如官方标准库、同项目核心模块）
- Capability 本身权限极小（仅读取公开数据）
- 设计明确为 Escrow 托管模式，且有第三方仲裁机制
- 委托有明确的经济抵押或保险金机制（攻击成本 > 攻击收益）
- 测试网或沙盒环境（明确标记非生产代码）
- 委托链深度为 1 且目标模块已通过形式化验证
- 能力对象受 Move Prover 不变式约束保护

## 审计专业技巧

### 1. 真实漏洞的关键特征

**权限泄露链识别**（最常见误判点）：
- 真实漏洞：Capability 能从公开函数经过 3+ 层调用链传递到不可控地址
  ```move
  public fun level_1(cap: &AdminCap) { level_2(cap); }  // 外部可调
  fun level_2(cap: &AdminCap) { level_3(cap); }         // 内部转发
  fun level_3(cap: &AdminCap) { borrow_global_mut<State>(UNTRUSTED_ADDR).cap = *cap; }
  ```
  审计要点：追踪 `signer` 参数在调用链中是否被检查，若中途丢失则为真实漏洞

- 误报案例：Capability 虽多层转发但最终被存储在 `move_to<State>(signer)` 且 `State` 使用 `signer` 参数，实际上访问控制完整

**时间/次数限制的细致判断**：
- 真实漏洞：检查表单显示有 `expiry: u64` 但实际函数体中被注释掉或被覆盖
  ```move
  public fun execute_delegated(cap: &DelegatedCap) {
      // assert!(now() < cap.expiry);  // 被注释的验证！
      perform_critical_operation(cap);
  }
  ```
  审计技巧：必须检查所有声明的限制是否在所有代码路径中被执行，使用 CTRL+F 搜索字段名但未被读取的场景

- 误报案例：Capability 结构体声明了 `expiry` 但不需要检查，因为它是只读的演示用数据而非实际权限凭证

**调用者验证的隐蔽失败**：
- 真实漏洞：使用 `tx_context::sender()` 而非 `signer` 参数（在某些 Move 框架中 sender 可被欺骗）
  ```move
  public fun delegate_to(cap: &AdminCap, target: address) {
      let caller = tx_context::sender(&mut ctx);  // 可能是攻击者伪造
      assert!(caller == ADMIN, E_UNAUTHORIZED);
  }
  ```
  审计技巧：优先级排序为 `signer` 参数 > 权限检查宏 > 合约内 sender() 调用

- 误报案例：虽然没有显式 `signer` 参数但使用了 Move 的 `requires module_address == @module_addr` 属性检查

### 2. 误报陷阱与绕避

**跨模块接口的隐蔽限制**：
- 审计要点：不要仅看被审计模块的代码，必须跨模块追踪
  ```move
  // module A (被审计)
  public fun delegate(cap: &AdminCap) {
      module_b::accept_delegation(cap);  // 看起来无限制
  }

  // module B (隐蔽限制在这里)
  public fun accept_delegation(cap: &AdminCapability) {
      assert!(signer::address_of(signer) == AUTHORIZED_MODULE_ADDRESS, E_UNAUTHORIZED);
  }
  ```
  实际应用：永远要求对跨模块调用的被调用端进行同步审计

**Witness Pattern 的识别**：
- 真实安全：
  ```move
  public fun create_delegated_cap<W: drop>(
      _witness: W,  // 需要特定类型作为通行证
      cap: &AdminCap
  ): DelegatedCap { ... }
  ```
  只有掌握 W 类型定义的模块才能创建委托

- 常见误报：视 `<T: copy>` 为无效安全保护（实际上如果 T 的创建受限则仍有效）

**存储位置与可见性的组合判断**：
- 漏洞标准：存储在 `0x00...00` 等全局地址的 Capability
- 安全设计：存储在用户地址下（`move_to<State>(signer)`)，读取需要同地址的 signer 验证
- 审计技巧：搜索所有 `move_to<>()` 和 `borrow_global<>()` 的地址参数来源

### 3. 常见漏洞与正常设计的区分

| 现象 | 真实漏洞标志 | 可能安全标志 | 审计行动 |
|------|-------------|-----------|---------|
| 存储 Capability | 地址参数是常量（如 `POOL`) | 地址参数是 `signer` | 追踪地址来源 |
| 多层函数转发 | 中途 `signer` 参数被删除 | 每层都有 `signer` 或权限检查 | 逐层验证权限传递 |
| 枚举权限委托 | 枚举值被完全忽略执行 | 枚举在关键分支被读取/匹配 | 确认枚举在所有路径被用 |
| 时间限制字段 | 字段声明但从不被读取 | 字段在关键操作前被断言 | 搜索字段名的全部 occurrence |
| 委托给外部模块 | 无白名单/签名验证 | 外部模块是核心库或形式化验证过 | 查看被委托模块的源码 |

### 4. 实战审计清单

**第一轮快速筛查（5分钟）**：
- [ ] 搜索所有 `public fun` 含 Capability 参数的函数
- [ ] 标记这些函数中是否有 `signer` 参数（无则可能风险）
- [ ] 检查是否有 `move_to<>()` 存储 Capability 到非 signer 地址
- [ ] 统计委托链深度（超过 3 层则复杂度高）

**第二轮深度分析（20分钟）**：
- [ ] 对每个高风险函数，绘制完整的权限检查树（包括被调用函数的权限检查）
- [ ] 验证时间/次数限制字段是否在所有代码路径中被检查（使用代码覆盖工具）
- [ ] 检查是否存在特权提升路径（低权限输入如何导致高权限操作）
- [ ] 查验外部模块调用是否有版本/签名验证机制

**第三轮误报排除（10分钟）**：
- [ ] 确认所有权限检查是否被实际执行（未被注释、未在 unreachable 分支）
- [ ] 验证 Witness Pattern 的 W 类型定义和使用限制
- [ ] 检查是否使用了 Move Prover 约束（通过查看 `.spec` 文件）
- [ ] 查证外部模块的源码确认其安全性

### 5. 常见审计错误

**错误1：过度依赖函数名**
- 错：看到 `check_permission()` 就认为已验证权限
- 对：必须读取 `check_permission()` 的具体实现，确认它真的校验了 signer

**错误2：忽视全局状态污染**
- 错：Capability 存储在 `move_to<State>(owner)` 就认为安全
- 对：还要检查 `State` 结构体本身是否能被其他方式修改或替换

**错误3：链路追踪不彻底**
- 错：仅审计被标记为高风险的函数
- 对：追踪所有可能调用到该函数的路径，包括来自其他模块的调用

**错误4：版本/环境差异忽视**
- 错：在审计旧代码时不关注 Move VM 版本变化（权限模型可能变化）
- 对：查证代码编写时的 Move 版本和官方安全建议
