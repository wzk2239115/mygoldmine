---
name: email-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 邮件注入（Email Injection）漏洞；重点关注邮件头/模板/SMTP 命令注入、CRLF 注入、地址验证绕过等核心特征；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 email_injection 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：未验证的用户输入被用于构造邮件头（Subject/From/To/CC/BCC）、邮件体模板或直接发送到 SMTP 命令流（CRLF 注入/命令注入）、邮件地址验证不严导致地址绕过、模板引擎未转义导致 SSTI/模板注入、允许用户上传/提供完整邮件内容或附件。

**Email Injection**

**Attention**  
邮件发送相关的模块（邮件模板渲染、邮件发送封装、第三方邮件库适配、用户输入拼接到邮件头或模板）是高风险区域；尤其注意处理用户输入构造邮件头字段、允许用户提供模板或自定义邮件内容、以及直接拼接到 SMTP 命令/协议字段的代码路径。

**Early exit**  
当且仅当项目没有任何邮件发送功能、代码库不包含 `sendMail`/`sendmail`/`nodemailer`/`smtplib`/`JavaMail`/`PHPMailer` 等相关调用，且不存在邮件模板或邮件队列模块时，可以快速退出该漏洞类别的审计。

**Cases**

**NodeJS**  
使用模板引擎渲染邮件时未转义用户输入，可能导致模板注入或敏感信息泄露，详见：[NodeJS_Email_Template_Injection.md](NodeJS_Email_Template_Injection.md)  
Nodemailer 使用不当导致邮件头 CRLF 注入，详见：[NodeJS_Nodemailer_Header_CRLF_Injection.md](NodeJS_Nodemailer_Header_CRLF_Injection.md)  
允许用户提供邮件内容或直接拼接 SMTP 命令，详见：[NodeJS_Custom_SMTP_Command_Injection.md](NodeJS_Custom_SMTP_Command_Injection.md)  
邮件地址验证不严导致地址绕过或回收利用，详见：[NodeJS_Email_Address_Validation_Bypass.md](NodeJS_Email_Address_Validation_Bypass.md)  
Express 中不安全的邮件发送封装导致注入，详见：[NodeJS_Express_Email_Injection.md](NodeJS_Express_Email_Injection.md)

**Java**  
模板引擎或邮件库中未对用户输入进行过滤，详见：[Java_Email_Template_Injection.md](Java_Email_Template_Injection.md)  
JavaMail 邮件头处理不当导致 CRLF 注入，详见：[Java_JavaMail_Header_CRLF_Injection.md](Java_JavaMail_Header_CRLF_Injection.md)  
Spring Mail 配置或参数拼接导致头注入或命令注入，详见：[Java_Spring_Mail_Header_Injection.md](Java_Spring_Mail_Header_Injection.md)  
邮件地址验证绕过，详见：[Java_Email_Address_Validation_Bypass.md](Java_Email_Address_Validation_Bypass.md)  
Commons Email 使用不当导致注入，详见：[Java_Commons_Email_Injection.md](Java_Commons_Email_Injection.md)

**Python**  
模板渲染（Django/Flask）中将用户输入直接注入邮件模板，详见：[Python_Email_Template_Injection.md](Python_Email_Template_Injection.md)  
SMTP 头或参数拼接导致 CRLF 注入，详见：[Python_SMTP_Header_CRLF_Injection.md](Python_SMTP_Header_CRLF_Injection.md)  
Flask-Mail 等扩展不当使用导致注入，详见：[Python_Flask_Mail_Injection.md](Python_Flask_Mail_Injection.md)  
Django 邮件头处理与地址验证问题，详见：[Python_Django_Email_Header_Injection.md](Python_Django_Email_Header_Injection.md)  
邮件地址验证绕过，详见：[Python_Email_Address_Validation_Bypass.md](Python_Email_Address_Validation_Bypass.md)

**Go**  
邮件模板渲染或字符串拼接导致注入，详见：[Go_Email_Template_Injection.md](Go_Email_Template_Injection.md)  
gomail 或邮件库头处理导致 CRLF 注入，详见：[Go_Gomail_Header_Injection.md](Go_Gomail_Header_Injection.md)  
SMTP 层面 CRLF/命令注入，详见：[Go_SMTP_Header_CRLF_Injection.md](Go_SMTP_Header_CRLF_Injection.md)  
自定义 SMTP 命令注入场景，详见：[Go_Custom_SMTP_Command_Injection.md](Go_Custom_SMTP_Command_Injection.md)  
邮件地址验证绕过，详见：[Go_Email_Address_Validation_Bypass.md](Go_Email_Address_Validation_Bypass.md)

**PHP**  
使用 `mail()` 或第三方库时的 CRLF 注入与头注入，详见：[PHP_Mail_Function_CRLF_Injection.md](PHP_Mail_Function_CRLF_Injection.md)  
PHPMailer/SwiftMailer 头注入与配置不当，详见：[PHP_PHPMailer_Header_Injection.md](PHP_PHPMailer_Header_Injection.md)  
模板注入与地址验证绕过，详见：[PHP_Email_Template_Injection.md](PHP_Email_Template_Injection.md)  
邮件地址验证绕过，详见：[PHP_Email_Address_Validation_Bypass.md](PHP_Email_Address_Validation_Bypass.md)

**C / C++**  
低级邮件库或手工拼接 SMTP 命令导致 CRLF/命令注入，详见：[C_SMTP_Header_CRLF_Injection.md](C_SMTP_Header_CRLF_Injection.md)  
自定义邮件命令注入，详见：[C_Custom_Email_Command_Injection.md](C_Custom_Email_Command_Injection.md)  
地址验证与头解析缺陷，详见：[C_Email_Address_Validation_Bypass.md](C_Email_Address_Validation_Bypass.md)  
邮件头解析缺陷导致注入，详见：[C_Email_Header_Parsing.md](C_Email_Header_Parsing.md)

**Rust**  
模板渲染或邮件库头处理导致注入，详见：[Rust_Email_Template_Injection.md](Rust_Email_Template_Injection.md)  
Lettre 等库的头注入/CRLF 问题，详见：[Rust_Lettre_Header_CRLF_Injection.md](Rust_Lettre_Header_CRLF_Injection.md)  
自定义 SMTP 命令注入，详见：[Rust_Custom_SMTP_Command_Injection.md](Rust_Custom_SMTP_Command_Injection.md)  
邮件地址验证绕过，详见：[Rust_Email_Address_Validation_Bypass.md](Rust_Email_Address_Validation_Bypass.md)

---

（注）本文件仅列出按语言划分的常见案例与定位要点；具体审计请参考各语言下对应的案例文件与 `general.md` 中的通用检查清单。

## 邮件注入绕过技巧

在进行邮件注入漏洞审计时，特别是验证防护机制的有效性，需要了解常见的绕过技巧。参考详细的绕过技巧文档：[bypassTricks.md](bypassTricks.md)

该文档包含：
- CRLF 注入绕过（编码、多层过滤绕过）
- 邮件地址验证绕过（正则、验证函数、IDN homograph）
- 邮件模板注入绕过（转义绕过、沙箱逃逸）
- SMTP 命令注入绕过（协议特性、邮件库特性）
- 邮件头编码绕过（RFC 2047、Quoted-Printable）
- 邮件地址格式化绕过（注释、IPv6、角括号）
- 多邮件库特定漏洞（PHPMailer、SwiftMailer、Django）

在验证防护机制时，应使用这些绕过技巧来测试防护的鲁棒性。

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-email-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板




