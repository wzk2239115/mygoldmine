# Solidity 硬编码私钥漏洞

**漏洞场景**  
常出现在钱包代理、多签控制器、链下签名验证、升级权限控制等业务逻辑实现中。私钥或助记词直接写入合约代码，任何人可通过查看合约字节码或源码获取敏感密钥材料。

## Details

**典型代码示例：**
```solidity
contract Wallet {
    // 硬编码私钥
    bytes32 private constant OWNER_KEY = 0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a;
    
    // 硬编码助记词
    string private mnemonic = "witch collapse practice feed shame open despair creek road again ice least";
    
    // 用于链下签名验证
    function verifySignature(bytes memory signature, bytes32 hash) public view returns (bool) {
        address signer = ecrecover(hash, v, r, s);
        return signer == deriveAddress(OWNER_KEY); // 使用硬编码密钥派生地址
    }
}
```

**快速定位核心操作（L2-L3）：**
- 搜索关键常量声明：`constant`、`immutable` 配合 `bytes32`、`bytes`、`string` 类型
- 扫描赋值模式：长度32字节的十六进制字符串（0x开头64位）或12/24单词助记词格式
- 追踪 `ecrecover`、`ECDSA.recover` 调用链，检查签名验证源是否引用固定值
- 检查构造函数和初始化函数中的硬编码地址推导逻辑（如 `keccak256(privateKey)`）

**快速定位保护机制（L1-L2）：**
- 检查是否使用 HSM/KMS 接口抽象（如 `IKeyManager`、`Signer` 接口调用）
- 确认密钥材料是否来自 `constructor` 参数、`initialize` 参数或 `storage` 动态赋值
- 验证是否存在密钥轮换机制（`updateKey`、`rotateSecret` 等函数）
- 审查测试文件：硬编码通常首先出现在测试合约，需区分生产代码

## Classify

**漏洞判定：**
- 生产合约中包含完整私钥材料（32字节原始值或助记词明文）→ **高危漏洞**
- 私钥用于权限控制、资产操作、签名验证等关键路径 → **严重漏洞**

**误报场景：**
- 测试合约或 Mock 合约中的示例密钥，且明确标注 `Test`、`Mock` 前缀
- 用于公共演示的已公开密钥（需确认无实际资产关联）
- 注释或文档中的示例代码片段（非实际执行代码）

**代码异味：**
- 使用弱熵源派生密钥（如 `blockhash`、`block.timestamp`）但未直接硬编码原始私钥
- 在事件日志中暴露部分密钥信息（如前4字节），可能辅助暴力破解

## Low risk

**降级为低风险的条件：**
1. **时效性失效**：硬编码密钥对应的地址已废弃，无资产且无权限（需链上数据验证）
2. **隔离环境专用**：合约明确仅部署于私有测试网络，且代码注释说明临时性质
3. **公钥场景误判**：审计发现的"密钥"实际为公钥或地址，而非私钥本身（需区分椭圆曲线公钥与私钥格式）
4. **加密存储但密钥管理仍有缺陷**：私钥经加密后硬编码，但解密密钥同样硬编码（仍存在风险但优先级可降低）

**注意**：即使满足低风险条件，仍应在报告中明确记录该模式为不良实践，建议重构为密钥注入或外部签名方案。

## 审计专业技巧与实战区分

### 1. 密钥格式识别

**真实私钥特征（需全部满足）：**
- 长度恒定（256 bit = 32字节 = 64位十六进制字符）
- 数值范围：`0x1` 到 `0xFFFFFFF...FFFF`（小于曲线阶数）
- 通常以 `0x` 前缀的64位十六进制表示，或作为 `bytes32` 常量

**常见误报模式：**
- **地址混淆**：`address constant ADMIN = 0x742d35Cc...` 长度仅40位（20字节），实际是公钥地址而非私钥
- **事件主题哈希**：`bytes32 constant TRANSFER_TOPIC = keccak256("Transfer(address,address,uint256)")` 虽然是 bytes32，但为ABI签名摘要，非密钥材料
- **存储布局占位符**：合约中大量 `bytes32` 常量用于 slot 定位，如 `keccak256("owner")` 派生值，属于存储管理而非密钥

### 2. 真实漏洞案例与误报对比

**案例A：真实硬编码私钥漏洞**
```solidity
contract VulnerableWallet {
    // 实际私钥硬编码，从公开泄露的钱包中复制
    bytes32 private signingKey = 0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a;

    function authorizeTransfer(address recipient, uint amount) external {
        require(msg.sender == owner);
        // 使用硬编码私钥生成签名，链下攻击者可直接调用此函数
        bytes memory signature = _signMessage(signingKey, ...);
    }
}
```
**判定标准**：私钥直接参与权限控制和资产转账函数的关键路径 → **确实是漏洞**

**案例B：测试合约误报为漏洞**
```solidity
// test/MockWallet.test.sol
contract MockWallet {
    // 测试用虚拟密钥，已公开，无实际资产
    bytes32 internal constant TEST_PRIVATE_KEY = 0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a;

    function testSignatureVerification() public {
        address recovered = recoverSigner(TEST_PRIVATE_KEY);
        // 仅用于单元测试中的签名验证逻辑
    }
}
```
**判定标准**：
- 文件位置：`test/` 或 `tests/` 目录
- 类名包含 `Mock`、`Test` 前缀
- 注释明确说明仅用于测试
- 部署目标为本地测试网络（Hardhat、Ganache）
→ **误报，可降级或忽略**

### 3. 链上数据验证技巧

**验证密钥是否被使用或有权限：**
1. 提取硬编码密钥对应的地址（通过 ECDSA 公钥推导）
2. 查询区块链浏览器，检查该地址的：
   - 余额（是否有资产）
   - 交易历史（是否曾被使用）
   - 权限配置（`allowlist`、`owner` 角色等）
3. 若地址为零余额、无交易记录、无权限配置 → 可能低风险
4. 若地址曾被使用或拥有权限 → 确认为严重漏洞

**示例查询工序（以 Ethereum 为例）：**
```
1. 从合约代码提取：0x47e179ec...
2. 通过 ecrecover 推导公钥，计算 Keccak256 得到地址
3. Etherscan 查询该地址的 Txn Count 和 Balance
4. 若均为零且代码中无权限分配，记为低风险
```

### 4. 常见误判的上下文分析

| 检测项 | 真实漏洞信号 | 误报信号 |
|--------|-----------|--------|
| **代码位置** | src/、contracts/ 生产目录 | test/、tests/、mock/ 目录 |
| **变量命名** | 如 `OPERATOR_KEY`、`SIGNER_KEY`（暗示权限用途） | 如 `EXAMPLE_KEY`、`DEMO_KEY`（暗示示例） |
| **注释说明** | 无警告或移除注释 | 包含 "//TODO: replace"、"test only" |
| **函数调用链** | 在 `transfer`、`mint`、`approve` 等权限函数中使用 | 仅在测试断言或 mock 中使用 |
| **网络部署** | mainnet、polygon 生产网络 | 本地 localhost、testnet 标记明确 |
| **密钥轮换迹象** | 无 `rotateKey`、`updateSigner` 函数 | 存在密钥管理函数（虽然测试环境也可能有） |

### 5. 审计工作流建议

**第一步**：使用自动化工具初筛
```bash
# 搜索可疑的 bytes32 常量赋值
grep -n "bytes32.*constant.*=.*0x[a-f0-9]\{64\}" contracts/
```

**第二步**：手工确认上下文
- 查看变量所在的文件路径和类名
- 阅读前后的注释和代码逻辑
- 确认使用场景是否涉及签名或权限

**第三步**：链上交叉验证
- 若是生产合约，推导对应地址并查询余额和权限
- 检查合约的 `owner`、`admin` 等角色是否指向该地址

**第四步**：分级报告
- 高危：生产环境 + 有权限 + 有资产 + 无密钥轮换
- 中危：生产环境但无权限或资产，或测试环境但有权限的函数
- 低危：测试环境 + 明确标记 + 无实际部署
- 信息：已过期密钥对应的地址无活动
