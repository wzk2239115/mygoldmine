---
name: token-standards-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证代币标准实现（Token Standards Implementation）问题；重点关注智能合约是否正确实现了所声称的代币标准（ERC-20、ERC-721、ERC-1155 等），确保与生态系统集成的兼容性；涵盖必需函数缺失、返回值不符合标准、事件定义不正确、接口实现不兼容、元数据缺失等实现缺陷；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 token_standards 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：必需函数缺失或不完整（totalSupply/balanceOf/transfer/approve 等）、返回值不符合标准（返回 bool 值缺失、返回值类型错误）、事件定义不正确（Transfer/Approval 事件参数缺失或类型错误）、接口实现不兼容（未实现标准接口、接口签名不匹配）、元数据缺失（name/symbol/decimals 未实现或返回错误）、转账逻辑不符合标准（转账失败未回滚、转账金额验证缺失）、授权机制实现错误（allowance 计算错误、approve 未重置为 0）、批量操作不符合标准（批量转账/授权实现错误）、NFT 标准实现缺陷（tokenURI 缺失、ownerOf 实现错误、枚举功能缺失）、多代币标准实现缺陷（balanceOfBatch 实现错误、safeTransferFrom 逻辑缺失）

**Token Standards Implementation**

**Attention**  
当项目声明实现了特定代币标准（如 ERC-20、ERC-721、ERC-1155）但实际实现中缺少必需函数、返回值不符合标准、事件定义不正确或接口签名不匹配时，需重点审计代币标准实现。此类问题通常源于对标准规范理解不足、实现不完整或为了优化而偏离标准，常见于代币合约、NFT 合约、多代币合约等业务场景，可能导致与 DEX、钱包、索引器等生态工具的集成失败。

**Early exit**  
如果项目代码中完全不存在代币相关合约（如无 ERC-20/ERC-721/ERC-1155 接口声明、无代币转账逻辑、无余额查询功能），且业务逻辑不涉及任何代币发行、转账或授权操作，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在 ERC-20、ERC-721、ERC-1155 等代币标准实现中，包括但不限于必需函数缺失、返回值不符合标准、事件定义不正确、接口实现不兼容等方式：  
- ERC-20 必需函数缺失：代币合约未实现 totalSupply、balanceOf、transfer、approve 等必需函数，导致不符合 ERC-20 标准，详见：[Solidity_ERC20_MissingRequiredFunctions.md](Solidity_ERC20_MissingRequiredFunctions.md)  
- ERC-20 返回值不符合标准：transfer 和 approve 函数未返回 bool 值，或返回值类型错误，导致与标准不兼容，详见：[Solidity_ERC20_InvalidReturnValue.md](Solidity_ERC20_InvalidReturnValue.md)  
- ERC-20 事件定义不正确：Transfer 和 Approval 事件参数缺失、参数类型错误或事件名称不匹配，导致索引器无法正确解析，详见：[Solidity_ERC20_InvalidEventDefinition.md](Solidity_ERC20_InvalidEventDefinition.md)  
- ERC-721 tokenURI 缺失：NFT 合约未实现 tokenURI 函数或返回空值，导致元数据无法获取，详见：[Solidity_ERC721_MissingTokenURI.md](Solidity_ERC721_MissingTokenURI.md)  
- ERC-721 ownerOf 实现错误：ownerOf 函数对不存在的 tokenId 返回错误值或未回滚，导致标准兼容性问题，详见：[Solidity_ERC721_InvalidOwnerOf.md](Solidity_ERC721_InvalidOwnerOf.md)  
- ERC-1155 balanceOfBatch 实现错误：批量查询函数未正确实现或返回值格式错误，导致批量操作失败，详见：[Solidity_ERC1155_InvalidBalanceOfBatch.md](Solidity_ERC1155_InvalidBalanceOfBatch.md)  
- ERC-1155 safeTransferFrom 逻辑缺失：批量转账函数未实现或缺少安全检查，导致标准兼容性问题，详见：[Solidity_ERC1155_MissingSafeTransferFrom.md](Solidity_ERC1155_MissingSafeTransferFrom.md)

**Rust**（适用于 Solana SPL Token、CosmWasm CW20 等）  
常出现在 SPL Token、CW20、CW721 等代币标准实现中，包括但不限于指令处理不符合标准、账户结构不匹配、元数据缺失等方式：  
- SPL Token 指令处理不符合标准：代币程序未正确处理 Transfer、Approve、Mint 等标准指令，导致与钱包和 DEX 不兼容，详见：[Rust_SPLToken_InvalidInstruction.md](Rust_SPLToken_InvalidInstruction.md)  
- SPL Token 账户结构不匹配：代币账户数据结构不符合 SPL Token 标准，导致解析失败，详见：[Rust_SPLToken_InvalidAccountStructure.md](Rust_SPLToken_InvalidAccountStructure.md)  
- CW20 必需函数缺失：CosmWasm CW20 代币合约未实现 transfer、send、burn 等必需函数，详见：[Rust_CW20_MissingRequiredFunctions.md](Rust_CW20_MissingRequiredFunctions.md)  
- CW721 token_info 缺失：NFT 合约未实现 token_info 查询函数或返回格式错误，详见：[Rust_CW721_MissingTokenInfo.md](Rust_CW721_MissingTokenInfo.md)

**Move**  
常出现在 Move 代币标准（如 Aptos Coin、Sui Coin）实现中，包括但不限于资源结构不符合标准、函数签名不匹配、元数据缺失等方式：  
- Coin 资源结构不符合标准：代币资源结构未遵循标准 Coin 类型定义，导致与标准库不兼容，详见：[Move_Coin_InvalidResourceStructure.md](Move_Coin_InvalidResourceStructure.md)  
- Coin 函数签名不匹配：transfer、mint、burn 等函数签名与标准接口不匹配，导致调用失败，详见：[Move_Coin_InvalidFunctionSignature.md](Move_Coin_InvalidFunctionSignature.md)  
- NFT 资源元数据缺失：NFT 资源未包含标准元数据字段（如 name、description、uri），导致无法正确展示，详见：[Move_NFT_MissingMetadata.md](Move_NFT_MissingMetadata.md)

**Vyper**  
常出现在基于 Vyper 实现的代币标准中，包括但不限于接口实现不完整、事件定义错误、返回值缺失等方式：  
- ERC-20 接口实现不完整：Vyper 代币合约未完整实现 ERC-20 接口的所有必需函数，详见：[Vyper_ERC20_IncompleteInterface.md](Vyper_ERC20_IncompleteInterface.md)  
- ERC-20 事件定义错误：Transfer 和 Approval 事件参数定义与标准不匹配，导致事件解析失败，详见：[Vyper_ERC20_InvalidEventDefinition.md](Vyper_ERC20_InvalidEventDefinition.md)  
- ERC-721 枚举功能缺失：NFT 合约未实现 totalSupply 和 tokenByIndex 等枚举功能，不符合 ERC-721 Enumerable 扩展标准，详见：[Vyper_ERC721_MissingEnumerable.md](Vyper_ERC721_MissingEnumerable.md)

**Go**（适用于 Cosmos SDK Token 模块等）  
常出现在 Cosmos SDK 代币模块、IBC Token 等实现中，包括但不限于消息处理不符合标准、查询接口缺失、元数据验证错误等方式：  
- Token 消息处理不符合标准：代币模块的消息处理逻辑不符合 Cosmos SDK 标准，导致转账和授权操作失败，详见：[Go_Token_InvalidMessageHandler.md](Go_Token_InvalidMessageHandler.md)  
- Token 查询接口缺失：代币模块未实现 balance、supply 等标准查询接口，导致无法查询代币信息，详见：[Go_Token_MissingQueryInterface.md](Go_Token_MissingQueryInterface.md)  
- IBC Token 元数据验证错误：跨链代币的元数据验证逻辑不符合 IBC 标准，导致跨链转账失败，详见：[Go_IBCToken_InvalidMetadataValidation.md](Go_IBCToken_InvalidMetadataValidation.md)

