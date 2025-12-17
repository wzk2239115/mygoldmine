# Rust_UnfrozenUpgradeAuthority

**适用链：** Solana、CosmWasm、NEAR  
**风险类型：** 升级权限管理缺陷  
**成因：** 程序升级权限（upgrade_authority）未冻结或转移到治理合约，导致单点控制风险

---

## Details

### 代码示例

**Solana 程序部署（未冻结）：**
```rust
// 部署后未调用 set_upgrade_authority(None)
solana program deploy --program-id <PROGRAM_ID> target/deploy/program.so
// upgrade_authority 默认为部署者钱包地址
```

**CosmWasm 合约初始化：**
```rust
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn instantiate(deps: DepsMut, env: Env, info: MessageInfo, msg: InstantiateMsg) -> Result<Response, ContractError> {
    let admin = msg.admin.unwrap_or(info.sender.to_string()); // 允许指定 admin
    CONFIG.save(deps.storage, &Config { admin })?;
    Ok(Response::default())
}

pub fn execute_migrate(deps: DepsMut, info: MessageInfo, new_code_id: u64) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin { return Err(ContractError::Unauthorized {}); }
    // 单点 admin 可随意迁移合约
    Ok(Response::new().add_message(WasmMsg::Migrate { contract_addr: env.contract.address, new_code_id, msg: to_binary(&{})? }))
}
```

**NEAR 合约状态管理：**
```rust
#[near_bindgen]
impl Contract {
    #[private]
    pub fn upgrade(&mut self, code: Base64VecU8) {
        // 仅通过 #[private] 限制为自调用，但未验证多签治理
        Promise::new(env::current_account_id()).deploy_contract(code.0);
    }
}
```

### 快速定位核心操作（L2 跳读）

**Solana：**
- 搜索 `bpf_loader_upgradeable` 程序 ID 引用
- 检查 `ProgramData` 账户的 `upgrade_authority_address` 字段是否为 `None` 或多签地址
- 定位 `solana program set-upgrade-authority` 调用历史

**CosmWasm：**
- 查找 `instantiate` 中 `admin` 参数处理逻辑
- 扫描 `ExecuteMsg::UpdateAdmin` 或自定义升级入口
- 检查 `migrate` 函数的权限校验（`deps.api.addr_validate`）

**NEAR：**
- 定位 `#[private]` 修饰的升级函数
- 搜索 `Promise::new(...).deploy_contract` 调用
- 验证是否通过 `signer_account_id()` 多签验证

### 快速定位保护机制（L3 逐行读）

**核心验证点：**
1. **权限冻结检查：**
   - Solana: `if upgrade_authority_address.is_some()` 标记为风险
   - CosmWasm: `admin` 是否为多签合约地址（需跨合约验证）
   - NEAR: 升级函数是否需要多方签名调用

2. **时间锁/延迟机制：**
   - 搜索 `Timelock`、`delay`、`scheduled_upgrade` 等关键词
   - 检查是否存在 `propose -> wait -> execute` 模式

3. **提案投票流程：**
   - 定位治理合约调用（如 `spl-governance`、`cw3-multisig`）
   - 验证升级是否需要通过 DAO 投票门槛

4. **紧急暂停开关：**
   - 查找 `pause`、`emergency_shutdown` 状态标志
   - 确认升级前是否检查合约状态

---

## Classify

### 漏洞判定标准：
1. **关键特征：** upgrade_authority 为 EOA 地址（外部账户）且无时间锁保护
2. **场景验证：** 
   - Solana: 通过 `solana program show <PROGRAM_ID>` 查看 `Authority` 字段
   - CosmWasm: 调用 `query_contract_info` 检查 `admin` 是否为多签
   - NEAR: 升级函数可被单一账户直接调用

### 误报情况：
1. Admin 地址实为多签合约但链上标识不清晰（需人工确认合约类型）
2. 通过链下治理流程控制私钥但未体现在代码中
3. 测试网环境保留灵活升级权限（需区分主网/测试网）

### 代码异味：
1. Admin 可转移但存在 24 小时延迟（风险降低但仍非最佳实践）
2. 紧急升级通道绕过治理但需 3/5 多签（应明确文档说明）

---

## Low risk

### 可接受的低风险场景：
1. **初始部署阶段：** 主网上线首 30 天内保留快速修复权限，但需公告冻结时间表
2. **多重保护叠加：**
   - Upgrade_authority 为 2/3 多签 + 48 小时 Timelock
   - 存在独立的紧急暂停机制（由不同密钥控制）
3. **渐进式去中心化：**
   - 已公开权限转移路线图
   - 当前阶段在治理代币分发期，代码已审计且存在漏洞赏金计划
4. **有限升级范围：**
   - 仅允许修改非关键参数（如手续费率上限）
   - 核心逻辑（如资产转移函数）不可变更
5. **透明度补偿措施：**
   - 所有升级提案提前 7 天公示
   - 链上事件可被监控系统实时捕获并警报
