# Rust_KeyMaterialInLog - 日志中的密钥材料泄露

**Rust**（适用于智能合约如 Solana 程序或 Off-chain 服务）  
密钥或种子在调试日志、错误信息、trace输出中暴露，可能被日志系统持久化、远程收集或被未授权访问者获取。

## Details

**典型代码模式：**
```rust
// 危险：直接打印私钥/种子
let keypair = Keypair::generate(&mut OsRng);
println!("Generated keypair: {:?}", keypair);
log::debug!("Signing key: {}", hex::encode(&signing_key.to_bytes()));

// 危险：结构体派生Debug自动暴露敏感字段
#[derive(Debug)]
struct Wallet {
    private_key: [u8; 32],
    seed_phrase: String,
}
```

**快速定位核心操作（L2-L3）：**
- 关键搜索词：`println!`、`log::`、`debug!`、`info!`、`trace!`、`eprintln!`、`format!`、`write!`
- 跳读审计点：密钥生成/加载函数后的日志语句、错误处理分支中的日志输出
- 敏感类型：`Keypair`、`SecretKey`、`PrivateKey`、`[u8; 32/64]`、`seed`、`mnemonic`、`private_*`变量
- 危险派生宏：结构体上同时有 `#[derive(Debug)]` 和敏感字段

**快速定位保护机制（L1-L2）：**
- 关键词扫描：`SecretString`、`Zeroize`、`SecretVec`、`#[serde(skip)]`、自定义 `Debug` 实现
- 保护模式识别：
  ```rust
  // 正面：自定义Debug隐藏敏感字段
  impl std::fmt::Debug for Wallet {
      fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
          write!(f, "Wallet {{ private_key: [REDACTED] }}")
      }
  }
  
  // 正面：条件编译仅在测试时输出
  #[cfg(test)]
  log::debug!("Key material: {:?}", key);
  ```
- 审计路径：若无 `impl Debug`、无 `#[cfg(test)]` 保护、无脱敏函数包装 → 高风险

## Classify

**漏洞判定标准：**
- **确认漏洞**：生产环境下将私钥/种子/助记词的原始值输出到日志、标准输出/错误流；使用 `{:?}` 格式化含敏感字段的结构体且无自定义 `Debug` 实现；错误处理中直接 `format!("{:?}", error)` 传递包含密钥的错误类型。
- **误报场景**：日志输出仅限于测试代码（`#[cfg(test)]`）；输出的是公钥、地址或密钥派生路径（非私钥本身）；输出前已通过 `&key[..4]` 截取、哈希摘要、或脱敏函数处理。
- **代码异味**：日志级别设置为 `trace!` 且理论上生产环境禁用，但缺乏编译期保证；日志输出包含中间密钥材料（如 seed 的 hash，虽非原始种子但可能辅助攻击）。

**上下文研判要点：**
- 检查日志配置文件：是否在生产环境启用 Debug/Trace 级别
- 追踪日志收集器：是否将日志发送到第三方服务（增加泄露面）
- 评估结构体生命周期：若密钥材料仅在初始化时短暂日志输出，风险高于运行时周期性输出（后者更易被监控捕获）

## Low risk

**降级条件：**
- **隔离环境**：代码仅在完全隔离的开发环境运行，且日志系统无外部可达性（如断网的测试机）。
- **临时调试**：代码位于明确标记为临时调试的分支/commit（需人工确认不会合并到主线）。
- **加密日志管道**：日志在写入前已加密，且解密密钥由独立的密钥管理系统控制（极少见于实际实现）。
- **非关键密钥**：泄露的是短期会话密钥且具有严格的时效性（如仅5分钟有效且已过期），但需评估时间窗口内的实际风险。

**注意：** Rust 区块链项目（尤其 Solana 程序）中，即使是 `cfg(test)` 保护的代码，若测试日志被 CI 系统持久化到公开日志，仍构成风险。审计时需验证 CI 配置是否正确处理敏感日志。

## 审计专业技巧

### 1. 真实漏洞特征识别

**高可信度漏洞信号（99% 确认）：**
- **原始十六进制字符串在生产日志**：发现 `log::info!("secret: {}", hex::encode(&key))` 且外层无 `#[cfg(test)]`、无条件编译、无环境变量控制 → 确认漏洞。实际审计案例：某 Solana program 在 `invoke_signed` 前输出了完整的 Keypair 调试信息，导致私钥在 RPC 节点日志中暴露。
- **Debug 派生与敏感结构体组合**：`#[derive(Debug, Serialize)]` 修饰包含 `[u8; 32]` 私钥字段的结构体，且：
  - 结构体被传入日志宏（`debug!("{:?}", wallet)`）
  - 结构体在错误枚举中被包装（如 `enum Error { KeyError(Wallet) }`）
  - 结构体被 Serde 序列化到日志（常见于 `serde_json::to_string`）
- **错误链中的密钥泄露**：使用 `anyhow::Error` 或 `thiserror` 时，若自定义错误类型包含原始密钥，`Display` 实现会将其打印。例如 `SigningError(SigningKey)` 被 `?` 传播后日志打印错误链。
- **条件编译缺失的日志**：代码中出现 `// TODO: remove debug log` 注释，或日志级别在代码审查中被提到需要降级但未实施。

**中等可信度信号（50-80% 需要上下文）：**
- **trace! 宏输出敏感信息**：虽然 `trace!` 默认关闭，但需验证：
  - 项目 `Cargo.toml` 中是否定义了 `release` profile 的日志过滤
  - CI/CD 环节是否曾临时开启 trace 进行调试
  - 某些 Solana RPC endpoint（如 Helius）支持 `commitment=debug`，可能绕过日志级别限制
- **Zeroize 使用不完整**：代码导入了 `zeroize` 但仅在某些分支使用，其他分支漏掉 `.zeroize()` 调用。需判断：
  - 是否所有含密钥的分支都 zeroize？
  - Zeroize 是否在栈变量超出作用域前执行？（否则编译器可能优化掉）
- **公钥误认为敏感**：输出 Base58 编码的公钥被误报为漏洞，需根据上下文判断该项目是否有"公钥保密"的业务需求。

### 2. 常见误报模式与排除法

**误报 Pattern 1 - 派生路径与哈希混淆：**
```rust
// 误报示例（实际安全）
log::info!("Derived path: m/44'/501'/0'/0'{}'", index);
log::debug!("Key hash: {}", sha256(&public_key));
// 原因：派生路径信息本身不足以恢复密钥；公钥哈希不可逆
```
**排除法**：检查输出是否包含完整的 `[0-9a-f]{64}` 或 `[0-9a-f]{128}` 的十六进制串（对应 256bit 或 512bit 密钥），而非派生指数或摘要。

**误报 Pattern 2 - 短期会话密钥：**
```rust
// 理论上更低风险（但需确认）
log::debug!("Session token: {}", session_key_with_5min_ttl);
// 排除法：
// 1) 确认代码中是否存在 TTL 检查与过期机制
// 2) 验证会话密钥是否由主密钥独立派生（单点失效）
// 3) 评估 5 分钟内的链上转账或签名能做什么
```
在区块链场景中，即使是 5 分钟也可能完成多笔交易，建议仍作为高风险对待。

**误报 Pattern 3 - 测试框架日志隔离：**
```rust
#[cfg(test)]
mod tests {
    #[test]
    fn test_signing() {
        log::debug!("Key: {:?}", private_key);  // 真的只在测试运行
    }
}
// 排除法：
// 1) 验证 #[cfg(test)] 确实限制编译（使用 `cargo build --release` 验证二进制大小，确认测试模块未被包含）
// 2) 检查 tests/ 目录下的集成测试是否也被同样保护
// 3) 最关键：验证 CI/CD 日志是否真的没有捕获测试输出
```
实际案例：某项目在 GitHub Actions 中使用 `-- --nocapture` 运行测试，导致所有日志（含 debug 级别）被上传到 artifact。

**误报 Pattern 4 - Display vs Debug 实现：**
```rust
impl Display for SecureKey {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        write!(f, "SecureKey[***]")  // 安全的 Display
    }
}
// 但若结构体同时 derive Debug，format! 可能优先使用 Debug
// log::info!("{}", key);  // 使用 Display，通常安全
// log::info!("{:?}", key);  // 使用 Debug，可能泄露
```
**排除法**：区分日志宏的格式说明符，并检查是否有其他代码路径隐式调用 Debug。

### 3. 跨文件关联审计

**关键审计点：**
1. **日志配置文件审计**（Cargo.toml、log4rs.yaml、tracing-subscriber 配置）：
   - 搜索 `env_logger::Builder::from_default_env()` 或 `LevelFilter::Debug/Trace`
   - 检查是否存在 `RUST_LOG=debug` 的默认启用
   - 验证 release build 中日志级别是否自动降级

2. **错误类型定义审计**：
   - 搜索所有 `#[derive(Debug)]` 的错误枚举
   - 检查是否存在包含密钥相关数据的 variant（如 `KeyDerivationFailed(Vec<u8>)`）
   - 验证是否有自定义的 `fmt::Display` 实现来隐藏敏感字段

3. **依赖库版本审计**：
   - 某些旧版本的 `solana-sdk` 或 `anchor-lang` 会在库内部日志输出密钥信息
   - 例：`solana-sdk < 1.9.0` 在 `rpc_client` 错误路径中暴露完整签名请求

4. **CI/CD 管道审计**：
   ```yaml
   # 危险示例
   - name: Run tests
     run: cargo test -- --nocapture  # 会捕获所有 println! 和日志

   # 安全示例
   - name: Run tests
     run: cargo test --release
     env:
       RUST_LOG: warn  # 或完全不设置，使用 off 级别
   ```

### 4. 区块链特定审计角度

**Solana program 特有陷阱：**
- Program 日志通过 `msg!` 宏发送到链上日志：`msg!("Secret: {}", hex::encode(&key))` 会永久记录在区块链上
- Anchor 框架的 `event!` 宏可能导致结构体被序列化到日志
- 本地验证器（`solana-test-validator`）会在 STDOUT 中打印所有 program 日志，若未使用 `--quiet` 会被 CI 捕获

**钱包/密钥管理特定：**
- 检查钱包导入/导出函数是否在操作前后输出调试信息
- 验证助记词恢复流程是否涉及日志输出
- 审计密钥派生函数（BIP32 等）的中间计算是否暴露

### 5. 实战审计工作流

**精准定位策略（10分钟快速审计）：**
1. 搜索所有 `log::` 和 `println!` 调用（Ctrl+F）
2. 对每个结果，识别被输出的变量名或表达式
3. 回溯变量定义，检查是否包含 `key`、`secret`、`private`、`seed` 等关键词
4. 检查该输出是否被 `#[cfg(test)]` 或其他条件编译保护
5. 若涉及结构体，检查该结构体是否 derive Debug 且无自定义实现

**深度审计验证（如标记为高风险需二次确认）：**
```bash
# 1. 编译并检查二进制中是否包含字符串
cargo build --release
strings target/release/program | grep -i "generated\|secret\|key"

# 2. 运行程序并重定向所有输出到文件
./target/release/program 2>&1 | tee output.log

# 3. 检查日志文件
grep -E "[0-9a-f]{64}" output.log  # 寻找 256bit 十六进制串
```

**误报确认清单：**
- [ ] 该日志输出是否在 `#[cfg(test)]` 或 `#[cfg(debug_assertions)]` 中？
- [ ] 被输出的值是否来自非生产代码路径（如错误处理中的 panic）？
- [ ] 输出的是否是公钥、地址或派生路径而非私钥本身？
- [ ] 项目是否有明确的日志级别管理策略（release profile 中禁用 debug）？
- [ ] CI/CD 日志是否被保存和访问？若访问受限则风险大幅降低
