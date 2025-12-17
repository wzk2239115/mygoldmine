# Rust 跨链调用上下文泄露

**漏洞类型：** 跨链桥接层权限隔离缺陷  
**影响范围：** Substrate pallet、Solana 跨链程序、中继器服务

## Details

### 典型代码特征

**Substrate Pallet 示例：**
```rust
// 漏洞：跨链调用时直接使用来源上下文
pub fn execute_remote_call(origin, remote_msg: Vec<u8>) -> DispatchResult {
    let caller = ensure_signed(origin)?;  // 本地签名者
    let decoded = decode_message(remote_msg)?;
    // 危险：使用 caller 作为跨链操作的执行者
    Self::transfer(caller, decoded.to, decoded.amount)?;
}

// 漏洞：未隔离跨链调用的存储上下文
impl CrossChainExecutor {
    fn execute_bridge_tx(&mut self, tx_data: BridgeTx) {
        // 直接在当前上下文执行，可能污染本地状态
        Self::dispatch(tx_data.target, tx_data.calldata);
    }
}
```

### 定位核心操作技巧（L3：逐行读）

**关键检查点：**
1. **Origin 传递链路** - 追踪 `origin` 参数在跨链调用中的流动，重点看：
   - `ensure_signed()` 后是否直接用于权限判断
   - `frame_system::ensure_root()` 是否可被跨链消息触发
   - `RawOrigin::Signed(account)` 是否混用本地和远程账户

2. **上下文切换边界** - 检查跨链执行点：
   - `pallet::call` 函数入口处是否创建隔离上下文
   - `execute_*` / `dispatch_*` 方法是否使用 `with_transaction` 或专用 origin
   - Solana 的 `invoke_signed()` 是否正确设置 PDA seeds

3. **状态读写作用域** - 扫描存储操作：
   - 跨链写入是否标记来源链 ID（如 `ChainId::get()`）
   - 是否使用双映射隔离不同链的状态（`StorageDoubleMap<ChainId, ...>`）

### 定位保护机制技巧（L2：跳读）

**保护模式识别：**
1. **专用 Origin 类型**（正向标记）  
   - 搜索 `pub enum CrossChainOrigin` 或 `RawOrigin::CrossChain`
   - 检查是否有 `ensure_cross_chain_origin()` 自定义鉴权
   - 确认跨链调用是否强制使用 `OriginFor<T>::none()` 或特殊标记

2. **上下文隔离层**（正向标记）  
   - 查找 `with_bridged_context()` / `IsolatedExecutor` 类模式
   - 检查是否使用 `sp_io::storage::start_transaction()` 包裹跨链执行
   - Solana 中是否通过 CPI guard（`invoke_signed` 的 signer_seeds）隔离

3. **缺失保护**（负向标记）  
   - 跨链函数入口直接调用 `ensure_signed` 且无后续验证 → 危险
   - 全局可变状态在跨链调用中直接修改 → 潜在污染
   - 无 `ReentrancyGuard` 且存在跨链回调 → 可能重入

## Classify

### 判定为漏洞的条件
- **权限提升可达性：** 外部跨链消息可触发本地特权操作（如 root call、资产铸造）且无独立校验
- **状态污染可证：** 跨链调用可修改非预期的本地存储域，导致共识不一致
- **身份混淆可利用：** 本地账户身份可被跨链消息伪造，绕过本地访问控制

### 判定为误报的情况
- 跨链 origin 虽未显式隔离，但通过业务逻辑强制校验（如白名单合约地址）
- 仅记录日志或非关键状态的上下文混用
- 存在外层 relayer 签名验证机制，且密钥管理安全

### 代码异味标准
- 上下文传递层级 >3 层，需跨模块追踪才能确认安全性
- 存在跨链调用但未统一使用 Origin 抽象，存在未来引入漏洞风险
- 文档中声称隔离但代码实现不明确

## Low risk

### 低风险场景
1. **仅查询操作：** 跨链调用仅读取状态不修改（如 `get_balance()`），且无 view 函数副作用
2. **双重验证存在：** 虽有上下文泄露路径，但存在：
   - 多签 threshold 拦截（需 N/M 签名）
   - 时间锁延迟执行（允许紧急暂停）
   - 金额/频率硬编码上限
3. **降级影响域：** 上下文泄露仅影响测试链或沙盒环境，主网有不同实现
4. **经济不可行：** 利用成本（如跨链手续费）远超可获利益
