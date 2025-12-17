# Move_ImproperResourceAccess - 不当资源访问

**漏洞定义**：资源读写逻辑未正确限制访问范围，允许未授权模块或账户访问私有资源状态，违反 Move 资源封装原则。

## Details

**对应代码示例**：
```move
module owner::vault {
    struct Vault has key {
        balance: u64,
        owner: address
    }
    
    // 危险：直接暴露 borrow_global，未验证调用者身份
    public fun get_balance(addr: address): u64 acquires Vault {
        borrow_global<Vault>(addr).balance
    }
    
    // 危险：可从外部直接修改任意账户的 Vault
    public fun withdraw(addr: address, amount: u64) acquires Vault {
        let vault = borrow_global_mut<Vault>(addr);
        vault.balance = vault.balance - amount;
    }
}
```

**快速定位核心操作的技巧（L2：跳读）**：
- 扫描所有 `public` 函数签名，重点关注带有 `acquires` 关键字的函数
- 查找 `borrow_global<T>` / `borrow_global_mut<T>` / `move_from<T>` / `move_to<T>` 等资源操作原语
- 识别接受 `address` 或 `&signer` 参数的函数，评估资源访问目标是否可控
- 检查 `public entry` 函数是否直接操作全局资源

**快速定位保护机制的技巧（L3：逐行读）**：
- 确认资源操作前是否验证 `signer::address_of(&caller) == target_address`
- 检查是否使用 Capability 模式（如 `AdminCap has store, key`）限制函数调用者
- 验证 `assert!(condition, ERROR_CODE)` 是否覆盖所有敏感路径
- 追踪 `acquires` 声明的资源是否仅在受信任的上下文中被借用
- 确认 `friend` 声明是否合理限制了跨模块访问范围

## Classify

**漏洞**：
- 公开函数直接操作任意地址的资源，且未验证调用者与资源所有者关系
- 资源可通过非预期路径被外部模块访问（如 `public(friend)` 误用）
- 缺少 Capability 保护的管理员函数允许任意用户修改全局状态

**误报**：
- 函数设计上需要读取他人资源作为只读查询（如排行榜、NFT 元数据）
- 资源所有权已通过业务逻辑层（如智能合约上层）进行校验
- 使用 `&signer` 参数限制资源访问，且 Aptos/Sui 运行时已保证签名者身份

**代码异味**：
- 资源访问权限过于宽泛但业务逻辑尚未触发实际风险
- 缺少显式的权限校验注释，代码可读性差
- `public` 函数暴露资源操作能力但调用路径复杂，需跨模块分析

## Low risk

- 资源仅包含非敏感的公开数据（如统计信息、元数据），泄露不影响资产安全
- 资源访问受链级权限控制（如 Sui Object Capability），即使函数公开也无法绕过所有权检查
- 资源操作受严格的业务流程限制（如需多签、时间锁），单点突破难以造成损失
- 仅在测试模块或已弃用代码路径中存在，未部署到主网环境
- 资源访问需配合其他高门槛条件（如需支付高额手续费、链上治理投票通过）

## 审计专业技巧

**技巧1：资源所有权链路追踪**
- 从 `borrow_global` 的目标地址入手，反向追踪该地址的来源：是函数参数、常量、还是动态计算？
- 若地址来自参数，检查调用堆栈上层是否有签名者校验（`signer::address_of(&tx_context::signer())`）
- 绘制"访问链路图"：用户 → 入口函数 → 资源访问 → 状态修改，识别每个环节的校验点
- 特别关注 `entry` 函数与内部函数的权限边界，`entry` 无法接收 `&signer` 以外的对象作为证明

**技巧2：Capability 模式完整性检查**
- 不仅检查是否存在 Cap 结构体，更要验证 Cap 的初始化与分发逻辑是否安全
- 检查 Cap 是否只能由 `init_module` 函数单次创建，或存在运行时无限创建的漏洞
- 追踪 Cap 的 `store` 能力：若 Cap has `store`，需检查是否可被保存到全局状态被恶意调用者获取
- 确认所有敏感操作的守门函数（gate function）是否都要求传入相应 Cap

**技巧3：多链合约差异化理解**
- **Aptos**：`&signer` 参数由链运时保证真实性，验证 `signer::address_of()` 后可信任；`vector` 和 `table` 遍历需小心边界
- **Sui**：优先使用 `ID` 和 Object Capability，`borrow_global` 模式本质上风险更高；`transfer_to_object` 后的所有权转移需完整路径检查
- **Movement**：Move 语言的 `acquires` 声明不只是编译检查，也提示了该函数涉及的全局状态，遗漏易导致逻辑漏洞

**技巧4：真实漏洞的标志特征**
- 直接拼接地址参数到 `borrow_global<Vault>(addr)`，无任何前置校验 → **高危**
- 函数接受 `address` 参数但无 `&signer` 参数，仍执行转账/销毁操作 → **高危**
- `public(friend)` 模块列表包含不可信第三方 → **中危**
- 资源包含私钥、签名密钥等加密材料但可被公开读取 → **严重**
- `assert!` 语句中存在逻辑漏洞（如 `assert!(addr != 0x0)` 但未检查是否等于 `caller`）→ **高危**

**技巧5：常见误报陷阱与判别**
1. **陷阱：只读查询被标记为高危**
   - 症状：`public fun query_user_balance(addr: address): u64` 被报告为漏洞
   - 判别：确认函数返回值仅为查询，不修改任何资源状态；链下查询通常允许读取任意账户数据
   - 结论：如果查询返回的数据本就是公开的（如 NFT 元数据、排行榜），则为误报

2. **陷阱：Capability 模式的误识别**
   - 症状：函数接受 `struct Cap` 参数但报告为"缺少权限检查"
   - 判别：检查是否正确验证了 Cap 的真实性（通过类型系统，Cap 无法伪造），而非额外的 `assert!`
   - 结论：Move 的强类型系统本身就是权限证明，不需要额外的地址检查

3. **陷阱：业务层校验的忽视**
   - 症状：智能合约函数 `public fun transfer(to: address, amount: u64)` 看似无校验
   - 判别：检查该函数是否只能在特定交易脚本或上层合约内部调用；链上应用可能在应用层做权限检查
   - 结论：若调用路径已通过 SDK/脚本层严格限制，智能合约层次的冗余检查可能被优化掉

4. **陷阱：测试代码的误报**
   - 症状：`#[test_only]` 或 `#[test]` 模块中存在不安全模式
   - 判别：确认该代码是否编译到主网合约中（通常测试代码不应进入生产）
   - 结论：如部署时已剥离测试代码，则为误报；否则为高危漏洞

**技巧6：深层审计检查清单**
- [ ] 所有 `public(friend)` 的模块列表是否已审计？存在恶意模块？
- [ ] 资源初始化（`move_to<T>(&account, resource)`）的调用权限是否严格？
- [ ] 是否存在通过 `&mut GlobalState` 进行间接资源修改？
- [ ] 多步事务中，每步都验证了签名者与操作目标的关系吗？
- [ ] 是否存在整数溢出后权限校验失效的场景（如 `require!(caller_balance >= amount)`）？
- [ ] 资源的 `drop` 能力是否被不当利用（如未销毁就声明资源被删除）？

## 真实漏洞案例对比

**案例A：真实漏洞 - Diem 社区合约权限绕过**
```move
public fun withdraw_from_any(src: address, amount: u64) {
    // ❌ 未验证调用者与 src 关系，任意账户可提现他人资金
    let account = borrow_global_mut<Account>(src);
    account.balance = account.balance - amount;
}
```
判别要点：函数公开、接受地址参数、无前置权限检查 → **确定漏洞**

**案例B：看似漏洞，实为设计 - 交易对流动性查询**
```move
public fun get_pool_state(pool_id: u64): (u64, u64) acquires Pool {
    let pool = borrow_global<Pool>(@0x1);
    // 返回流动性池的公开状态，任意地址可查询
    (pool.reserve_x, pool.reserve_y)
}
```
判别要点：仅读取、数据本身应为公开、业务模型要求透明 → **确定为合法设计**

**案例C：边界漏洞 - Capability 创建条件不足**
```move
public fun create_admin_cap(): AdminCap {
    // ❌ 任意地址都能创建 AdminCap，无初始化限制
    AdminCap {}
}
```
判别要点：Cap 的创建无 `entry` 限制、无 `signer` 验证 → **确定漏洞**
