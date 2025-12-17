# Rust_MissingVersionValidation

**适用链**：Solana、CosmWasm、NEAR Protocol 等 Rust 生态链  
**漏洞分类**：升级风险 - 缺失版本验证

---

## Details

### 代码示例

**Solana 可升级程序未验证版本号**
```rust
// 升级函数未检查版本兼容性
pub fn upgrade_program(ctx: Context<UpgradeProgram>, new_program_data: Vec<u8>) -> Result<()> {
    let program_account = &mut ctx.accounts.program;
    
    // 危险：直接覆盖程序数据，未验证版本号
    program_account.data = new_program_data;
    
    Ok(())
}
```

**CosmWasm 迁移未检查版本约束**
```rust
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn migrate(deps: DepsMut, _env: Env, _msg: MigrateMsg) -> Result<Response, ContractError> {
    // 危险：直接执行迁移逻辑，未验证版本兼容性
    let new_state = State { /* ... */ };
    STATE.save(deps.storage, &new_state)?;
    
    Ok(Response::default())
}
```

**NEAR 合约升级缺少版本守卫**
```rust
#[near_bindgen]
impl Contract {
    // 危险：升级方法无版本检查
    pub fn upgrade(&mut self, code: Vec<u8>) {
        Promise::new(env::current_account_id())
            .deploy_contract(code);
    }
}
```

### 快速定位核心操作的技巧 **(L2-L3)**

**关键函数特征** (L1-L2)：
- Solana: `upgrade_program`, `set_upgrade_authority`, `bpf_loader_upgradeable`
- CosmWasm: `migrate()`, `MigrateMsg`, `entry_point`
- NEAR: `#[private]` upgrade 方法, `deploy_contract`

**审计路径** (L3)：
1. 搜索 `upgrade`/`migrate`/`deploy_contract` 关键词
2. 检查是否存在 `VERSION` 常量或版本字段定义
3. 确认升级逻辑是否包含版本号比对（如 `require!(new_version > old_version)`）
4. 验证是否有数据结构兼容性检查（如字段类型、顺序）

### 快速定位保护机制的技巧 **(L2-L4)**

**有效保护特征** (L2)：
- 存在明确的版本号字段：`VERSION`, `CONTRACT_VERSION`, `PROGRAM_VERSION`
- 版本比对逻辑：`version > previous_version`, `semver::Version::parse()`
- 状态兼容性校验：字段映射检查、数据迁移测试

**审计检查点** (L3-L4)：
1. **版本递增验证** (L3)：是否强制新版本号必须大于旧版本
2. **版本格式校验** (L2)：是否使用语义化版本控制（semver）
3. **破坏性变更检测** (L4)：
   - 跨文件追踪：状态结构体定义的历史变化
   - 反序列化测试：旧数据能否被新代码正确解析
4. **回滚机制** (L3)：是否保留旧版本数据快照或回滚路径

---

## Classify

### 归类为漏洞
- **无版本校验**：升级/迁移函数完全不检查版本号，可任意覆盖
- **版本可降级**：允许 `new_version < old_version`，可回退到有漏洞的旧版本
- **状态结构不兼容**：新版本改变了核心存储布局但未迁移（如 CosmWasm Item 键名变更、Solana Account 字段重排）
- **缺少权限隔离**：升级权限未单独管理，可被滥用

### 归类为误报
- **测试/示例代码**：明确标注为 `#[cfg(test)]` 或 demo 合约
- **不可升级设计**：`upgrade_authority` 已置为 `None` 或合约设计为不可变
- **链上治理控制**：升级需经过 DAO 多签+时间锁，版本验证由链下治理流程保证

### 归类为代码异味
- **版本号仅作日志记录**：有版本字段但未在升级逻辑中使用
- **软性版本检查**：版本不匹配时仅发出警告，不阻止升级
- **文档与代码不一致**：README 声称有版本保护，但代码实现缺失

---

## Low risk

### 可接受的低风险场景
- **版本回退有业务合理性**：协议明确支持紧急回滚，且有额外的多签+时间锁保护
- **内部管理合约**：仅用于团队内部测试环境，不处理用户资金
- **链级升级保护**：区块链本身提供强制版本检查（如 Cosmos SDK 的 ConsensusVersion）
- **冻结的权限**：升级权限已被销毁或转移至黑洞地址（Solana: `set_upgrade_authority(None)`）
- **向后兼容设计**：所有状态变更严格遵循向后兼容原则，旧数据可无缝迁移

### 降低风险的补偿措施
- **全面的集成测试**：覆盖所有历史版本的升级路径
- **分阶段升级**：使用金丝雀部署，先在测试账户上验证
- **链下版本审核**：通过治理投票审查每个版本的代码差异
