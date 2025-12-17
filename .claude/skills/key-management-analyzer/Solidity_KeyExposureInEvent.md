# Solidity_KeyExposureInEvent

**漏洞概述**  
密钥材料或敏感信息通过 `event` 记录在链上，导致永久可见。常见于钱包代理、多签控制器、链下签名验证、升级权限控制等场景。

## Details

**代码示例**：
```solidity
event KeyRotation(address indexed signer, bytes32 privateKey); // 私钥暴露
event SignerUpdate(bytes memory secretSeed); // 种子暴露
event AuthConfig(string apiKey, bytes encryptedKey); // 敏感信息暴露

function updateSigner(bytes32 newKey) external {
    signerKey = newKey;
    emit KeyRotation(msg.sender, newKey); // 密钥直接记录到事件
}
```

**快速定位核心操作**（L1-L2）：
- **L1关键词扫描**：搜索 `event` 定义，关注参数类型为 `bytes32/bytes/string` 且命名包含 `key/private/secret/seed/mnemonic/signature/auth/credential` 的事件
- **L2跳读**：检查 `emit` 语句，确认是否传递了密钥派生输入、私钥哈希前的原始值、签名材料、API密钥、加密种子等

**快速定位保护机制**（L2-L3）：
- **L2跳读**：查找事件参数是否仅记录公钥、地址、哈希摘要（如 `keccak256(key)`）而非原始密钥
- **L3逐行读**：验证在 `emit` 前是否对敏感数据进行了不可逆转换（如哈希、承诺方案），确认转换后数据无法反推原始密钥
- **L3逐行读**：检查是否使用 `indexed` 修饰符存储敏感数据（虽然不能解决暴露问题，但会影响日志查询方式）

## Classify

**漏洞判定依据**：
- 事件参数直接记录私钥、助记词、未哈希的种子、加密密钥原文 → 严重漏洞
- 事件记录可反推密钥的中间值（如熵源、部分私钥） → 高危漏洞
- 记录密钥的可逆加密形式但密钥硬编码在合约中 → 高危漏洞

**误报识别**：
- 事件仅记录公钥、地址、签名结果（不含 `r/s/v` 原始值可重放的场景）
- 记录的是经过 `keccak256` 等不可逆哈希后的密钥摘要
- 记录的是密钥承诺（commitment）而非密钥本身

**代码异味**：
- 事件记录加密后的密钥但解密密钥通过链下安全管理
- 事件命名暗示敏感性（含 `Secret/Private`）但实际记录的是公开数据

## Low risk

**降级为低风险的场景**：
- 事件记录的是测试网/演示环境的模拟密钥，且有明确注释说明
- 密钥已过期失效且合约包含密钥轮换机制，事件仅用于历史审计
- 记录的是对称加密密钥的公钥部分（在非对称密钥交换场景）
- 合约明确标注为教学示例且未部署到主网
- 记录的密钥材料已通过时间锁或多签保护，且在事件记录前已失效

## 审计专业技巧

### 真实漏洞识别要点

**1. 链下密钥直接上链的场景**
- 检查 `event` 是否包含 `emit` 了用户输入的密钥参数
- 搜索函数签名中含有 `bytes32 key / privateKey / secret` 的参数，追踪这些参数是否被记录到事件
- 关键词搜索：`emit` 后跟随 `private/secret/seed` 相关变量名，高概率表示密钥暴露
- **真实案例**：Bancor 合约在 `updateFrozenAccount()` 中意外记录了用户的私钥相关信息到日志

**2. 多签/控制器场景的加密密钥暴露**
- 当合约涉及多个签名者时，检查 `emit` 中是否暴露了签名预像（`preimage`）或中间签名材料
- 审查事件是否记录了 Merkle 树的完整路径或中间节点（可能导致私钥推导）
- **识别方法**：查找 `HashChainUpdate / SignatureAdded / KeyApproved` 等事件，确认参数是否包含未哈希的签名分片

**3. 预言机价格信息与密钥混淆的陷阱**
- 某些合约在记录"加密参数"时，实际混淆了加密密钥与公开数据
- 检查参数命名是否有误导性：例如 `encryptedValue` 实际上是明文，`hashOfKey` 实际上存储了可反推的值
- 使用密钥推导函数（KDF）前的原始 salt/nonce 被记录到事件，虽然不是密钥但可能允许彩虹表攻击

**4. 跨链桥接合约的密钥暴露**
- Bridge 合约在 `emit CrossChainTransfer()` 时可能记录了签名器的绑定密钥
- 检查是否有 `ValidatorKeyUpdate / RelayerAuthUpdate` 事件记录了原始 ECDSA 密钥而非公钥
- **实战技巧**：对比 Mainnet 和 Testnet 的同一事件，若参数值不同可能存在硬编码密钥

### 常见误报场景

**1. 哈希值与原始密钥的混淆**
```solidity
event KeyDigest(bytes32 digest);  // 这是 keccak256(privateKey) 的哈希，不是漏洞

// 正确的审计流程：
// ✗ 错误判定：看到 "Key" 字眼立即标记为漏洞
// ✓ 正确做法：检查 emit 前是否执行了不可逆转换
```

**2. 公钥与私钥的区分失误**
- `event SignerAdded(bytes32 indexed publicKey)` 中的 `publicKey` 虽然含有 "Key"，但本身是公开信息
- **区分方法**：检查事件参数是否出现在 `mapping(bytes32 => address)` 这样的公开查询中

**3. 签名值与签名原材料的混淆**
```solidity
// 这不是漏洞：只记录了签名的结果
event Signed(bytes32 transactionHash, bytes signature);

// 这才是漏洞：记录了签名材料
event SignatureGenerated(bytes32 nonce, bytes32 randomness, bytes privateKeyFragment);
```

**4. 已失效密钥的重新激活陷阱**
- 合约使用了旧密钥，审计师认为 "已失效" 可以降级风险
- **审查要点**：搜索 `mapping(bytes32 => bool) isKeyActive` 并追踪状态变化，确保密钥确实被标记为 `false`
- 检查是否存在 `enableKey() / restoreKey()` 等恢复函数，允许重新激活已失效密钥

### 审计检查清单

| 检查项 | 高风险信号 | 低风险信号 |
|--------|-----------|----------|
| **事件参数类型** | `bytes/bytes32` 命名包含 key/secret | `address` 或 `bytes32` 但已哈希 |
| **emit 前处理** | 直接传递参数 | `keccak256(value)` 或 `commit(value)` |
| **参数来源** | 函数参数或 storage 中的敏感数据 | 常量或经过安全初始化的值 |
| **事件可见性** | public 默认，所有人可查询 | 若为 `internal event` 则风险降低（稀有） |
| **时间上下文** | 密钥在事件记录后仍被使用 | 密钥已过期，有明确注释说明 |

### 实战审计技巧

**快速判断流程**：
1. 搜索所有 `event` 定义，标记含有 `key/secret/private/seed/auth/credential` 的参数
2. 对每个可疑事件，找到其 `emit` 语句（通常在函数体中）
3. 查看 emit 前是否进行了 `keccak256()` 或其他单向函数转换
4. 检查函数调用链：这个 `emit` 来自哪个函数，参数是否来自用户输入
5. 搜索 `event` 名称在测试文件或文档中的含义，确认是否真正代表密钥

**常见误判修正**：
- 看到 `emit KeyRotation(address signer, bytes32 hashedKey)` 时，不要急着标记漏洞
- 用 `bytes32 result = keccak256(abi.encodePacked(hashedKey))` 追踪数据流，确认无法反向推导
- 在 exploit 阶段尝试从事件日志反推原始密钥，若不可行则降级为低风险
