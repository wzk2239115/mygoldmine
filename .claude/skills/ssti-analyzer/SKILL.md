---
name: ssti-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 SSTI（服务器端模板注入）漏洞；重点关注检测不安全的模板渲染，即用户可控输入未经适当验证或过滤直接嵌入模板引擎进行渲染执行；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 SSTI 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：用户输入直接嵌入模板渲染（未过滤用户输入、直接拼接模板代码）、模板引擎配置不安全（允许执行任意代码、未禁用危险函数）、动态模板加载（用户可控模板路径、远程模板加载）、模板上下文污染（用户输入作为模板变量、全局上下文注入）、模板继承和包含注入（用户可控继承路径、include 路径可控）、表达式注入（用户输入作为表达式、EL 表达式注入）、模板过滤器滥用（危险过滤器未禁用、自定义过滤器不安全）、渲染上下文不当（渲染时执行代码、模板编译时执行）

**服务器端模板注入（SSTI）**

**Attention**  
当项目中存在将用户可控输入直接嵌入模板引擎进行渲染的业务逻辑时，极易引发服务器端模板注入漏洞。此类问题通常出现在动态网页渲染、邮件模板生成、用户自定义通知、报告生成等涉及模板渲染的业务模块中，需重点审计模板引擎的渲染调用点，特别是用户输入未经过滤直接作为模板内容或模板变量的场景。

**Early exit**  
若项目完全不使用任何模板引擎（如纯静态页面、纯 API 服务无模板渲染、仅使用客户端模板渲染），或所有模板内容均为静态预定义且无任何用户输入参与模板构造，则可快速退出对该漏洞类型的审计。

**Cases**

**Python**
使用 Jinja2 模板引擎时未对用户输入进行过滤，直接将用户可控内容嵌入模板渲染，详见：[Python_SSTI_Jinja2_Unsanitized_User_Input.md](Python_SSTI_Jinja2_Unsanitized_User_Input.md)
使用 Mako 模板引擎时允许用户输入作为模板代码执行，详见：[Python_SSTI_Mako_Template_Evaluation.md](Python_SSTI_Mako_Template_Evaluation.md)
Django 模板系统中不当使用用户输入作为模板上下文，详见：[Python_SSTI_Django_Improper_Template_Context.md](Python_SSTI_Django_Improper_Template_Context.md)
Flask render_template_string 直接渲染用户输入，详见：[Python_SSTI_Flask_Render_Template_String.md](Python_SSTI_Flask_Render_Template_String.md)
Tornado 模板渲染时用户输入未转义，详见：[Python_SSTI_Tornado_Unescaped_Input.md](Python_SSTI_Tornado_Unescaped_Input.md)
遇到黑名单/白名单过滤保护机制，详见 [bypassTricks.md](bypassTricks.md) 第1、2节（模板语法检测与变量访问限制绕过）；遇到 SandboxedEnvironment 沙箱保护，详见第4.1、5.1节（Jinja2 特定绕过与 Python 沙箱逃逸）；遇到 Django 模板限制，详见第4.2节（Django 模板绕过）

**Java**
使用 FreeMarker 模板引擎时用户输入直接作为模板内容，详见：[Java_SSTI_Freemarker_Template_Include.md](Java_SSTI_Freemarker_Template_Include.md)
Velocity 模板引擎中用户可控的模板变量，详见：[Java_SSTI_Velocity_User_Controlled_Variable.md](Java_SSTI_Velocity_User_Controlled_Variable.md)
Thymeleaf 模板中表达式注入，详见：[Java_SSTI_Thymeleaf_Expression_Injection.md](Java_SSTI_Thymeleaf_Expression_Injection.md)
JSP EL 表达式注入，详见：[Java_SSTI_JSP_EL_Injection.md](Java_SSTI_JSP_EL_Injection.md)
Spring MVC 视图解析时用户输入作为模板路径，详见：[Java_SSTI_Spring_View_Resolution.md](Java_SSTI_Spring_View_Resolution.md)
遇到对象访问限制保护机制，详见 [bypassTricks.md](bypassTricks.md) 第2节（变量访问限制绕过）；遇到 FreeMarker 特定限制，详见第4.3节（FreeMarker 绕过，如 new 操作符利用）；遇到 Velocity 反射限制，详见第4.4节（Velocity 绕过）；遇到 SecurityManager 沙箱，详见第5.2节（Java 沙箱逃逸）

**Go**
使用 text/template 或 html/template 时用户输入直接嵌入模板，详见：[Go_SSTI_Text_Template_User_Input.md](Go_SSTI_Text_Template_User_Input.md)
模板执行时未限制函数调用，详见：[Go_SSTI_Template_Function_Call.md](Go_SSTI_Template_Function_Call.md)
动态模板加载时用户可控路径，详见：[Go_SSTI_Dynamic_Template_Load.md](Go_SSTI_Dynamic_Template_Load.md)
遇到模板语法过滤保护机制，详见 [bypassTricks.md](bypassTricks.md) 第1节（模板语法检测绕过，如特殊字符编码）；遇到危险函数调用限制，详见第3节（代码执行防护绕过）；遇到二阶注入场景，详见第8节（二阶注入绕过）

**PHP**
Smarty 模板引擎中用户输入作为模板变量，详见：[PHP_SSTI_Smarty_User_Variable.md](PHP_SSTI_Smarty_User_Variable.md)
Twig 模板中用户输入未转义，详见：[PHP_SSTI_Twig_Unescaped_Input.md](PHP_SSTI_Twig_Unescaped_Input.md)
原生 PHP 模板中 eval 或 include 用户输入，详见：[PHP_SSTI_Native_Eval_Include.md](PHP_SSTI_Native_Eval_Include.md)
Laravel Blade 模板中用户输入直接渲染，详见：[PHP_SSTI_Laravel_Blade_User_Input.md](PHP_SSTI_Laravel_Blade_User_Input.md)
遇到字符过滤或转义保护机制，详见 [bypassTricks.md](bypassTricks.md) 第1节（模板语法检测绕过，如编码技巧）；遇到变量黑名单限制，详见第2节（变量访问限制绕过，如字符串拼接）；遇到过滤器防护，详见第3.2节（过滤器链绕过）

**JavaScript / TypeScript (Node.js)**
使用 Handlebars 模板时用户输入作为模板内容，详见：[NodeJS_SSTI_Handlebars_User_Content.md](NodeJS_SSTI_Handlebars_User_Content.md)
EJS 模板引擎中用户输入未转义，详见：[NodeJS_SSTI_EJS_Unescaped_Input.md](NodeJS_SSTI_EJS_Unescaped_Input.md)
Mustache 模板中用户可控变量，详见：[NodeJS_SSTI_Mustache_User_Variable.md](NodeJS_SSTI_Mustache_User_Variable.md)
Pug 模板中用户输入作为模板代码，详见：[NodeJS_SSTI_Pug_Template_Code.md](NodeJS_SSTI_Pug_Template_Code.md)
Nunjucks 模板渲染时用户输入未过滤，详见：[NodeJS_SSTI_Nunjucks_Unfiltered_Input.md](NodeJS_SSTI_Nunjucks_Unfiltered_Input.md)
遇到 Handlebars prototype 限制保护，详见 [bypassTricks.md](bypassTricks.md) 第4.7节（Handlebars 绕过，如 lookup helper 利用）；遇到 EJS 转义防护，详见第4.5节（EJS 绕过，如 JavaScript 代码注入）；遇到 Pug 语法限制，详见第4.6节（Pug 绕过，如代码块利用）

**C/C++**
使用模板库（如 inja、Jinja2C++）时用户输入直接嵌入，详见：[C_SSTI_Template_Library_User_Input.md](C_SSTI_Template_Library_User_Input.md)
自定义模板解析器中用户输入作为模板代码执行，详见：[C_SSTI_Custom_Parser_Code_Execution.md](C_SSTI_Custom_Parser_Code_Execution.md)
遇到模板语法字符检测保护，详见 [bypassTricks.md](bypassTricks.md) 第1节（模板语法检测绕过，如编码与空白字符）；遇到自定义解析器防护逻辑，详见第2、3节（变量访问与代码执行防护绕过）

**Rust**
使用 Tera 模板引擎时用户输入未转义，详见：[Rust_SSTI_Tera_Unescaped_Input.md](Rust_SSTI_Tera_Unescaped_Input.md)
Askama 模板中用户可控变量，详见：[Rust_SSTI_Askama_User_Variable.md](Rust_SSTI_Askama_User_Variable.md)
自定义模板宏中用户输入作为模板内容，详见：[Rust_SSTI_Custom_Macro_User_Input.md](Rust_SSTI_Custom_Macro_User_Input.md)
遇到模板转义或过滤保护机制，详见 [bypassTricks.md](bypassTricks.md) 第1节（模板语法检测绕过）；遇到变量访问限制，详见第2节（变量访问限制绕过）；遇到条件/循环中的注入检测，详见第9节（条件和循环中的注入）

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-ssti-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

