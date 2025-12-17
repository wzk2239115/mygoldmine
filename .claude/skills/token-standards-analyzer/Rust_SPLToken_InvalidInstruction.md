# Rust SPL Token: Invalid Instruction

## Details

代币程序未正确处理 Transfer、Approve、Mint 等标准 SPL Token 指令，导致与 Solana 生态钱包和 DEX 不兼容。指令处理逻辑错误或缺失会导致交易失败和流动性问题。

### 典型表现

**缺失 Transfer 指令处理**
```rust
// 缺失处理标准的转账指令
pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    match TokenInstruction::unpack(instruction_data)? {
        // 缺失 TokenInstruction::Transfer 分支
        TokenInstruction::Approve { amount } => { /* ... */ }
        TokenInstruction::Mint { amount } => { /* ... */ }
        _ => Err(ProgramError::InvalidInstructionData),
    }
}
```

**缺失 Approve 指令处理**
```rust
// TokenInstruction::Approve 分支完全缺失
match instruction {
    TokenInstruction::Transfer { amount } => { /* ... */ }
    TokenInstruction::Mint { amount } => { /* ... */ }
    TokenInstruction::Burn { amount } => { /* ... */ }
    // 缺失 Approve 指令，无法进行授权转账
}
```

**Mint 指令处理逻辑错误**
```rust
TokenInstruction::Mint { amount } => {
    // 缺失权限检查
    mint_tokens(&mut token_account, amount)?;
    
    // 或者返回类型错误
    Ok(amount) // 应返回 Ok(())
}
```

**指令参数解析不正确**
```rust
// 参数字节偏移错误
pub fn unpack_transfer(input: &[u8]) -> Result<Transfer, ProgramError> {
    let amount = u64::from_le_bytes(
        // 字节范围错误，可能重叠或超界
        input[8..16].try_into()
            .map_err(|_| ProgramError::InvalidInstructionData)?
    );
    Ok(Transfer { amount })
}

// 缺失账户验证
TokenInstruction::Transfer { amount } => {
    // 未验证源账户、目标账户、授权人
    transfer_tokens(accounts, amount)?;
}
```

**账户签名验证缺失**
```rust
TokenInstruction::Approve { amount } => {
    let owner = &accounts[2];
    // 缺失检查 owner.is_signer
    approve_tokens(owner, spender, amount)?;
}

TokenInstruction::Mint { amount } => {
    let mint_auth = &accounts[1];
    // 缺失验证 mint_auth 是否已签名
    mint_tokens(mint_auth, amount)?;
}
```

## Classify

**风险等级**: HIGH

**影响范围**:
- 与标准 SPL Token 钱包不兼容
- DEX 无法正常运作
- 交易所集成困难
- 授权机制失效
- Solana 生态集成受阻

**审计关键词**:
- `TokenInstruction::Transfer` - 验证实现和权限检查
- `TokenInstruction::Approve` - 验证是否存在
- `TokenInstruction::Mint` - 验证权限和金额检查
- `TokenInstruction::Burn` - 验证实现
- `Instruction` 分派 - 检查所有分支覆盖
- 账户验证 - is_signer、is_writable 检查
- 参数解析 - 字节范围和顺序正确性

## Low risk

此缺陷属于结构性问题，不存在低风险情形。任何标准指令的缺失或错误都会导致互操作性问题。

建议审查所有指令处理逻辑，确保完整实现并通过官方 SPL Token 程序验证。
