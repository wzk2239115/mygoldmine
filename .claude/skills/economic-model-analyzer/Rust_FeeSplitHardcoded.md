# Rust_FeeSplitHardcoded - 硬编码费用分配

**漏洞类型**: 经济模型缺陷 - 费用分配比例固化  
**影响范围**: Solana programs, Substrate pallets, 自定义 Rust 链协议层

## Details

**典型代码特征**：费用分配逻辑直接使用常量或魔法数字，无可配置参数或治理入口

```rust
// 示例：硬编码的70/30分配
let protocol_fee = total_fee * 70 / 100;
let validator_fee = total_fee * 30 / 100;

// 或通过不可变常量
const PROTOCOL_SHARE: u64 = 7000; // basis points
const VALIDATOR_SHARE: u64 = 3000;
```

**快速定位核心操作（L2-跳读）**:  
- 搜索关键词：`fee`, `split`, `distribute`, `share`, `percentage`, `basis_points`, `mul_div`
- 关注函数：`distribute_fees`, `split_rewards`, `calculate_share`, `process_protocol_fee`
- 数学运算：涉及除法/乘法的费用计算表达式（特别是包含常量的）
- Account 结构：查看 `fee_account`, `treasury`, `protocol_vault` 等账户的资金流入逻辑

**快速定位保护机制（L3-逐行读 + L4-跨模块追踪）**:  
- 参数存储：检查是否有 `Config` 账户或状态变量存储分配比例（PDA 配置账户）
- 治理入口：搜索 `update_fee_split`, `set_protocol_share`, `governance`, `admin_only` 等修饰符/函数
- 权限控制：查找 `require!(ctx.accounts.authority.key() == ...)`，确认是否有权限管理者可动态调整
- 跨模块：追踪 `initialize` 函数查看初始化是否预留配置接口，检查是否有单独的 admin 模块

## Classify

**判定为漏洞**：
- 费用分配比例完全硬编码为常量，且协议无任何治理机制可调整
- 涉及多方利益分配（协议/质押者/LP/开发者）且比例固定，无法响应市场博弈变化
- 经济白皮书承诺参数可调，但代码实现为固定值

**判定为误报**：
- 协议明确声明"不可变费用模型"作为核心特性（需文档佐证）
- 存在升级机制（如 Solana 的 `bpf_loader_upgradeable`）且有明确治理流程
- 已有独立的配置账户存储参数，只是当前调用使用快照值

**判定为代码异味**：
- 费用比例虽硬编码，但金额极小（如 0.1%）且仅用于覆盖交易成本
- 测试网或早期版本明确标注 TODO/FIXME 待治理模块开发

## Low risk

以下情况可评定为 **Low** 风险：
- 硬编码比例符合主流协议标准（如 Uniswap 0.3% 类标准费率），无明显不合理之处
- 协议处于冷启动阶段，团队承诺在 TVL 达到阈值前引入治理
- 分配仅影响单一内部角色（如全部归属单一 DAO 金库），不涉及多方博弈失衡
- 合约已部署时间短（<3个月）且社区规模小（TVL < $100K），调整成本可控
- 存在"紧急暂停"机制可冻结费用收取，降低长期固化风险

## 审计专业技巧：真实漏洞 vs 误报区分经验

### 1. 现场实战区分框架

**真实漏洞的五层递进证据**：
- **L1 代码层**：硬编码常量 + 无配置账户存储 + 无治理函数入口（三点同时满足）
- **L2 链上查证**：部署合约代码中确实无 `update_fee_split` 等治理函数（反编译/字节码验证）
- **L3 文档层**：白皮书/文档宣称"费用可调配"但代码实现固定（承诺-实现落差）
- **L4 权限层**：即使有治理函数，升级权限在多签/时锁后仍由单个团队控制（实质中心化）
- **L5 资金风险**：硬编码比例偏离市场合理值（如 Protocol 80% 而市场标准 20%），会导致使用者资金损失

**真实漏洞案例识别**：Moola Market (Celo) 的费用分配就曾因硬编码导致流动性提供者激励不足，最终被迫紧急升级。特征是：协议已上线真实资金但无法快速调整参数。

### 2. 常见误报陷阱与应对

**误报情景1: 配置分离但审计员未全面跟踪**
```rust
// config.rs (分离文件，审计员遗漏)
pub struct FeeConfig {
    protocol_share: u64,
    validator_share: u64,
}

// main.rs (审计员只看这里)
let protocol_fee = total_fee * 70 / 100;  // 看起来硬编码
```
**应对**：完整读取 `initialize` 和 `Config` 相关逻辑，追踪数据流向。执行 `grep -r "FeeConfig"` 找到所有引用点。

**误报情景2: 常量用于默认值，但实际由账户变量覆盖**
```rust
const DEFAULT_PROTOCOL_SHARE: u64 = 7000;

pub fn distribute_fees(ctx: Context<DistributeFees>) -> Result<()> {
    let share = ctx.accounts.config.protocol_share; // 从账户读取，非常量
    let amount = (total_fee * share) / 10000;
    ...
}
```
**应对**：跟踪变量源头，确认是否真的来自 `Config` 账户（链上可变存储）还是编译期常量。

**误报情景3: Phantom Data 或仅用于类型安全的常量**
```rust
const MAX_FEE_PERCENTAGE: u64 = 100;  // 纯数学边界，非业务配置
```
**应对**：分析常量含义，区分"业务配置"（应可调）vs "数学常数"（无需调）。

### 3. 链上验证技巧

**三步验证法**：
1. **字节码级验证**：使用 `solana account <contract-address>` 查看部署数据，确认无配置账户（config PDA 应存在且可寻址）
2. **事件追踪**：搜索 `emit` 语句，是否有 `FeeUpdated` 等事件日志（有则意味曾被修改）
3. **调用链分析**：在链上浏览器追踪费用账户资金流，若金额一致性高说明比例固定；若变动则可能有参数调整

**真实案例**：Orca Whirlpools (Solana) 的费用分配初期硬编码为 25%，但通过 `whirlpool_config` PDA 存储实现治理，审计时易误报。解决办法是检查 `WhirlpoolConfig::fee_rate` 是否在 `initialize` 中可设置且在 `update_fee_rate` 中可修改。

### 4. 经济模型审计检查清单

| 检查项 | 真实漏洞信号 | 正常信号 | 审计优先级 |
|--------|------------|--------|----------|
| 配置存储位置 | 常量定义 | Config 账户/状态树 | P0 必查 |
| 治理函数存在 | 否 | `update_*` 函数+权限检查 | P0 必查 |
| 参数可修改性 | 编译期固化 | 链上动态可读写 | P0 必查 |
| 升级机制 | 无/单中心 | 多签/时锁/社区提案 | P1 重点 |
| 文档一致性 | 白皮书说可调，代码硬编码 | 文档与代码相符 | P1 重点 |
| 经济激励合理性 | 比例极端失衡 | 符合市场标准/明确阶段目标 | P2 参考 |

### 5. 跨协议对标检查

- **Uniswap V4**: 使用 `Hooks` 动态控制费用，配置可从外部合约读取
- **Aave V3**: 费用在 `DataTypes.ReserveConfigurationMap` 中存储，通过 `updateATokenIncentivesController` 修改
- **Curve**: 费用在 `admin_fee` 和 `fee` 变量中（链上可读），`commit_new_fee` + `apply_new_fee` 时锁机制

**对标方法**：将目标协议的费用机制与同类主流协议对比，若明显劣化（如完全无治理）则风险上升。

### 6. 报告撰写建议

- **避免**："代码存在硬编码，这是安全漏洞" ❌ （过度简化，易触发误报纠纷）
- **建议**："费用分配比例（70% Protocol / 30% Validator）在主合约中通过常量定义，暂无链上可调参数或治理函数入口。根据文档 v1.0 宣称的'动态费用治理'承诺，建议评定为 Medium 风险，需在 v1.1 引入 Config 账户机制。" ✅ （逻辑严谨，易与团队沟通）
