# Rust CW721: Missing Token Info

## Details

CW721 NFT 合约未实现 token_info 查询函数或返回格式不符合标准，导致 NFT 市场、钱包和链上应用无法获取代币元数据。缺失的代币信息影响 NFT 的展示、交易和验证。

### 典型表现

**缺失 token_info 查询**
```rust
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    OwnerOf { token_id: String, include_expired: Option<bool> },
    ApprovedForAll { owner: String, operator: String, include_expired: Option<bool> },
    NumTokens {},
    ContractInfo {},
    // 缺失 TokenInfo 查询
    // 导致无法获取单个代币的元数据
}

pub fn query(deps: Deps, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::OwnerOf { token_id, .. } => { /* ... */ }
        // 缺失 QueryMsg::TokenInfo 分支
    }
}
```

**TokenInfo 返回格式不符标准**
```rust
// 标准应返回完整的代币信息
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct TokenInfoResponse {
    pub token_uri: Option<String>,
    // 缺失 extension 字段以支持自定义元数据
    // 缺失 owner 字段
}

// 或者返回类型完全错误
pub struct TokenInfoResponse {
    pub id: u64,         // 应为 String
    pub owner: Pubkey,   // 应为 String (Cosmos 地址)
    pub url: String,     // 应为 token_uri
}
```

**token_uri 字段缺失**
```rust
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct TokenInfo<T> {
    pub owner: Addr,
    pub approvals: Vec<Approval>,
    // 缺失 token_uri: Option<String>
    // 导致无法获取 NFT 的元数据 URI
}

// TokenInfo 查询返回不包含 URI
pub fn query_token_info(
    deps: Deps,
    token_id: String,
) -> StdResult<TokenInfoResponse> {
    let token = tokens.load(deps.storage, &token_id)?;
    Ok(TokenInfoResponse {
        owner: token.owner,
        approvals: token.approvals,
        // token_uri 未包含
    })
}
```

**token_metadata 结构不完整**
```rust
// 元数据结构过于简单或缺少关键字段
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Metadata {
    pub name: String,
    // 缺失 description
    // 缺失 image
    // 缺失 external_url
    // 缺失 attributes
}

// 或者与返回格式不一致
pub struct TokenInfoResponse {
    pub token_uri: Option<String>,
    pub metadata: Option<Metadata>,  // 混淆了 URI 和 metadata 概念
}
```

**Extension 字段处理错误**
```rust
// CW721 标准支持自定义扩展，但实现错误
pub struct TokenInfoResponse<T> {
    pub owner: Addr,
    pub token_uri: Option<String>,
    // extension 字段缺失或类型错误
}

// 泛型参数未正确使用
pub fn query_token_info(
    deps: Deps,
    token_id: String,
) -> StdResult<Binary> {
    let token = tokens.load(deps.storage, &token_id)?;
    // 缺失 extension 序列化
    to_json_binary(&TokenInfoResponse {
        owner: token.owner,
        token_uri: token.token_uri,
    })
}
```

**查询参数处理不当**
```rust
pub fn query_all_tokens(
    deps: Deps,
    start_after: Option<String>,
    limit: Option<u32>,
) -> StdResult<Binary> {
    // 缺失 limit 的默认值和最大值检查
    let limit = limit.unwrap_or(30);
    
    // 或者缺失 start_after 处理，导致分页失败
    let tokens = all_tokens()
        .range(deps.storage, None, None, Order::Ascending)
        .take(limit as usize)
        .collect::<Result<Vec<_>, _>>()?;
    
    to_json_binary(&TokensResponse { tokens })
}
```

## Classify

**风险等级**: HIGH

**影响范围**:
- NFT 市场无法显示完整信息
- 钱包无法展示代币元数据
- 链上验证和所有权追踪困难
- OpenSea 等通用市场不兼容
- 交易流动性受限

**审计关键词**:
- `QueryMsg::TokenInfo` - 验证是否存在
- `TokenInfoResponse` - 检查返回字段完整性
- `token_uri` 字段 - 应返回元数据 URI
- `extension` 字段 - 支持自定义元数据
- `owner` 字段 - 应包含代币所有者
- 分页查询 - start_after 和 limit 参数
- 返回类型一致性 - 与标准结构匹配

## Low risk

**受限实现情况**:
- 如果 NFT 合约仅用于特定应用内部使用，可能无需完整的 token_info
- 如果通过其他机制（如 IPFS 网关）提供元数据，可接受
- 但应在合约文档中明确说明限制

建议参照官方 CW721 标准实现，确保 token_info 查询返回完整且正确的元数据。
