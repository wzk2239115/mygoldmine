# Rust CW20: Missing Required Functions

## Details

CosmWasm CW20 代币合约未实现 transfer、send、burn 等必需的执行消息或 balance_of、token_info 等查询函数，导致合约无法在 Cosmos 生态中正常运作。缺失的核心功能影响代币的流动性和可用性。

### 典型表现

**缺失 transfer 消息处理**
```rust
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExecuteMsg {
    Send { contract: String, amount: Uint128, msg: Binary },
    Burn { amount: Uint128 },
    Approve { spender: String, amount: Uint128 },
    // 缺失 Transfer 消息
    // 导致无法进行基础的代币转账
}

pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::Send { .. } => { /* ... */ }
        ExecuteMsg::Burn { .. } => { /* ... */ }
        // 缺失 ExecuteMsg::Transfer 分支
    }
}
```

**缺失 send 消息处理**
```rust
pub enum ExecuteMsg {
    Transfer { recipient: String, amount: Uint128 },
    Burn { amount: Uint128 },
    // 缺失 Send 消息
    // 导致无法调用接收方合约的消息
}

// Send 消息支持跨合约转账并触发接收方回调
// 缺失此功能限制了代币的功能性
```

**缺失 burn 消息处理**
```rust
pub enum ExecuteMsg {
    Transfer { recipient: String, amount: Uint128 },
    Send { contract: String, amount: Uint128, msg: Binary },
    Approve { spender: String, amount: Uint128 },
    // 缺失 Burn 消息
    // 无法实现代币销毁机制
}

// Burn 消息参数定义错误
pub enum ExecuteMsg {
    Burn { amount: String },  // 类型错误，应为 Uint128
}
```

**缺失 balance_of 查询**
```rust
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    TokenInfo {},
    TotalSupply {},
    // 缺失 BalanceOf 查询
    // 导致钱包无法查询账户余额
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct BalanceResponse {
    pub balance: Uint128,
}

pub fn query(deps: Deps, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::TokenInfo {} => { /* ... */ }
        // 缺失 QueryMsg::BalanceOf 分支
    }
}
```

**查询函数返回类型错误**
```rust
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct TokenInfoResponse {
    pub name: String,
    pub symbol: String,
    pub decimals: u8,
    // 缺失 total_supply: Uint128
    // 缺失 owner 或 minter 字段
}

// 或者返回不必要的敏感信息
pub struct BalanceResponse {
    pub balance: Uint128,
    pub allowance: Uint128,  // 不应在 balance 查询中返回
}
```

**缺失关键执行检查**
```rust
pub fn execute_transfer(
    deps: DepsMut,
    from: String,
    to: String,
    amount: Uint128,
) -> Result<Response, ContractError> {
    // 缺失检查发送者是否已初始化账户
    // 缺失检查余额是否充足
    // 缺失检查接收地址有效性
    deps.api.addr_validate(&to)?;
    // ... 实现
    Ok(Response::default())
}
```

## Classify

**风险等级**: HIGH

**影响范围**:
- 代币基础功能无法使用
- 钱包兼容性问题
- DEX 和流动性协议无法集成
- Cosmos 生态互操作失败
- 合约无法部署到主网

**审计关键词**:
- `ExecuteMsg::Transfer` - 验证实现和余额检查
- `ExecuteMsg::Send` - 验证跨合约调用实现
- `ExecuteMsg::Burn` - 验证销毁逻辑
- `QueryMsg::BalanceOf` - 验证查询实现
- `QueryMsg::TokenInfo` - 检查返回字段完整性
- 权限检查 - 验证 sender、spender、owner 验证
- 消息处理 - 检查所有必需分支覆盖

## Low risk

此缺陷属于结构性问题，不存在低风险情形。任何核心消息或查询的缺失都会导致合约不可用。

建议参照官方 CW20 标准和参考实现，确保所有必需的消息和查询函数完整实现。
