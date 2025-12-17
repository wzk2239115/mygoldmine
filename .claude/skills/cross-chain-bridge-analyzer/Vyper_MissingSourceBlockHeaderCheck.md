**Vyper**  
常出现在简化版跨链锁定/释放合约或预言机驱动的桥接逻辑中，包括但不限于事件日志解析可被操控、目标链未验证源链区块头、跨链操作无速率限制等方式：  
- 缺失源区块头检查：目标链未验证源链区块头有效性，接受未确认或伪造的跨链消息，详见：Vyper_MissingSourceBlockHeaderCheck.md  
在区块链领域，专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

目标链接收跨链消息时，直接信任传入的 `block_hash`、`block_number` 或事件日志，未验证源链区块头的 Merkle 根、难度或最终确认状态。常见模式：
```vyper
@external
def relay_message(_block_hash: bytes32, _proof: Bytes[1024], _message: Bytes[512]):
    # 直接使用 _block_hash，无验证逻辑
    assert self._verify_proof(_block_hash, _proof, _message)
    self._execute_message(_message)
```

**快速定位核心操作技巧（L2:跳读）**  
- 搜索函数名：`relay`、`process_message`、`execute_cross_chain`、`bridge_transfer`
- 定位入口参数：包含 `block_hash`、`block_number`、`header` 的外部函数
- 追踪消息执行流：从接收到资金释放/铸造的完整路径

**快速定位保护机制技巧（L3:逐行读）**  
- 查找区块头验证：`verify_header`、`check_finality`、`validate_block`
- 检查轻客户端调用：是否依赖 `light_client.verify()`、存储的 `state_root`
- 确认延迟机制：`finalization_delay`、`challenge_period`、最小确认数
- 审查状态依赖：`finalized_blocks`、`trusted_relayers` 等存储变量

## Classify

**确认为漏洞**：目标链合约在执行资金操作前，完全无区块头验证或确认性检查，仅依赖 relayer 提交的参数，可直接伪造未确认交易。

**判定为误报**：  
1. 合约调用外部轻客户端合约进行区块头验证（需追踪确认轻客户端实现可靠）
2. 消息已通过可信预言机多签验证（需确认预言机去中心化程度）
3. 设计为私有链桥，源链和目标链由同一实体控制且在威胁模型外

**识别代码异味**：  
- 区块头验证逻辑存在但参数可配置为 0（如 `min_confirmations=0`）
- 仅验证格式正确性而非共识有效性（如只检查 `block_hash != empty(bytes32)`）
- 依赖单一 relayer 且无挑战期

## Low risk

1. **测试网或演示环境**：合约注释明确标注为非生产环境，资金量受限
2. **有效的经济惩罚机制**：relayer 需质押高额保证金，且存在欺诈证明窗口期能完全覆盖损失
3. **低价值资产桥接**：仅支持测试代币或限额极小（如单笔 < $100）
4. **冗余验证层**：链下监控系统实时对比源链状态，可暂停合约（需确认响应时间 < 区块最终确认时间）
5. **源链即时最终性**：源链本身具有即时最终性共识（如 BFT 链），且目标链已验证 BFT 签名集

## Audit Techniques

**深度审计检查清单**：

1. **区块头验证源头追踪**
   - 在合约中搜索 Merkle 根存储：`merkle_root[block_number]`、`block_headers[block_hash]`
   - 追踪轻客户端交互：检查是否存在 `lightclient_address`、`ILightClient` 接口调用
   - 跨合约验证链：确认轻客户端合约本身的区块头验证逻辑（常见坑：轻客户端未同步最新headers）
   - 验证 state root 的使用：必须确认 state root 来自已验证的区块头，而非任意输入

2. **Relayer 信任边界分析**
   - 提取所有 Relayer 权限相关操作：`onlyRelayer`、`authorized_relayers` 映射
   - 统计 Relayer 数量：单一 relayer（极高风险）vs 多签验证（需检查签名阈值≥2/3）
   - 检查 relayer 更新机制：是否存在 `add_relayer`/`remove_relayer` 入口点，权限控制是否严密
   - 寻找特殊权限提升路径：如 admin 是否能直接调用消息执行函数绕过验证

3. **真实漏洞表现特征**
   - **模式A**：区块头参数直接用于 Merkle 证明验证，无区块头自身有效性检查
     ```vyper
     # 风险：未检查 _block_header 是否为已确认区块
     def verify_proof(_block_header: bytes32, _proof: DynArray[bytes32, 10]) -> bool:
         return self._check_merkle(_block_header, _proof)  # 仅验证 Merkle，不验证 header 来源
     ```
   - **模式B**：finality_delay 参数可被调用者设置或为 0
     ```vyper
     def process_message(_message: Bytes[512], _finality: uint256):
         # 审计员可输入 _finality = 0，直接跳过延迟检查
         self._release_funds()
     ```
   - **模式C**：存储状态验证不完整，遗漏关键检查
     - 检查 `processed_messages` 映射：是否防止重复处理
     - 检查 `confirmed_blocks` 映射：是否真正存储并验证了区块头
     - 遗漏 nonce 或序列号检查，允许乱序处理

4. **常见误报陷阱与识别技巧**
   - **误报1**：合约中存在 `verify_header()` 函数名 → 易错认为已验证
     - 正确做法：追踪该函数实现，检查是否真的对 block_header 做了共识验证（不只是格式检查）
   - **误报2**：看到 `chainlink_oracle` 或 `price_feed` 接口调用 → 假设已验证链状态
     - 正确做法：预言机仅能提供价格数据，不能验证区块头有效性，需分别审查
   - **误报3**：存在 `challenge_period` 延迟参数 → 假设已有欺诈证明机制
     - 正确做法：检查是否真的实现了欺诈证明接口、是否能在延迟内撤销有问题的消息
   - **误报4**：注释说"轻客户端已通过审计" → 盲目信任
     - 正确做法：至少审查轻客户端的 header 同步逻辑（是否防止回滚、双花）

5. **对比审计技巧**（审计多链桥接合约时）
   - 对标成熟项目：与 Stargate、Across、IBC 等实现对比
   - 检查多签验证阈值：M-of-N 多签中 M 的设置（M < N/2 即风险）
   - 审查权限梯度：普通 relayer、验证者(validator)、管理员(admin) 的权限划分
   - 确认异构链差异：以太坊 PoW finality ≠ Cosmos BFT finality，不同链的最终确认时间需独立评估

6. **手工挖掘审计日志**
   - 追踪消息的完整生命周期：输入参数 → 存储状态 → 输出操作
   - 在关键操作前标记检查点：资金转账、状态修改、权限变更
   - 验证状态转移的一致性：confirm → release 每个环节的必要条件是否充分
   - 检查异常路径：如何处理验证失败、超时、或目标链回滚场景

## Real Cases & Lessons

**真实漏洞案例特征**：
- Nomad（2022）：未验证 Merkle root，允许任意证明被接受
- Ronin（2022）：跳过 validator 签名验证，直接接受消息
- Poly Network（2021）：轻客户端未验证公钥集合的权限变更

**判定要点**：是否存在能让攻击者伪造未在源链最终确认的消息，并在目标链成功执行的完整攻击路径
