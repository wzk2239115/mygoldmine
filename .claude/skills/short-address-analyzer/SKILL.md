---
name: short-address-analyzer
description: 专业的审计工作流程，通过静态与动态代码分析识别和验证短地址攻击（Short Address Attack）漏洞；重点关注ERC20代币转账函数中的地址参数处理缺陷，包括缺失地址长度验证、calldata操纵导致的金额改变等；涵盖代币转账、批量转账、授权转账等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
短地址攻击是一类特殊的ERC20漏洞，攻击者通过提供长度不足的地址（如以0x00结尾）利用Solidity对calldata的处理特性，导致函数参数被错误地解析。当缺失地址长度验证时，calldata可能被错误补零，进而改变转账金额或其他参数值。需重点审计所有涉及地址参数处理的代币函数，特别是转账、授权、批量操作等功能。

**Early exit**
如果合约完全不处理外部地址参数（仅使用内部地址或常数地址）、不涉及ERC20转账逻辑、或对所有地址参数实施了严格的长度/格式验证且验证逻辑正确无误，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**
短地址攻击常出现在ERC20代币实现中，特别是transfer、transferFrom等敏感函数，攻击者可通过精心构造的交易导致实际转账金额与预期不符：
- 缺失地址长度验证：代币转账函数未检查收款地址的有效性，接受任意长度参数，导致calldata被错误解析，详见：[Solidity_ShortAddressAttack.md](Solidity_ShortAddressAttack.md)
- calldata操纵导致金额改变：由于Solidity对参数补零的特性，短地址攻击可导致uint256金额参数被改变，从而转账金额大幅增加或数据被篡改，详见：[Solidity_ShortAddressAttack.md](Solidity_ShortAddressAttack.md)
- 批量转账中的短地址风险：含有批量地址处理的函数（如airDrop等）未对地址数组元素进行长度验证，导致多笔转账金额被串联篡改，详见：[Solidity_ShortAddressAttack.md](Solidity_ShortAddressAttack.md)

**Vyper**
Vyper 对短地址的处理与 Solidity 相同，需关注地址参数验证：
- Vyper transfer 函数缺失地址验证：未检查 `_to` 参数长度，导致 calldata 被错误解析，详见：[Vyper_ShortAddressAttack.md](Vyper_ShortAddressAttack.md)

**快速扫描检查清单**

| 项目 | 检查内容 | 关键字 |
|-----|--------|-------|
| L1: 敏感函数定位 | 定位所有处理地址参数的外部函数 | `transfer`, `transferFrom`, `approve`, `mint`, `burn`, `send`, `receive`, `swap`, `execute` |
| L2: 参数验证 | 检查函数是否验证地址参数长度 | `require`, `assert`, `address(...).code`, `address(...).length` |
| L3: calldata 长度 | 检查函数是否验证或记录 calldata 长度 | `msg.data.length`, `require(msg.data.length == ...)` |
| L4: 参数提取 | 检查是否使用了不安全的参数提取方式 | 动态数组、低级 `call`, `delegatecall` |

---

## 漏洞详解

### 短地址攻击原理

短地址攻击利用以下特性：

1. **Solidity 参数编码**：函数参数在 calldata 中以固定宽度（32 字节）编码
2. **地址参数补零**：如果地址参数长度不足 20 字节，EVM 会在末尾补零
3. **calldata 滑动**：当地址长度不足时，后续参数的 calldata 偏移量会异常，导致参数值错位

### 攻击场景

**场景 1：transfer 函数中的短地址攻击**
```solidity
// 易受攻击的代码
function transfer(address to, uint256 amount) public returns (bool) {
    require(balances[msg.sender] >= amount);
    balances[msg.sender] -= amount;
    balances[to] += amount;
    emit Transfer(msg.sender, to, amount);
    return true;
}

// 攻击交易：
// 正常：transfer(0x1234...abcd, 100)
// 攻击：transfer(0x1234...ab00, 100)  <- 以 0x00 结尾的短地址
//       由于补零，amount 被解析为 0x100 * 256 (即 25600)
```

**场景 2：批量转账中的短地址攻击**
```solidity
// 易受攻击的代码
function batchTransfer(address[] recipients, uint256[] amounts) public {
    for (uint i = 0; i < recipients.length; i++) {
        transfer(recipients[i], amounts[i]);
    }
}

// 攻击：提供包含短地址的 recipients 数组
// 第一个短地址的补零可能影响后续参数的解析
```

---

## 检查方法

### 核心定位技巧

**L1: 敏感函数扫描**
- 扫描关键词：`transfer`, `transferFrom`, `approve`, `mint`, `burn`, `send`, `receive`, `swap`, `execute`
- 查找所有包含 `address` 类型参数的 `external`/`public` 函数
- 特别关注 ERC20/ERC721 标准函数实现

**L2: 参数验证检查**
- 检查函数开始是否有地址长度验证：`require(to != address(0))` 只能排除零地址，不能验证长度
- 查找是否存在显式的地址验证：如检查 `to.code.length`、`msg.data.length` 等
- 检查是否使用了库函数进行地址验证

**L3: 低级调用风险**
- 检查是否使用了 `call`, `delegatecall`, `staticcall` 处理地址参数
- 低级调用直接操作 calldata，更容易受到参数操纵

**L4: 依赖项检查**
- 检查是否继承自标准库（如 OpenZeppelin）的安全实现
- 使用官方库的代码通常已有地址验证

---

## 分类研判

**漏洞判定**
- ERC20 transfer/transferFrom 函数不验证地址参数有效性
- 函数接受地址参数但未检查参数长度或来源合法性
- 使用了自定义的地址处理逻辑，绕过了标准库的验证

**误报判定**
- 使用了 OpenZeppelin 等标准库的 transfer 实现
- 函数使用了 `require(to != address(0))` 作为地址检查（虽然不能完全防御短地址攻击，但已是基础防护）
- 合约不涉及地址参数处理

**代码异味判定**
- 地址验证不一致：部分函数有验证，部分没有
- 注释标注"防止短地址"但实现不完整
- 直接操作 calldata 处理参数

---

## 低风险场景

- **使用标准库**：使用 OpenZeppelin 或其他审计过的标准库实现
- **仅内部调用**：函数为 `internal`，不接收外部调用的地址参数
- **常数地址**：函数使用硬编码的地址，不接收参数
- **已验证部署**：合约已在主网长期运行且未发现问题，社区已验证安全性

---

## 快速开始

1. **定位 ERC20 实现**：找到代币合约的 transfer/transferFrom 函数
2. **检查地址参数**：验证是否对 to 地址参数进行了长度检查
3. **查看库依赖**：确认是否使用了标准库的安全实现
4. **测试攻击**：构造包含短地址的交易进行测试

---

## 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-short-address-{file}-L{line}-{method}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
