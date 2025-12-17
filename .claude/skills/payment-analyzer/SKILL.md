---
name: payment-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证支付安全漏洞；重点关注检测支付业务流程中未对状态流转严谨性、金额计算精度、幂等性控制、回调验证、交易号唯一性、风控限额、数据安全、签名验签、密钥管理进行充分校验的问题，包括支付状态机非法跳过、重复支付、金额精度错误、回调伪造、交易号盗用、限额绕过、敏感数据泄露、签名未验证、密钥硬编码等，从而导致资金损失、重复扣款、数据泄露、交易伪造等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用支付安全漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：支付状态机/订单状态（状态流转未校验前置条件、非法跳过、重复支付、状态篡改）、金额/价格/货币（金额计算错误、精度处理不当、浮点数风险、超限、负数、整数溢出）、幂等性/重复提交（缺少幂等性控制、重复支付、重复退款）、回调/通知（签名验证缺失、IP白名单未配置、伪造通知、重放攻击）、交易号/流水号（唯一性校验缺失、可预测、可重复使用、可伪造）、风控/限额（交易频率未限制、单笔/累计限额缺失或可绕过）、数据安全（敏感数据未加密或脱敏、卡号/CVV/密钥泄露、日志泄露）、签名/验签（关键数据未签名、签名未验证、签名算法不安全）、密钥/证书（密钥硬编码、密钥存储不安全、访问控制缺失、轮换机制缺失）

**支付安全漏洞（Payment Security Vulnerabilities）**

**Attention**  
当项目中涉及支付、订单、交易等涉及资金流转的业务逻辑时，需重点审计支付状态机的状态流转是否严谨、金额计算与精度处理是否正确、是否具备幂等性控制、回调通知是否经过验证、交易号唯一性是否保证、风控限额是否生效、敏感数据是否加密或脱敏、签名验签是否完整、密钥证书是否安全存储等。此类漏洞常见于支付网关集成、订单处理、退款流程、第三方支付回调、金融交易等模块中。

**Early exit**  
若项目完全不涉及任何支付、订单、交易、资金流转相关的功能（例如纯内容管理系统、无交易功能的社交平台、只读数据展示系统），且代码中无任何支付接口、订单状态管理、金额计算、交易流水等逻辑，则可快速退出对该漏洞类型的审计。

**Cases**

**Java**
支付状态机状态流转未校验前置条件，允许非法跳过支付步骤，详见：[Java_PaymentStateMachine_Bypass.md](Java_PaymentStateMachine_Bypass.md) | 遇到状态机保护，详见：[bypassTricks.md#3-支付状态机绕过](bypassTricks.md#3-支付状态机绕过)
金额计算使用浮点数导致精度问题，详见：[Java_AmountCalculation_FloatPrecision.md](Java_AmountCalculation_FloatPrecision.md) | 遇到浮点数计算，详见：[bypassTricks.md#11-浮点数精度问题](bypassTricks.md#11-浮点数精度问题)
支付回调未验证签名，允许伪造回调通知，详见：[Java_PaymentCallback_SignatureVerification.md](Java_PaymentCallback_SignatureVerification.md) | 遇到签名验证，详见：[bypassTricks.md#41-回调签名验证绕过](bypassTricks.md#41-回调签名验证绕过)
交易号未做唯一性校验，存在重复使用风险，详见：[Java_TransactionId_UniquenessCheck.md](Java_TransactionId_UniquenessCheck.md) | 遇到交易ID验证，详见：[bypassTricks.md#22-id-重用](bypassTricks.md#22-id-重用)
支付接口缺少幂等性控制，允许重复支付，详见：[Java_PaymentIdempotency_Missing.md](Java_PaymentIdempotency_Missing.md) | 遇到幂等性机制，详见：[bypassTricks.md#42-回调重放攻击](bypassTricks.md#42-回调重放攻击)
支付敏感数据未加密或脱敏，存在泄露风险，详见：[Java_PaymentData_SensitiveDataLeakage.md](Java_PaymentData_SensitiveDataLeakage.md) | 遇到数据保护，详见：[bypassTricks.md#7-加密和数据保护绕过](bypassTricks.md#7-加密和数据保护绕过)
支付签名密钥管理不当，密钥存储不安全，详见：[Java_PaymentSign_KeyManagement.md](Java_PaymentSign_KeyManagement.md) | 遇到密钥管理，详见：[bypassTricks.md#5-密钥管理相关绕过](bypassTricks.md#5-密钥管理相关绕过)

**Python**
订单状态可被非法跳过，绕过支付验证，详见：[Python_PaymentState_SkipValidation.md](Python_PaymentState_SkipValidation.md) | 遇到状态机保护，详见：[bypassTricks.md#3-支付状态机绕过](bypassTricks.md#3-支付状态机绕过)
金额计算存在精度误差，使用浮点数导致计算错误，详见：[Python_Amount_FloatPrecision.md](Python_Amount_FloatPrecision.md) | 遇到浮点数计算，详见：[bypassTricks.md#11-浮点数精度问题](bypassTricks.md#11-浮点数精度问题)
支付回调未验证来源，缺少IP白名单验证，详见：[Python_Callback_OriginVerification.md](Python_Callback_OriginVerification.md) | 遇到IP白名单，详见：[bypassTricks.md#43-源地址验证绕过](bypassTricks.md#43-源地址验证绕过)
重复支付未检测，缺少幂等性控制，详见：[Python_DuplicatePayment_Detection.md](Python_DuplicatePayment_Detection.md) | 遇到幂等性机制，详见：[bypassTricks.md#42-回调重放攻击](bypassTricks.md#42-回调重放攻击)
交易流水号可被伪造，缺少唯一性校验，详见：[Python_TransactionId_Forgery.md](Python_TransactionId_Forgery.md) | 遇到交易ID验证，详见：[bypassTricks.md#21-可预测的交易id](bypassTricks.md#21-可预测的交易id)
风控限额可被绕过，交易频率和金额限制失效，详见：[Python_RiskControl_LimitBypass.md](Python_RiskControl_LimitBypass.md) | 遇到风控限制，详见：[bypassTricks.md#6-防欺诈机制绕过](bypassTricks.md#6-防欺诈机制绕过)
支付数据未加密，敏感信息泄露，详见：[Python_PaymentData_Encryption.md](Python_PaymentData_Encryption.md) | 遇到数据保护，详见：[bypassTricks.md#7-加密和数据保护绕过](bypassTricks.md#7-加密和数据保护绕过)

**Go**
并发场景下支付状态存在竞态条件，导致状态不一致，详见：[Go_PaymentState_RaceCondition.md](Go_PaymentState_RaceCondition.md) | 遇到并发控制，详见：[bypassTricks.md#10-竞态条件相关](bypassTricks.md#10-竞态条件相关)
金额计算整数溢出，未处理大金额情况，详见：[Go_Amount_IntegerOverflow.md](Go_Amount_IntegerOverflow.md) | 遇到整数溢出，详见：[bypassTricks.md#12-整数溢出](bypassTricks.md#12-整数溢出)
回调IP白名单未生效，允许任意IP回调，详见：[Go_Callback_IPWhitelist.md](Go_Callback_IPWhitelist.md) | 遇到IP白名单，详见：[bypassTricks.md#43-源地址验证绕过](bypassTricks.md#43-源地址验证绕过)
幂等性控制不完整，部分场景可重复处理，详见：[Go_Idempotency_Incomplete.md](Go_Idempotency_Incomplete.md) | 遇到幂等性机制，详见：[bypassTricks.md#42-回调重放攻击](bypassTricks.md#42-回调重放攻击)
交易号生成可预测，存在被猜测风险，详见：[Go_TransactionId_Predictable.md](Go_TransactionId_Predictable.md) | 遇到交易ID验证，详见：[bypassTricks.md#21-可预测的交易id](bypassTricks.md#21-可预测的交易id)
风控交易频率限制未生效，可绕过频率检查，详见：[Go_RiskControl_FrequencyLimit.md](Go_RiskControl_FrequencyLimit.md) | 遇到风控限制，详见：[bypassTricks.md#61-频率限制绕过](bypassTricks.md#61-频率限制绕过)
支付签名证书管理不当，证书过期或未轮换，详见：[Go_PaymentSign_CertificateManagement.md](Go_PaymentSign_CertificateManagement.md) | 遇到密钥管理，详见：[bypassTricks.md#5-密钥管理相关绕过](bypassTricks.md#5-密钥管理相关绕过)

**PHP**
支付状态可直接修改，未校验状态转换合法性，详见：[PHP_PaymentState_DirectModification.md](PHP_PaymentState_DirectModification.md) | 遇到状态机保护，详见：[bypassTricks.md#3-支付状态机绕过](bypassTricks.md#3-支付状态机绕过)
金额可为负数，未验证金额有效性，详见：[PHP_Amount_NegativeValue.md](PHP_Amount_NegativeValue.md) | 遇到负数金额，详见：[bypassTricks.md#13-负金额绕过](bypassTricks.md#13-负金额绕过)
回调通知可被重放，缺少时间戳和随机数验证，详见：[PHP_Callback_ReplayAttack.md](PHP_Callback_ReplayAttack.md) | 遇到重放攻击，详见：[bypassTricks.md#42-回调重放攻击](bypassTricks.md#42-回调重放攻击)
交易号可重复使用，唯一性约束缺失，详见：[PHP_TransactionId_Reuse.md](PHP_TransactionId_Reuse.md) | 遇到交易ID验证，详见：[bypassTricks.md#22-id-重用](bypassTricks.md#22-id-重用)
密钥硬编码在代码中，密钥泄露风险高，详见：[PHP_Key_Hardcoded.md](PHP_Key_Hardcoded.md) | 遇到硬编码密钥，详见：[bypassTricks.md#51-硬编码密钥](bypassTricks.md#51-硬编码密钥)
支付数据在日志中未脱敏，存在信息泄露，详见：[PHP_PaymentData_LogLeakage.md](PHP_PaymentData_LogLeakage.md) | 遇到数据保护，详见：[bypassTricks.md#7-加密和数据保护绕过](bypassTricks.md#7-加密和数据保护绕过)

**JavaScript / TypeScript (Node.js)**
客户端状态可被篡改，依赖前端状态进行支付决策，详见：[NodeJS_PaymentState_ClientTampering.md](NodeJS_PaymentState_ClientTampering.md) | 遇到客户端状态，详见：[bypassTricks.md#32-客户端状态篡改](bypassTricks.md#32-客户端状态篡改)
金额计算依赖前端逻辑，服务端未重新校验，详见：[NodeJS_Amount_ClientCalculation.md](NodeJS_Amount_ClientCalculation.md) | 遇到金额计算，详见：[bypassTricks.md#1-金额相关绕过](bypassTricks.md#1-金额相关绕过)
回调签名验证缺失，未验证回调来源合法性，详见：[NodeJS_Callback_SignatureMissing.md](NodeJS_Callback_SignatureMissing.md) | 遇到签名验证，详见：[bypassTricks.md#41-回调签名验证绕过](bypassTricks.md#41-回调签名验证绕过)
交易号在客户端生成，可被伪造或重复使用，详见：[NodeJS_TransactionId_ClientGeneration.md](NodeJS_TransactionId_ClientGeneration.md) | 遇到交易ID验证，详见：[bypassTricks.md#2-交易id相关绕过](bypassTricks.md#2-交易id相关绕过)
支付数据未加密传输，明文传输敏感信息，详见：[NodeJS_PaymentData_PlainTextTransmission.md](NodeJS_PaymentData_PlainTextTransmission.md) | 遇到明文传输，详见：[bypassTricks.md#71-明文传输](bypassTricks.md#71-明文传输)
风控限额检查在客户端进行，可被绕过，详见：[NodeJS_RiskControl_ClientSideLimit.md](NodeJS_RiskControl_ClientSideLimit.md) | 遇到风控限制，详见：[bypassTricks.md#6-防欺诈机制绕过](bypassTricks.md#6-防欺诈机制绕过)

**C/C++**
状态机实现未校验转换条件，允许非法状态转换，详见：[C_PaymentState_UncheckedTransition.md](C_PaymentState_UncheckedTransition.md) | 遇到状态机保护，详见：[bypassTricks.md#3-支付状态机绕过](bypassTricks.md#3-支付状态机绕过)
金额计算缓冲区溢出，未检查输入长度，详见：[C_Amount_BufferOverflow.md](C_Amount_BufferOverflow.md) | 遇到金额计算，详见：[bypassTricks.md#1-金额相关绕过](bypassTricks.md#1-金额相关绕过)
回调处理未验证来源，缺少来源合法性检查，详见：[C_Callback_SourceValidation.md](C_Callback_SourceValidation.md) | 遇到来源验证，详见：[bypassTricks.md#43-源地址验证绕过](bypassTricks.md#43-源地址验证绕过)
交易号生成算法不安全，可预测或碰撞，详见：[C_TransactionId_UnsafeGeneration.md](C_TransactionId_UnsafeGeneration.md) | 遇到交易ID验证，详见：[bypassTricks.md#21-可预测的交易id](bypassTricks.md#21-可预测的交易id)
密钥管理不当，密钥存储在内存中未加密，详见：[C_Key_Management.md](C_Key_Management.md) | 遇到密钥管理，详见：[bypassTricks.md#5-密钥管理相关绕过](bypassTricks.md#5-密钥管理相关绕过)
支付数据在内存中未清零，存在内存泄露风险，详见：[C_PaymentData_MemoryLeakage.md](C_PaymentData_MemoryLeakage.md) | 遇到数据保护，详见：[bypassTricks.md#7-加密和数据保护绕过](bypassTricks.md#7-加密和数据保护绕过)

**Rust**
状态枚举未充分利用类型系统，允许运行时非法状态跳转，详见：[Rust_PaymentState_TypeSystemBypass.md](Rust_PaymentState_TypeSystemBypass.md) | 遇到状态机保护，详见：[bypassTricks.md#3-支付状态机绕过](bypassTricks.md#3-支付状态机绕过)
金额计算未处理溢出，使用未检查的整数运算，详见：[Rust_Amount_OverflowHandling.md](Rust_Amount_OverflowHandling.md) | 遇到整数溢出，详见：[bypassTricks.md#12-整数溢出](bypassTricks.md#12-整数溢出)
回调验证逻辑不完整，部分验证条件缺失，详见：[Rust_Callback_VerificationIncomplete.md](Rust_Callback_VerificationIncomplete.md) | 遇到回调验证，详见：[bypassTricks.md#4-支付回调相关绕过](bypassTricks.md#4-支付回调相关绕过)
交易号生成存在竞态条件，并发场景下可能重复，详见：[Rust_TransactionId_RaceCondition.md](Rust_TransactionId_RaceCondition.md) | 遇到竞态条件，详见：[bypassTricks.md#10-竞态条件相关](bypassTricks.md#10-竞态条件相关)
密钥轮换机制缺失，密钥长期使用未更新，详见：[Rust_Key_RotationMissing.md](Rust_Key_RotationMissing.md) | 遇到密钥管理，详见：[bypassTricks.md#5-密钥管理相关绕过](bypassTricks.md#5-密钥管理相关绕过)
支付数据未使用安全清零，敏感数据残留内存，详见：[Rust_PaymentData_Zeroization.md](Rust_PaymentData_Zeroization.md) | 遇到数据保护，详见：[bypassTricks.md#7-加密和数据保护绕过](bypassTricks.md#7-加密和数据保护绕过)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-payment-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

