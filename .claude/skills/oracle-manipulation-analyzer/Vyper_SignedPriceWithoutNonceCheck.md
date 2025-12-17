**Vyper - 签名价格无 Nonce 检查**  
常出现在基于 Vyper 编写的借贷协议、稳定币或期权合约中，接受链下签名的预言机价格数据但未验证 nonce，导致旧签名可被重放利用，攻击者可在价格波动时提交有利的过期价格。

## Details

对应代码示例：
```vyper
# 典型漏洞模式
@external
def update_price(_price: uint256, _timestamp: uint256, _signature: Bytes[65]):
    signer: address = self._recover_signer(_price, _timestamp, _signature)
    assert signer == self.trusted_oracle, "Invalid signer"
    assert _timestamp > block.timestamp - 300, "Price too old"
    self.latest_price = _price  # ❌ 未检查 nonce，同一签名可重放
```

**快速定位核心操作（L2-跳读）：**  
搜索 `ecrecover`、`recover_signer`、`verify_signature` 等签名验证函数，定位到价格更新入口；检查函数参数是否包含递增标识（nonce/sequence/counter），若仅有 price + timestamp 则存在重放风险。

**快速定位保护机制（L3-逐行读）：**  
在签名验证后查找 `self.used_nonces[nonce] = True` 或 `assert self.last_nonce < nonce` 等防重放逻辑；检查是否存储每个签名的哈希到映射表 `self.consumed_signatures: HashMap[bytes32, bool]`；若仅校验 timestamp 而无单调性保证，则防护失效。

## Classify

**确认漏洞：**  
- 签名消息体仅包含 (price, timestamp) 无唯一标识，且无历史签名记录
- 存在经济动机：价格波动大于交易成本，攻击者可通过重放获利
- 关键操作（清算、铸币、借贷）直接依赖该价格源

**误报情况：**  
- 签名已包含 chain_id、contract_address、nonce，仅代码未显式命名为"nonce"
- 存在链下聚合器定期轮换密钥，旧签名因 signer 地址失效无法重放
- 价格更新频率极高（<12秒）且有严格时间窗口（如5秒），经济上无利可图

**代码异味：**  
- timestamp 校验过松（如允许1小时内价格），虽有时间限制但窗口内可重放

## Low risk

**低风险场景：**
- 价格仅用于展示或统计，不影响资产转移和权限变更
- 协议设计为多源聚合，单一签名价格需与其他3+独立源加权计算，重放单个源影响<10%
- 存在全局断路器：单次价格偏离超阈值自动暂停系统，需多签恢复
- 时间窗口≤1个区块时间且价格更新gas补偿充足，keeper主动更新使旧签名无经济价值
- 测试网或仅限白名单用户的早期版本，资金规模<$10k

## 审计专业技巧

### 1. 签名消息结构逆向分析
**关键技巧：** 不能仅通过搜索"nonce"字符串判断，需深度追踪签名哈希的计算过程。
```vyper
# ❌ 看似没有nonce，但需检查_message具体内容
def _recover_signer(_message: bytes32, _signature: Bytes[65]) -> address:
    return ecrecover(_message, _signature)

# 必须回溯_message的来源
def update_price(_price: uint256, _timestamp: uint256, _nonce: uint256, _signature: Bytes[65]):
    message: bytes32 = keccak256(concat(
        self.contract_address,  # chain binding
        self.chain_id.to_bytes(32, 'big'),
        convert(_price, bytes32),
        convert(_timestamp, bytes32),
        convert(_nonce, bytes32)  # ✅ 隐式存在，但需逆向确认
    ))
```
**专业做法：** 追踪所有`keccak256()`调用，理清输入参数的完整列表。误报案例：某些团队将nonce编码在签名本身或通过链下信号传递，代码中看不见但防护有效。

### 2. 时间窗口 vs 重放风险的经济学分析
**真实漏洞判断：** 不能机械地以时间窗口长短定性，需考虑价格波动性与交易成本。
```vyper
# 同样的时间检查，风险级别不同
# 场景A：高波动稳定币（ETH/stETH利差）+ 大额清算
if block.timestamp - _timestamp > 300:  # 5分钟窗口
    raise "Price too old"
# ❌ 高风险：5分钟可能出现3-5%价格波动，$100M TVL协议可被清算

# 场景B：低波动指数（CPI通胀指数）+ 小额流动性
if block.timestamp - _timestamp > 3600:  # 1小时窗口
    raise "Price too old"
# ✅ 低风险：通胀指数24小时内波动<0.1%，即使重放也无利可图
```
**审计经验：** 需要查看合约部署的实际场景：是稳定币（波动率100-300bp）、衍生品（1000bp+）还是权益资产（500bp）。

### 3. 多签名链式验证的陷阱识别
**常见误报点：** 出现多个签名校验函数时，需识别是否存在**验证逻辑短路**。
```vyper
def _verify_multi_price(prices: DynArray[uint256, 3], signatures: DynArray[Bytes[65], 3]):
    signers: DynArray[address, 3] = []
    for i in range(3):
        signer: address = self._recover_signer(prices[i], signatures[i])
        # ❌ 陷阱：if检查后没有assert，允许无效签名通过
        if signer == self.oracle_1 or signer == self.oracle_2 or signer == self.oracle_3:
            signers.append(signer)
    # 如果只有1个有效签名也能进行，则防护失效
    if len(signers) >= 1:
        self.latest_price = prices[0]
```
**正确做法：** 追踪`required_signatures`计数与实际验证数的关系，确保阈值硬编码且不可绕过。

### 4. 边界情况中的隐性重放
**真实案例：** Nonce校验存在但仅用于特定路径，其他入口缺失保护。
```vyper
def update_price_standard(_price: uint256, _nonce: uint256, _signature: Bytes[65]):
    # ✅ 完整保护
    assert self.last_nonce < _nonce, "Nonce not increasing"
    self.last_nonce = _nonce

def update_price_emergency(_price: uint256, _signature: Bytes[65]):
    # ❌ 紧急模式跳过nonce检查
    assert self._is_emergency_signer(...)
    self.latest_price = _price  # 无防护！
```
**审计技巧：** 搜索所有修改`latest_price`或关键状态的外部函数，确保防护机制覆盖所有路径。

### 5. 链上交互证据的挖掘
**高级检测：** 不依赖代码静态分析，而是通过历史交易寻找重放证据。
- 查询事件日志是否存在**相同的price + timestamp + signature组合**被多次提交
- 检查`update_price()`调用频率：若30天内某签名被调用20次，强烈表明存在重放
- 对比不同区块的`latest_price`变化：若价格在5秒内反复闪现同一数值后又回退，可能是重放被中断

### 6. 真实漏洞vs误报的决策树

| 判断点 | 高风险信号 | 误报信号 |
|--------|-----------|---------|
| **Nonce结构** | 完全缺失；仅校验timestamp | chain_id+contract_address+sequence在签名体中隐式存在 |
| **时间窗口** | >1小时；无预言机主动更新机制 | <1区块；keeper有奖励激励立即更新 |
| **经济激励** | TVL>$10M；价格波动率>300bp | TVL<$1M；价格波动率<50bp；清算触发条件严苛 |
| **防护深度** | 仅timestamp；无消费记录表 | 多层验证（oracle集合+断路器+超额抵押） |
| **历史证据** | 链上多笔交易重放同一签名 | 未观测到重复提交 |

## 最佳实践修复

```vyper
@external
def update_price(_price: uint256, _timestamp: uint256, _nonce: uint256, _signature: Bytes[65]):
    # 1. 时间有效性
    assert _timestamp > block.timestamp - 60, "Price too old"

    # 2. Nonce单调性
    assert _nonce > self.last_nonce, "Nonce must increase"

    # 3. 签名验证（包含完整消息）
    message: bytes32 = keccak256(concat(
        convert(self, bytes20),
        convert(self.chain_id, bytes32),
        convert(_price, bytes32),
        convert(_timestamp, bytes32),
        convert(_nonce, bytes32)
    ))
    signer: address = ecrecover(message, _signature)
    assert signer == self.oracle, "Invalid signature"

    # 4. 消费记录（防多签场景中的混淆）
    assert not self.consumed_nonces[_nonce], "Nonce already used"
    self.consumed_nonces[_nonce] = True

    # 5. 更新状态
    self.last_nonce = _nonce
    self.latest_price = _price
    log PriceUpdated(_price, _timestamp, _nonce)
```
