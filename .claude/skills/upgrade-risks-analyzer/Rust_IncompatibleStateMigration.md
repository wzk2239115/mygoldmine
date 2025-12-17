**Rust**（适用于 Solana、CosmWasm 等）  
常出现在可升级程序（Program）或模块热加载机制中，包括但不限于 upgrade_authority 未冻结、状态迁移未验证、新旧版本 ABI 不兼容等方式：  
- 不兼容的状态迁移：程序升级时账户数据结构变更但未提供迁移逻辑，导致旧数据无法被新版本正确解析，详见：Rust_IncompatibleStateMigration.md
## Details

**代码示例：**
```rust
// Solana 示例：账户结构体变更未提供迁移
#[account]
pub struct UserAccount {
    pub balance: u64,
    // 升级后新增字段，未处理旧数据
    pub rewards: u64,
}

// CosmWasm 示例：状态反序列化失败
pub fn migrate(deps: DepsMut, _env: Env, _msg: MigrateMsg) -> Result<Response, ContractError> {
    // 直接反序列化新结构，未兼容旧版本
    let state: State = STATE.load(deps.storage)?;
    Ok(Response::new())
}

// 危险：PDA/账户数据大小变化未检查
let account = UserAccount::try_from_slice(&account_data)?; // 新增字段后直接解析
```

**快速定位核心操作：（L2-L3: 跳读到逐行）**
- 搜索 `#[account]` / `#[derive(Accounts)]` 结构体定义的版本变更历史
- 检查 `try_from_slice` / `deserialize` 调用处是否有版本判断
- 关注 `migrate` 函数内的数据转换逻辑
- 追踪 `realloc` / `AccountInfo.realloc()` 调用是否处理扩容
- CosmWasm 中检查 `STATE.load()` 前是否有版本校验

**快速定位保护机制：（L3-L4: 逐行到跨模块）**
- 查找 `version` / `schema_version` 字段及其校验逻辑
- 确认 `migrate` 函数是否遍历所有可能的旧版本分支
- 检查是否存在 `from_v1_to_v2` 类型的迁移辅助函数
- 验证 `AccountInfo.data_len()` 在反序列化前是否被检查
- 追踪 `#[instruction]` 是否包含显式的 `init_if_needed` 约束

## Classify

**确认为漏洞的条件：**
- 结构体新增/删除字段后，未提供任何版本兼容处理
- 直接 `unwrap()` 或 `expect()` 反序列化结果，无回退逻辑
- PDA 种子计算发生变化但未迁移旧账户
- 数据大小变更但 `realloc` 调用缺失或条件错误

**误报标志：**
- 新部署合约（无历史数据需迁移）
- 测试/开发环境专用代码
- 已有完整版本号机制且所有分支都处理

**代码异味（需人工复核）：**
- 迁移逻辑存在但覆盖不全（如只处理最近一个版本）
- 版本检查在外部脚本而非链上合约内
- 依赖管理员手动升级所有账户（中心化风险）

## Low risk

**以下情况可评为低风险：**
- 字段仅追加且新字段有明确的 `Option<T>` 或默认值处理
- 合约实现了完善的版本迁移测试套件（检查测试覆盖率）
- 使用 `#[zero_copy]` 且布局未变（Solana）
- 升级前强制执行状态冻结期（时间锁保护）
- 数据迁移通过多签治理流程触发，且有回滚机制

## 审计专业技巧

### 版本兼容性的实地判断

**核心原则：跟踪数据生命周期**
1. **链上数据快照**：从创始块到最新块，追踪同一账户的反序列化日志
   - Solana 中使用 `anchor-client` 在升级前后对比账户数据二进制表示
   - CosmWasm 中查询历史状态根 (state root)，利用存档节点重放状态迁移

2. **版本号的隐式契约**：即使没有显式 `version` 字段，也要检查：
   - 结构体大小（通过 `std::mem::size_of()` 断言）
   - 字段偏移量（通过 memoffset crate 检查 `offset_of!` 宏）
   - 序列化格式的 magic bytes 或 discriminator 变化

### 真实漏洞 vs 误报案例对比

**案例 1：Solana PDA 种子变更引发的状态不可达**
```rust
// v1：使用固定 bump seed
pub fn init_account(ctx: Context<Initialize>) -> Result<()> {
    let (pda, bump) = Pubkey::find_program_address(&[b"vault"], program_id);
    // bump 为 254
}

// v2 升级：种子变更（真实漏洞）
pub fn init_account(ctx: Context<Initialize>) -> Result<()> {
    let (pda, bump) = Pubkey::find_program_address(&[b"vault", b"v2"], program_id);
    // bump 为 253，旧账户被遗弃
}
```
**区分方法**：
- ✅ 真实漏洞：旧 PDA 中的代币/SOL 永久锁定，无法通过链上指令触及
- ❌ 误报：如果有显式迁移指令将数据复制到新 PDA，或使用治理提案批量迁移

**案例 2：CosmWasm 反序列化边界条件**
```rust
// 看似危险的代码
pub fn migrate(deps: DepsMut, _env: Env, _msg: MigrateMsg) -> Result<Response> {
    let state: State = STATE.load(deps.storage)?; // 可能反序列化失败？
    Ok(Response::new())
}
```
**区分方法**：
- ✅ 真实漏洞：如果 `State` 结构体添加了非 `Option<T>` 字段，旧数据反序列化触发 `serde::Error`
- ❌ 误报：如果新增字段为 `#[serde(default)]`，或历史上从未有数据存储过该字段

### 审计清单与陷阱

**第一层检查（快速排查）**
- [ ] 搜索所有 `#[account]` 结构体，标记添加/删除字段的 Git commit
- [ ] 检查 `migrate` 函数是否存在（CosmWasm 必须、Solana 可选但推荐）
- [ ] 统计测试套件中的迁移相关用例数量（应 ≥ 3 个版本跨度）

**第二层检查（真伪区分）**
- [ ] 字段追加场景：确认新字段是否有默认值或 `Option` 包装
- [ ] 字段删除场景：验证旧字段是否在迁移函数中被显式赋予 zero 值或转移
- [ ] 数据扩容场景：检查 `realloc` 调用的条件是否涵盖所有升级路径
  ```rust
  // 正确做法：显式版本检查后再扩容
  if let Some(old_data) = deserialize_v1(data) {
      let new_data = convert_v1_to_v2(old_data);
      account.realloc(new_data.size(), is_signer)?;
      // 必须在 realloc 后赋值
  }
  ```

**第三层检查（上下文合成）**
- [ ] 交叉查证：权限模型中谁可以触发升级？（多签/DAO 风险更低）
- [ ] 时间约束：升级和迁移是否有时间锁（如 timelock 合约）？
- [ ] 测试网历史：该合约在测试网是否成功执行过迁移？

### 常见陷阱与启发

| 陷阱 | 症状 | 判断 |
|------|------|------|
| **隐形版本管理** | 无 `version` 字段，但通过结构体大小区分 | 需要反汇编或 memory layout 工具验证 |
| **分段迁移** | 迁移函数仅处理 v1→v2，遗漏 v2→v3 的历史数据 | 统计存储中仍为 v1 的账户占比 |
| **零拷贝陷阱** | `#[zero_copy]` 修饰结构体，布局变更未检查 | 检查 `#[repr(C)]` 和 `#[zero_copy]` 的互动 |
| **脚本外挂迁移** | 迁移逻辑在链外脚本而非合约内 | 验证脚本是否由多签管理员执行，是否有审计记录 |

### 实战审计流程

1. **信息收集**（30 分钟）
   - 获取 Git 历史中所有 account 结构体修改
   - 列出主网部署的合约版本号序列
   - 访问区块浏览器，采样 10 个账户的二进制数据

2. **静态分析**（1 小时）
   - 运行 `cargo expand` 查看宏展开后的结构体定义
   - 编写测试用例：手动序列化旧版本数据，尝试新版本反序列化
   - 使用 `memoffset` crate 打印所有结构体成员的字节偏移

3. **动态验证**（需沙箱环境）
   - 在本地 Anchor 集群模拟升级流程
   - 对比升级前后同一账户的状态根哈希
   - 执行迁移函数，捕获任何错误或边界情况

### 误报风险的最终定论

**参考基准**：如果满足以下任意一条，可降级为低风险：
- 合约已在测试网成功执行过至少 2 次版本迁移，且在主网部署后短期内（< 30 天）遭遇过升级，无故障记录
- 新字段添加使用 `#[serde(default)]`，且代码注释明确说明默认行为
- 迁移逻辑由独立的安全审计公司签字确认，报告需包含迁移路径覆盖率 ≥ 95%
