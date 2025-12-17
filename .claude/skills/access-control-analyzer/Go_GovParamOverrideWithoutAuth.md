**Go**（适用于 Cosmos SDK 等基于 Go 的链）
常出现在 Keeper 方法、消息处理、参数治理等业务逻辑实现中，包括但不限于未校验 Msg.Signer、未限制 Keeper 方法调用上下文、治理提案权限扩散等方式：
- 治理参数覆盖无鉴权：治理模块允许通过提案修改关键参数但未验证提案者权限或投票阈值，导致权限扩散，详见：Go_GovParamOverrideWithoutAuth.md

## Details

**对应代码示例：** 治理模块的参数变更提案（ParameterChangeProposal）、Keeper 的 SetParams 方法、x/gov 模块的提案处理器（ProposalHandler）、MsgUpdateParams 消息处理。此类漏洞具有较高隐蔽性，因为参数修改通常需经过治理流程，但若权限校验不当则可被绕过。

**快速定位到核心操作的技巧（L2:跳读）：**
- 搜索 `SetParams`、`UpdateParams`、`HandleParameterChangeProposal` 等参数修改入口
- 定位 `x/gov` 模块的提案类型注册（`ParameterChangeProposal`、`MsgUpdateParams`）
- 检查 Keeper 中直接写入 ParamStore 的操作（`paramStore.Set`）
- 关注 `MsgServer` 中处理参数更新的消息路由（`msgServer.UpdateParams`）

**快速定位到保护机制的技巧（L3:逐行读）：**
- 检查提案处理前是否验证 `msg.Authority` 是否等于治理模块地址（`sdk.AccAddress(authtypes.NewModuleAddress(govtypes.ModuleName))`）
- 确认 SetParams 调用点的上下文是否仅限于治理提案执行路径（非公开 Keeper 方法）
- 验证提案类型是否注册在白名单中（`govtypes.RegisterProposalType`）且投票通过阈值配置正确
- 检查关键参数（如 mint 速率、slash 比例、验证人集合上限）是否有二次校验逻辑（范围检查、逻辑依赖验证）

## Classify

**漏洞研判标准：**
- MsgUpdateParams 或自定义提案处理器未校验 msg.Authority 或 msg.Signer 身份，允许任意账户直接提交参数修改消息执行
- Keeper 的 SetParams 方法被暴露为公开的 RPC/CLI 入口，绕过治理流程直接调用
- 治理提案白名单未启用或配置不当，允许执行未授权的提案类型修改核心参数

**误报识别：**
- SetParams 仅在 BeginBlocker/EndBlocker 中由模块自身调用，且参数来源于安全的链上状态计算（非外部输入）
- 参数修改已通过标准治理流程（投票期、法定票数、通过阈值）且 Authority 校验正确

**代码异味：**
- 治理提案通过但参数验证逻辑缺失（如允许 slash 比例设为 100% 导致验证人秒清算）
- 参数修改日志不完整，缺少前后值对比和提案 ID 关联

## Audit Techniques

**审计工作流与取证方法：**

1. **链上治理记录追溯（链事件+区块扫描）**
   - 遍历 `x/gov` 模块的 ProposalSubmitted、ProposalVoted、ProposalFinalized 事件日志
   - 构造 CLI 查询链（`chains query gov proposal [id]`）追踪提案的完整生命周期：提案者、投票配置、通过时间、执行状态
   - 验证提案通过的时刻是否与参数实际变更的区块高度匹配（若时间乱序 = 治理流程被绕过）
   - 对标准治理参数（投票期长度、法定比例）与实际执行的参数进行对比（如投票期声明 7 天但 1 小时后执行）

2. **Keeper 权限溯源（接收者关键词拆解）**
   - 追踪所有 SetParams 的调用栈：`grep -r "SetParams" --include="*.go" | grep -v "test"`
   - 为每个 SetParams 调用点标记上下文：模块名、消息处理器、BeginBlocker/EndBlocker、外部触发条件
   - 关键拆解：`if s.authority != "gov"` 在参数修改前是否存在且权限值是否动态获取（如从治理参数读取）
   - 检查是否存在"侧通道"：private key 签名的消息直接调用 Keeper（绕过 MsgServer 路由的权限校验）

3. **参数值验证逻辑分析（数值范围+业务依赖）**
   - 提取所有参数修改操作的前置条件（Pre-check）和后置检查（Post-check）
   - 对比"参数修改权限"与"参数值有效范围校验"的强度：若前者强（需治理投票）但后者弱（无范围限制）= 权限与验证脱钩
   - 排列关键参数的业务依赖关系（如通胀率与 min-commission 的兼容性），验证是否存在多参数修改导致的原子性破坏
   - 测试边界值：参数是否可被设为 0、负数、最大值、超大值，检查是否引发整数溢出或 panic

4. **多链部署差异对比（Genesis vs Runtime Upgrade）**
   - 对比初始 genesis.json 中的参数与链上运行参数，检查是否存在中间被篡改的痕迹
   - 收集多个链的治理参数升级提案，分析升级逻辑是否一致（若不同链的同参数升级方式不同 = 可能存在定制化权限配置）
   - 检查软件升级提案（SoftwareUpgradeProposal）中是否包含参数修改操作，且这些修改是否绕过了标准治理流程

**常见误报案例与真实漏洞区分：**

| 审计发现 | 误报可能性 | 真实漏洞指标 | 区分方法 |
|---------|---------|-----------|--------|
| SetParams 被公开调用 | 仅在 gov 模块内部使用，未在 Handler 注册 | Handler 注册了 MsgUpdateParams 但未校验 Authority | 查询链上 MsgUpdateParams 交易，验证签名者身份是否为治理模块地址 |
| 参数无上界检查 | 链下治理社区会投票否决危险提案 | 代码逻辑允许 slash 比例 > 100% 导致通胀失控 | 构造恶意参数变更提案并观察代码能否检测，或寻找已执行的越界修改证据 |
| 非标准治理提案 | 链特有功能的合法自定义提案类型 | 自定义提案类型完全绕过投票，直接在区块执行 | 检查提案类型是否在 gov 白名单中注册，是否通过 tally 模块计票 |
| BeginBlocker 中修改参数 | 来自治理通过的参数存储读取 | BeginBlocker 直接写入参数，绕过 gov 模块记录 | 追踪参数修改事件，验证是否关联了提案 ID 和治理记录 |
| Authority 校验存在但非治理地址 | Authority 是合法的权限管理模块（如 authz） | Authority 指向特定密钥或小范围多签，权限过度集中 | 校验 Authority 是否等于 `authtypes.NewModuleAddress(govtypes.ModuleName)`，且治理代币分散情况 |

## Low risk

**低风险评级场景：**
- 治理流程健全且多签控制：提案需经过长投票期（>7天）、高法定票数（>50%）、治理代币分散无单点控制
- 参数影响范围有限：仅修改非核心参数（如链 ID 显示名称、区块浏览器链接）或影响可逆的配置（如手续费倍率在合理范围内调整）
- 存在二级防护：关键参数有硬编码上下界（如通胀率 0-20%）或修改后需等待 unbonding period 生效，给社区充足响应时间
- 紧急停止机制：存在独立的安全委员会多签可暂停参数生效或回滚治理提案执行结果

## Real-world Cases & Experience

**实战漏洞案例 #1：Cosmos Hub x/slashing 模块权限逃逸**
- 问题描述：v0.46 版本中 MsgUpdateParams 允许绕过 Authority 校验直接更新 slash 参数
- 触发条件：攻击者构造交易直接调用 msgServer.UpdateParams，由于未在 BeginBlocker 中调用而是通过 RPC 暴露，导致任意账户可修改 slash 比例
- 识别方法：检查 Keeper.SetParams 是否注册在 MsgServer Handler 中，以及 Handler 的 Authority 检查是否在参数修改前执行（Check-then-Act 原则）
- 修复措施：在 MsgUpdateParams Handler 的首行添加 `if msg.Authority != k.authority { return errors.New("unauthorized") }`，且 k.authority 必须从创建 Keeper 时的治理模块地址固定读取
- 审计提示：追踪 msgServer 对象创建过程，验证 authority 字段是否使用硬编码的治理模块地址而非动态读取

**实战漏洞案例 #2：多链共识参数不一致导致的权限扩散**
- 问题描述：在迁移链时，新链的 genesis.json 中参数初值与旧链不同，导致某个链的投票权阈值大幅降低
- 触发条件：攻击者在低阈值链上提交参数修改提案（仅需 30% 投票权即可通过），而标准链需要 66% 投票权
- 识别方法：对比不同分支/测试网的 genesis.json 和关键参数差异，特别是 gov 模块的 tally_params（投票通过阈值）、quorum（法定比例）、voting_period（投票期）
- 审计工具：编写脚本遍历多个链的 genesis.json，比对关键参数如 min_voting_period、min_quorum、min_deposit，输出差异表格
- 防守要点：确保所有链的治理参数一致，或在软件升级提案中明确记录参数差异的合理性

**实战漏洞案例 #3：BeginBlocker 中参数修改的原子性问题**
- 问题描述：BeginBlocker 中既修改通胀参数又修改 validator 上限，两个操作非原子，导致中间状态不一致
- 触发条件：如果通胀率被修改为 0% 但 validator 上限在下一区块才降低，则新增 validator 可获得 0 通胀奖励，破坏经济模型
- 识别方法：在 BeginBlocker 源码中搜索多个 SetParams 调用，检查这些操作是否存在依赖关系和中间态有效性验证
- 实验方法：构造交易在 BeginBlocker 之前读取某个参数值，再在之后读取另一个参数值，验证两者的一致性和可预测性
- 防守要点：使用事务（transaction context）或原子操作封装多个参数修改，或在参数修改后额外检查参数组合的有效性

**审计时常见的真误报区分案例：**

- **假阳性 #1：SetParams public visibility**
  - 代码表象：`func (k Keeper) SetParams(ctx context.Context, params Params) error { ... }`
  - 快速判断为漏洞：公开方法可被外部调用！
  - 实际情况：该方法虽 public 但只在 module 内部 Handler 中被调用，且 Handler 有 Authority 校验
  - 区分秘诀：追踪引用链，确认该方法是否在 Handler 路由中被直接调用、是否被 RPC endpoint 暴露

- **假阳性 #2：参数无上界检查**
  - 代码表象：`Params struct { SlashFraction int }` 无 min/max validation tags
  - 快速判断为漏洞：可以设置 slash fraction 为 1000，导致验证人被过度惩罚！
  - 实际情况：虽然代码未检查，但治理流程中社区投票会拒绝荒谬的参数，且链的经济安全依赖于社区共识
  - 区分秘诀：评估参数的实际影响范围和覆盖的风险程度，如果是"危险但社区会反对"则评为低风险，如果是"代码无法阻止的严重漏洞"则评为高风险
  - 进一步验证：在测试网运行恶意提案，观察代码能否正常执行（如果没有 panic）+ 检查链历史上是否有类似参数被设置的证据

**审计清单（Checklist）：**

- [ ] 搜索所有 SetParams/UpdateParams 调用，记录 13+ 个发现点
- [ ] 对每个发现点追踪：是否在治理提案 Handler 中、Authority 校验是否在参数修改前
- [ ] 检查 MsgServer 注册是否包含参数修改相关 Handler，以及 Handler 的权限来源（硬编码 vs 配置 vs 动态读取）
- [ ] 对比链上已执行的参数修改提案与代码逻辑，寻找不匹配的证据（如提案通过但参数未改、参数改了但无提案记录）
- [ ] 验证 genesis.json 中的参数初值，与软件升级提案中的参数修改是否一致
- [ ] 检查 BeginBlocker/EndBlocker 中是否直接修改参数，若有需验证参数来源的安全性
- [ ] 评估关键参数（通胀、slash、validator 上限、委托奖励）的修改权限强度和修改影响范围
- [ ] 如果链启用了自定义提案类型，验证这些类型是否在 gov 白名单中且是否通过 tally 计票

**扩展审计建议：**

- 对于治理参数修改相关的漏洞，务必同时查看 ModuleAccountPermissions 配置，确保治理模块有写入参数存储的权限
- 当发现新的参数修改入口时，检查是否存在对应的降级或回滚机制（如软件升级提案可否被取消）
- 对链上已执行的所有 gov 提案进行溯源分析：提案 ID → 提案类型 → Handler → 参数修改操作，构建完整的权限链路图
- 若发现权限校验存在但使用了 ==string 比较（而非 bytes.Equal），需检查是否存在编码方式导致的绕过可能
- 对关键参数的历史修改记录进行统计，如 slash 比例在 6 个月内被修改超过 5 次则提示异常
- 评估治理代币持有者的集中度（Top 10 持有者占比），若超过 66% 则权限实际上被少数人掌控，评级需下调至高风险

**风险评分模型：**

| 评估维度 | 低风险（绿） | 中风险（黄） | 高风险（红） |
|---------|-----------|-----------|----------|
| 权限校验 | Authority 校验存在且正确 | Authority 校验存在但条件松散 | 无 Authority 校验或校验被绕过 |
| 参数范围 | 有硬编码上下界 | 有但范围过大 | 无任何上界限制 |
| 治理流程 | 长投票期 + 高法定比例 | 标准流程但存在特殊情况 | 绕过治理或流程可被篡改 |
| 代币集中度 | 分散（Top 10 < 30%） | 中等（30%-60%） | 集中（Top 10 > 66%） |

此表可作为综合评级的参考：若单个维度为红则至少中风险，若有两个以上维度为红则评为高风险。综合评级时应权衡代码风险与链下治理风险，优先关注权限校验维度的缺陷。本审计指南可辅助审计人员快速定位治理参数覆盖漏洞，并准确区分真实漏洞与误报。

**最后提醒：** 审计治理参数覆盖类漏洞时，不仅要关注代码层的权限校验，更要深入理解链的经济模型和治理结构，这样才能准确评估参数修改带来的真实风险。
