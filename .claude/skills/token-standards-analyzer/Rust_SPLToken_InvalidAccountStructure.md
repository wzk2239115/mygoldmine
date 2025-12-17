# Rust SPL Token: Invalid Account Structure

## Details

代币账户数据结构不符合 SPL Token 标准布局，导致链上数据解析失败。账户状态、Mint 数据、权限字段的定义错误会导致与标准客户端库和钱包不兼容。

### 典型表现

**账户数据布局不匹配**
```rust
// 标准布局应为: mint (32) + owner (32) + amount (8) + decimals (1) + ...
#[derive(Serialize, Deserialize, Clone)]
pub struct TokenAccount {
    pub owner: Pubkey,  // 顺序错误，应在 mint 之后
    pub mint: Pubkey,   // 应为第一个字段
    pub amount: u64,
    pub state: AccountState,
}

// 错误的字段顺序导致反序列化失败
pub fn unpack_account(data: &[u8]) -> Result<TokenAccount, ProgramError> {
    // 按错误的字节偏移解析
    let owner = Pubkey::new(&data[0..32]);
    let mint = Pubkey::new(&data[32..64]);
    // 与实际内存布局不符
}
```

**Mint 字段定义错误**
```rust
#[derive(Serialize, Deserialize)]
pub struct Mint {
    pub mint_authority: Option<Pubkey>,
    pub supply: u64,
    pub decimals: u8,
    // 缺失 is_initialized
    // 缺失 freeze_authority
}

// 反序列化时出错
pub fn unpack_mint(data: &[u8]) -> Result<Mint, ProgramError> {
    if data.len() < 82 {  // 标准 Mint 为 82 字节
        return Err(ProgramError::InvalidAccountData);
    }
    // 字段大小计算错误
}
```

**Owner 字段缺失**
```rust
#[derive(Serialize, Deserialize)]
pub struct TokenAccount {
    pub mint: Pubkey,
    pub amount: u64,
    pub delegated_amount: u64,
    // 缺失 owner: Pubkey 字段
    pub state: AccountState,
}

// 导致无法确定代币所有者
pub fn get_owner(account: &TokenAccount) -> Result<Pubkey, ProgramError> {
    Ok(account.owner)  // 字段不存在
}
```

**Account State 字段类型不正确**
```rust
// 应为 u8 枚举，表示 Uninitialized(0) / Initialized(1) / Frozen(2)
#[derive(Serialize, Deserialize)]
pub struct TokenAccount {
    pub mint: Pubkey,
    pub owner: Pubkey,
    pub amount: u64,
    pub state: bool,  // 错误: 应为 AccountState 枚举
}

// 或者状态值范围错误
pub enum AccountState {
    Uninitialized = 0,
    Initialized = 2,  // 错误: 应为 1
    Frozen = 3,       // 错误: 应为 2
}
```

**缺失必需字段**
```rust
#[derive(Serialize, Deserialize)]
pub struct TokenAccount {
    pub mint: Pubkey,
    pub owner: Pubkey,
    pub amount: u64,
    // 缺失 state: AccountState
    // 缺失 is_native: bool
    // 缺失 delegated_amount: u64
    // 缺失 delegate: Option<Pubkey>
}

// 序列化大小不符
pub fn validate_account_size(account: &AccountInfo) -> ProgramResult {
    if account.data_len() != 165 {  // 标准大小
        return Err(ProgramError::InvalidAccountData);
    }
    Ok(())
}
```

## Classify

**风险等级**: HIGH

**影响范围**:
- 客户端库无法反序列化账户
- 钱包余额查询失败
- 链上数据验证失败
- SPL Token 程序互操作失败
- 交易解析错误

**审计关键词**:
- `struct TokenAccount` - 验证字段顺序和大小
- `struct Mint` - 确认 165 字节大小和所有字段
- `mint` 字段 - 应为第一个 32 字节 Pubkey
- `owner` 字段 - 应为第二个 32 字节 Pubkey
- `amount` 字段 - 应为 8 字节 u64
- `state` 字段 - 应为 u8 AccountState 枚举
- 字节偏移计算 - 确认与标准一致
- 序列化大小 - TokenAccount 165 字节、Mint 82 字节

## Low risk

此缺陷属于结构性问题，不存在低风险情形。任何账户数据结构不符都会导致互操作性失败。

建议使用官方 spl-token crate 中的数据结构定义，严格遵循标准布局。
