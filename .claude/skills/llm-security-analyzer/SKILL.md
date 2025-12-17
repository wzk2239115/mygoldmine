---
name: llm-security-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 LLM 安全（Large Language Model Security）漏洞；重点关注检测大语言模型应用中的安全风险，包括间接提示注入、恶意输出生成、输出洪水、令牌耗尽、敏感信息泄露、数据外泄、上下文泄露、训练数据提取、函数/工具滥用、API 滥用、工具访问控制绕过、SSRF、不安全输出处理、代码注入、SQL 注入、授权和访问控制滥用、权限提升、逻辑绕过、参数篡改等；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 LLM 安全漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：间接提示注入（隐藏指令注入、多轮对话污染、上下文污染）、恶意输出生成（XSS、HTML 注入、Markdown 注入）、输出洪水（无限循环输出、资源耗尽）、令牌耗尽（输入长度未限制、上下文窗口滥用）、敏感信息泄露（训练数据泄露、模型参数泄露、API 密钥泄露）、数据外泄（用户数据泄露、业务数据泄露）、上下文泄露（多用户上下文混淆、会话隔离失效）、训练数据提取（模型提取攻击、成员推断攻击）、函数/工具滥用（未授权函数调用、危险函数执行）、API 滥用（速率限制绕过、配额耗尽）、工具访问控制绕过（权限检查缺失、工具调用未验证）、SSRF（通过工具调用发起请求）、不安全输出处理（未转义输出、直接渲染）、代码注入（输出作为代码执行）、SQL 注入（通过 LLM 生成 SQL）、授权和访问控制滥用（权限检查缺失、越权访问）、权限提升（通过提示注入提升权限）、逻辑绕过（业务逻辑绕过、验证绕过）、参数篡改（输入参数篡改、配置参数篡改）

**LLM 安全漏洞**

**Attention**  
当项目中集成了大语言模型（LLM）功能，包括但不限于聊天机器人、代码生成、内容生成、智能问答、文档处理等涉及 LLM API 调用或本地模型部署的业务模块时，需重点审计提示词构造、用户输入处理、模型输出处理、函数调用机制、上下文管理、访问控制等关键环节。LLM 安全漏洞通常出现在用户输入直接拼接进提示词、模型输出未经验证直接使用、函数调用权限控制不当、多用户上下文隔离失效等场景。

**Early exit**  
若项目完全不涉及任何大语言模型功能（无 LLM API 调用、无本地模型部署、无提示词处理逻辑、无函数调用机制），或仅使用预编译的静态模型输出且无任何用户交互，则可快速退出对该漏洞类型的审计。

**Cases**

**Python**
使用 OpenAI/Anthropic 等 API 时用户输入直接拼接进提示词未过滤，详见：[Python_LLM_Prompt_Injection_Direct_Concatenation.md](Python_LLM_Prompt_Injection_Direct_Concatenation.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
使用 LangChain 框架时未对用户输入进行清理导致间接提示注入，详见：[Python_LLM_Indirect_Prompt_Injection_LangChain.md](Python_LLM_Indirect_Prompt_Injection_LangChain.md)；遇到数据验证、沙箱隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 2 节（间接提示注入）
模型输出直接渲染到 HTML 页面未转义导致 XSS，详见：[Python_LLM_Output_XSS_Unescaped.md](Python_LLM_Output_XSS_Unescaped.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.1 节（XSS 输出绕过）
模型输出作为 Markdown 渲染时未过滤危险标签，详见：[Python_LLM_Markdown_Injection.md](Python_LLM_Markdown_Injection.md)；遇到 Markdown 渲染限制保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.2 节（Markdown 注入绕过）
函数调用机制中未验证函数权限导致未授权执行，详见：[Python_LLM_Function_Call_Unauthorized.md](Python_LLM_Function_Call_Unauthorized.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）
上下文管理不当导致多用户数据泄露，详见：[Python_LLM_Context_Leaking.md](Python_LLM_Context_Leaking.md)；遇到上下文隔离、会话管理保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 5 节（上下文泄露和隔离失败）
输入长度未限制导致令牌耗尽攻击，详见：[Python_LLM_Token_Exhaustion.md](Python_LLM_Token_Exhaustion.md)；遇到令牌限制、输入长度检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 4 节（令牌耗尽攻击）
通过工具调用发起 SSRF 请求，详见：[Python_LLM_Tool_SSRF.md](Python_LLM_Tool_SSRF.md)；遇到 URL 白名单、域名限制保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6.2 节（SSRF 和外部调用）
模型输出直接作为代码执行，详见：[Python_LLM_Code_Injection.md](Python_LLM_Code_Injection.md)；遇到代码沙箱执行保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.3 节（代码执行绕过）
通过提示注入绕过业务逻辑验证，详见：[Python_LLM_Logic_Bypass.md](Python_LLM_Logic_Bypass.md)；遇到业务逻辑验证、权限检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 8 节（逻辑绕过和权限提升）

**JavaScript / TypeScript (Node.js)**
使用 OpenAI SDK 时用户输入未清理直接构造提示词，详见：[NodeJS_LLM_Prompt_Injection_Unsanitized.md](NodeJS_LLM_Prompt_Injection_Unsanitized.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
模型输出直接插入 DOM 未转义，详见：[NodeJS_LLM_Output_XSS_DOM.md](NodeJS_LLM_Output_XSS_DOM.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.1 节（XSS 输出绕过）
使用 Vercel AI SDK 时函数调用权限检查缺失，详见：[NodeJS_LLM_Function_Call_No_Permission_Check.md](NodeJS_LLM_Function_Call_No_Permission_Check.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）
上下文隔离失效导致用户数据混淆，详见：[NodeJS_LLM_Context_Isolation_Failure.md](NodeJS_LLM_Context_Isolation_Failure.md)；遇到上下文隔离、会话管理保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 5 节（上下文泄露和隔离失败）
输入验证不足导致输出洪水攻击，详见：[NodeJS_LLM_Output_Flooding.md](NodeJS_LLM_Output_Flooding.md)；遇到令牌限制、输入长度检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 4 节（令牌耗尽攻击）
通过工具调用访问敏感 API，详见：[NodeJS_LLM_Tool_API_Abuse.md](NodeJS_LLM_Tool_API_Abuse.md)；遇到速率限制、API 配额保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 7 节（API 和配额滥用）
模型输出作为 SQL 查询执行，详见：[NodeJS_LLM_SQL_Injection.md](NodeJS_LLM_SQL_Injection.md)；遇到 SQL 参数化保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.4 节（SQL 注入绕过）
提示注入导致权限提升，详见：[NodeJS_LLM_Privilege_Escalation.md](NodeJS_LLM_Privilege_Escalation.md)；遇到业务逻辑验证、权限检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 8 节（逻辑绕过和权限提升）
参数篡改绕过输入验证，详见：[NodeJS_LLM_Parameter_Tampering.md](NodeJS_LLM_Parameter_Tampering.md)；遇到输入验证、参数检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 9 节（参数篡改和输入验证）

**Java**
使用 Spring AI 时提示词构造未过滤用户输入，详见：[Java_LLM_Prompt_Injection_Spring_AI.md](Java_LLM_Prompt_Injection_Spring_AI.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
模型输出直接渲染到 JSP 页面未转义，详见：[Java_LLM_Output_XSS_JSP.md](Java_LLM_Output_XSS_JSP.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.1 节（XSS 输出绕过）
函数调用机制中未实施访问控制，详见：[Java_LLM_Function_Call_No_Access_Control.md](Java_LLM_Function_Call_No_Access_Control.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）
会话管理不当导致上下文泄露，详见：[Java_LLM_Session_Context_Leak.md](Java_LLM_Session_Context_Leak.md)；遇到上下文隔离、会话管理保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 5 节（上下文泄露和隔离失败）
输入长度限制缺失，详见：[Java_LLM_Input_Length_No_Limit.md](Java_LLM_Input_Length_No_Limit.md)；遇到令牌限制、输入长度检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 4 节（令牌耗尽攻击）
通过工具调用执行系统命令，详见：[Java_LLM_Tool_Command_Injection.md](Java_LLM_Tool_Command_Injection.md)；遇到命令白名单和转义保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6.3 节（命令注入）
模型输出作为代码编译执行，详见：[Java_LLM_Code_Execution.md](Java_LLM_Code_Execution.md)；遇到代码沙箱执行保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.3 节（代码执行绕过）

**Go**
使用 OpenAI Go SDK 时提示词拼接未验证，详见：[Go_LLM_Prompt_Injection_Concatenation.md](Go_LLM_Prompt_Injection_Concatenation.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
模型输出直接写入 HTTP 响应未转义，详见：[Go_LLM_Output_XSS_HTTP.md](Go_LLM_Output_XSS_HTTP.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.1 节（XSS 输出绕过）
函数调用权限验证缺失，详见：[Go_LLM_Function_Call_Permission_Missing.md](Go_LLM_Function_Call_Permission_Missing.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）
上下文管理并发安全问题，详见：[Go_LLM_Context_Concurrency_Issue.md](Go_LLM_Context_Concurrency_Issue.md)；遇到上下文隔离、会话管理保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 5 节（上下文泄露和隔离失败）
令牌配额未限制，详见：[Go_LLM_Token_Quota_No_Limit.md](Go_LLM_Token_Quota_No_Limit.md)；遇到令牌限制、输入长度检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 4 节（令牌耗尽攻击）
工具调用访问控制绕过，详见：[Go_LLM_Tool_Access_Control_Bypass.md](Go_LLM_Tool_Access_Control_Bypass.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）

**PHP**
使用 OpenAI PHP SDK 时用户输入直接嵌入提示词，详见：[PHP_LLM_Prompt_Injection_Embedded.md](PHP_LLM_Prompt_Injection_Embedded.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
模型输出直接 echo 到页面未转义，详见：[PHP_LLM_Output_XSS_Echo.md](PHP_LLM_Output_XSS_Echo.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3.1 节（XSS 输出绕过）
函数调用未验证调用者身份，详见：[PHP_LLM_Function_Call_No_Identity_Check.md](PHP_LLM_Function_Call_No_Identity_Check.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）
会话隔离失效，详见：[PHP_LLM_Session_Isolation_Failure.md](PHP_LLM_Session_Isolation_Failure.md)；遇到上下文隔离、会话管理保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 5 节（上下文泄露和隔离失败）
输入验证绕过，详见：[PHP_LLM_Input_Validation_Bypass.md](PHP_LLM_Input_Validation_Bypass.md)；遇到输入验证、参数检查保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 9 节（参数篡改和输入验证）

**C/C++**
使用本地模型推理时提示词处理未清理，详见：[C_LLM_Prompt_Injection_Native.md](C_LLM_Prompt_Injection_Native.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
模型输出缓冲区溢出，详见：[C_LLM_Output_Buffer_Overflow.md](C_LLM_Output_Buffer_Overflow.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3 节（恶意输出生成绕过）
函数调用指针安全问题，详见：[C_LLM_Function_Call_Pointer_Safety.md](C_LLM_Function_Call_Pointer_Safety.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）

**Rust**
使用 OpenAI Rust SDK 时提示词构造未验证，详见：[Rust_LLM_Prompt_Injection_Unvalidated.md](Rust_LLM_Prompt_Injection_Unvalidated.md)；遇到输入过滤、内容检测、提示词隔离保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 1 节（提示注入绕过）
模型输出未转义直接渲染，详见：[Rust_LLM_Output_Unescaped.md](Rust_LLM_Output_Unescaped.md)；遇到输出过滤、转义处理、沙箱渲染保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 3 节（恶意输出生成绕过）
函数调用所有权安全问题，详见：[Rust_LLM_Function_Call_Ownership_Issue.md](Rust_LLM_Function_Call_Ownership_Issue.md)；遇到函数访问控制、权限验证保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 6 节（函数/工具调用滥用）
上下文生命周期管理问题，详见：[Rust_LLM_Context_Lifetime_Issue.md](Rust_LLM_Context_Lifetime_Issue.md)；遇到上下文隔离、会话管理保护机制，详见 [bypassTricks.md](bypassTricks.md) 第 5 节（上下文泄露和隔离失败）

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-llm-security-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

