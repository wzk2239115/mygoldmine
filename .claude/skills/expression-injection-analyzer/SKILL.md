---
name: expression-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证表达式注入（Expression Injection）漏洞；重点关注检测不安全的表达式解析和执行，即用户可控输入未经适当验证或过滤直接用于构造或执行表达式（如 SpEL、OGNL、模板表达式、EL 表达式等）；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用表达式注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：用户输入直接用于表达式构造（未过滤用户输入、直接拼接表达式代码）、表达式解析器配置不安全（允许执行任意代码、未禁用危险函数）、动态表达式求值（用户可控表达式内容、远程表达式加载）、表达式上下文污染（用户输入作为表达式变量、全局上下文注入）、表达式语言特性滥用（反射调用、方法调用、类型转换）、模板表达式注入（用户输入作为模板表达式、EL 表达式注入）、表达式过滤器不足（危险函数未禁用、自定义函数不安全）、表达式执行上下文不当（执行时权限过高、沙箱绕过）

**表达式注入（Expression Injection）**

**Attention**  
当项目中存在将用户可控输入直接用于构造或执行表达式的业务逻辑时，极易引发表达式注入漏洞。此类问题通常出现在动态配置解析、规则引擎、权限控制、数据绑定、模板渲染等涉及表达式求值的业务模块中，需重点审计表达式解析器的调用点，特别是用户输入未经过滤直接作为表达式内容或表达式变量的场景。常见的表达式语言包括 Spring SpEL、OGNL、JSP EL、JavaScript eval、Python eval/exec、模板表达式等。

**Early exit**  
若项目完全不使用任何表达式解析引擎（如纯静态配置、无动态求值逻辑、仅使用预编译的表达式），或所有表达式内容均为静态预定义且无任何用户输入参与表达式构造，则可快速退出对该漏洞类型的审计。

**Cases**

**Java**  
Spring SpEL 表达式中用户输入直接作为表达式内容，详见：[Java_Spring_SpEL_User_Input.md](Java_Spring_SpEL_User_Input.md)  
OGNL 表达式注入，用户可控的表达式字符串，详见：[Java_OGNL_Expression_Injection.md](Java_OGNL_Expression_Injection.md)  
JSP EL 表达式中用户输入未过滤，详见：[Java_JSP_EL_User_Input.md](Java_JSP_EL_User_Input.md)  
Spring Security 权限表达式中的注入风险，详见：[Java_Spring_Security_Expression_Injection.md](Java_Spring_Security_Expression_Injection.md)  
MVEL 表达式引擎中用户可控表达式，详见：[Java_MVEL_Expression_Injection.md](Java_MVEL_Expression_Injection.md)  
规则引擎（Drools、Easy Rules）中用户输入作为规则表达式，详见：[Java_Rule_Engine_Expression_Injection.md](Java_Rule_Engine_Expression_Injection.md)

**Python**  
使用 eval() 或 exec() 函数执行用户输入，详见：[Python_Eval_Exec_User_Input.md](Python_Eval_Exec_User_Input.md)  
Jinja2 模板表达式中的注入风险，详见：[Python_Jinja2_Expression_Injection.md](Python_Jinja2_Expression_Injection.md)  
Django 模板表达式中的用户输入，详见：[Python_Django_Template_Expression.md](Python_Django_Template_Expression.md)  
动态代码执行场景中的表达式注入，详见：[Python_Dynamic_Code_Execution.md](Python_Dynamic_Code_Execution.md)  
配置解析器（如 configparser）中的表达式注入，详见：[Python_Config_Parser_Expression.md](Python_Config_Parser_Expression.md)

**Go**  
使用 text/template 或 html/template 时表达式中的用户输入，详见：[Go_Template_Expression_Injection.md](Go_Template_Expression_Injection.md)  
动态表达式求值库中的注入风险，详见：[Go_Dynamic_Expression_Evaluation.md](Go_Dynamic_Expression_Evaluation.md)  
配置解析时用户输入作为表达式，详见：[Go_Config_Expression_Injection.md](Go_Config_Expression_Injection.md)

**PHP**  
使用 eval() 函数执行用户输入，详见：[PHP_Eval_User_Input.md](PHP_Eval_User_Input.md)  
Twig 模板表达式中的注入风险，详见：[PHP_Twig_Expression_Injection.md](PHP_Twig_Expression_Injection.md)  
Smarty 模板中的表达式注入，详见：[PHP_Smarty_Expression_Injection.md](PHP_Smarty_Expression_Injection.md)  
动态函数调用中的表达式注入，详见：[PHP_Dynamic_Function_Call.md](PHP_Dynamic_Function_Call.md)

**JavaScript / TypeScript (Node.js)**  
使用 eval() 或 Function() 构造函数执行用户输入，详见：[NodeJS_Eval_Function_User_Input.md](NodeJS_Eval_Function_User_Input.md)  
模板字符串中的表达式注入，详见：[NodeJS_Template_Literal_Expression.md](NodeJS_Template_Literal_Expression.md)  
EJS 模板表达式中的注入风险，详见：[NodeJS_EJS_Expression_Injection.md](NodeJS_EJS_Expression_Injection.md)  
Handlebars 表达式中的用户输入，详见：[NodeJS_Handlebars_Expression_Injection.md](NodeJS_Handlebars_Expression_Injection.md)  
动态代码执行场景中的表达式注入，详见：[NodeJS_Dynamic_Code_Execution.md](NodeJS_Dynamic_Code_Execution.md)

**C/C++**  
使用脚本引擎（如 Lua、JavaScript V8）时用户输入作为脚本表达式，详见：[C_Script_Engine_Expression_Injection.md](C_Script_Engine_Expression_Injection.md)  
自定义表达式解析器中的注入风险，详见：[C_Custom_Expression_Parser.md](C_Custom_Expression_Parser.md)  
配置解析时表达式注入，详见：[C_Config_Expression_Injection.md](C_Config_Expression_Injection.md)

**Rust**
使用 Tera 模板表达式中的用户输入，详见：[Rust_Tera_Expression_Injection.md](Rust_Tera_Expression_Injection.md)
动态表达式求值库中的注入风险，详见：[Rust_Dynamic_Expression_Evaluation.md](Rust_Dynamic_Expression_Evaluation.md)
配置解析时表达式注入，详见：[Rust_Config_Expression_Injection.md](Rust_Config_Expression_Injection.md)

---

## 表达式注入绕过技巧

在进行表达式注入漏洞审计时，特别是验证防护机制的有效性，需要了解常见的绕过技巧。参考详细的绕过技巧文档：[bypassTricks.md](bypassTricks.md)

### 常见防护机制及绕过指南

当审计过程中遇到以下防护机制时，应参考 bypassTricks.md 中的对应章节进行深度验证：

#### Java Spring SpEL 防护

**遇到 T() 函数被禁用**
→ 详见 [bypassTricks.md 第 1.1 节](bypassTricks.md#11-t-函数限制绕过)
绕过方向：使用对象属性获取类、@bean 引用、内置对象属性、绕过方法黑名单

**遇到 SimpleEvaluationContext 限制**
→ 详见 [bypassTricks.md 第 1.2 节](bypassTricks.md#12-simpleevaluationcontext-绕过)
绕过方向：属性访问链、方法调用绕过、函数注册绕过

**遇到关键字或方法名黑名单**
→ 详见 [bypassTricks.md 第 1.3 节](bypassTricks.md#13-spel-版本和实现差异)
绕过方向：Unicode 编码、字符串拼接、十进制转换、版本特定漏洞

#### Java OGNL 防护

**遇到 Runtime/ProcessBuilder 等危险类被禁用**
→ 详见 [bypassTricks.md 第 2.1 节](bypassTricks.md#21-黑名单绕过)
绕过方向：使用 ClassLoader、ProcessImpl、反射和字符串拼接

**遇到 Struts2 多层安全配置**
→ 详见 [bypassTricks.md 第 2.2 节](bypassTricks.md#22-struts2-特定绕过)
绕过方向：OGNL 注入点识别、双重编码和混淆

#### Java JSP EL 防护

**遇到 EL 表达式被禁用或函数限制**
→ 详见 [bypassTricks.md 第 3.1 节](bypassTricks.md#31-el-表达式过滤绕过)
绕过方向：getClass() 链、HttpServletRequest、ApplicationContext、上下文差异利用

**遇到 JSTL 标签限制**
→ 详见 [bypassTricks.md 第 3.2 节](bypassTricks.md#32-jstl-标签绕过)
绕过方向：动态标签库调用、forEach 中的表达式

#### Python Jinja2 防护

**遇到 __ 属性访问被禁用**
→ 详见 [bypassTricks.md 第 4.1 节](bypassTricks.md#41-属性访问限制绕过)
绕过方向：attr() 函数、编码绕过、对象属性链绕过

**遇到内置对象限制**
→ 详见 [bypassTricks.md 第 4.2 节](bypassTricks.md#42-jinja2-内置对象滥用)
绕过方向：内置过滤器和函数、字符串方法链、子类遍历

**遇到模板路径限制**
→ 详见 [bypassTricks.md 第 4.3 节](bypassTricks.md#43-jinja2-宏和包含绕过)
绕过方向：include/import 路径遍历、内存文件访问

#### Java Freemarker 防护

**遇到 ?new()、?api 等内置函数被禁用**
→ 详见 [bypassTricks.md 第 5.1 节](bypassTricks.md#51-内置函数-built-ins-绕过)
绕过方向：使用其他内置函数、反射调用绕过

**遇到数据模型限制**
→ 详见 [bypassTricks.md 第 5.2 节](bypassTricks.md#52-freemarker-数据模型注入)
绕过方向：利用数据模型对象、构造函数链

#### Python Django 防护

**遇到上下文变量过滤**
→ 详见 [bypassTricks.md 第 6.1 节](bypassTricks.md#61-上下文变量注入)
绕过方向：访问全局对象（request、settings）、对象方法调用、模板标签注入

**遇到模板继承限制**
→ 详见 [bypassTricks.md 第 6.2 节](bypassTricks.md#62-模板继承链注入)
绕过方向：基础模板污染、路径遍历、内存模板

#### 通用表达式引擎防护

**遇到表达式语法限制（允许的运算符列表）**
→ 详见 [bypassTricks.md 第 7.1 节](bypassTricks.md#71-表达式解析器限制绕过)
绕过方向：编码和混淆、字符串拼接、沙箱逃逸、原型链污染

#### 规则引擎防护

**遇到 Drools 规则内容限制**
→ 详见 [bypassTricks.md 第 8.1 节](bypassTricks.md#81-drools-规则注入)
绕过方向：规则条件注入、规则操作注入

#### 配置文件防护

**遇到 YAML/JSON 配置表达式动态求值**
→ 详见 [bypassTricks.md 第 9.1 节](bypassTricks.md#91-yamljson-配置表达式注入)
绕过方向：配置表达式注入、属性占位符注入

#### JavaScript / Node.js 防护

**遇到 eval() 或 Function() 构造函数被禁用**
→ 详见 [bypassTricks.md 第 10.1 节](bypassTricks.md#101-eval-和-function-绕过)
绕过方向：间接 eval 调用、模板字符串、vm 模块、Proxy、字符编码

**遇到 require 函数限制（Node.js）**
→ 详见 [bypassTricks.md 第 10.2 节](bypassTricks.md#102-nodejs-特定绕过)
绕过方向：global.require、process.mainModule.require、module.constructor._load、原型污染

#### PHP 防护

**遇到 eval()、assert()、create_function() 被禁用**
→ 详见 [bypassTricks.md 第 11.1 节](bypassTricks.md#111-eval-和动态函数调用绕过)
绕过方向：可变函数、回调函数、魔术方法、字符串拼接和编码

**遇到 Twig/Smarty 模板限制**
→ 详见 [bypassTricks.md 第 11.2 节](bypassTricks.md#112-twigsmarty-模板绕过)
绕过方向：过滤器链、_self 对象、{php} 标签

### 验证绕过有效性

在尝试绕过技巧时，务必：
1. **识别防护类型**：确定具体的防护机制（黑名单、白名单、沙箱等）
2. **选择对应绕过**：根据上述映射关系，查阅 bypassTricks.md 对应章节
3. **多次尝试**：一个绕过失败不代表防护有效，应尝试同一类别下的多种绕过方式
4. **组合绕过**：某些场景需要组合多种绕过技巧（如编码+反射+属性链）
5. **版本差异**：关注表达式引擎的版本差异，不同版本可能有不同的绕过方式

### 绕过技巧快速索引

| 防护机制类型 | 绕过难度 | 推荐尝试次数 | bypassTricks.md 章节 |
|------------|---------|------------|---------------------|
| 黑名单过滤 | 低 | 5-10 次 | 各章节 .1 小节 |
| 简单白名单 | 低-中 | 3-5 次 | 各章节 .1 小节 |
| 沙箱隔离 | 中 | 5-8 次 | 1.2, 4.1, 4.4, 7.1, 10.1 |
| 上下文限制 | 中 | 3-6 次 | 4.2, 6.1 |
| 内置函数禁用 | 中-高 | 5-10 次 | 4.1, 4.2, 5.1, 10.1, 11.1 |
| 版本特定防护 | 高 | 研究版本后尝试 | 1.3, 各章节 |
| eval/动态执行禁用 | 中 | 5-10 次 | 10.1, 11.1 |
| 反射/原型链限制 | 中-高 | 5-8 次 | 1.1, 2.1, 4.1, 10.2 |

### 重要提醒：多次尝试原则

**关键原则**：一次绕过失败不代表防护有效！

详见 [bypassTricks.md 第 13 节 - 审计时多次尝试的重要性](bypassTricks.md#审计时多次尝试的重要性)

在审计表达式注入漏洞时，必须进行**系统化、多轮次**的绕过尝试：

1. **第一轮**：直接尝试标准 payload
2. **第二轮**：编码变换（Unicode、十六进制、Base64、字符串拼接）
3. **第三轮**：间接访问（对象属性链、反射、原型链、构造函数）
4. **第四轮**：替代方法（替代类/方法、回调函数、过滤器、内置函数）
5. **第五轮**：组合技巧（多种绕过组合、版本特定漏洞、上下文注入）

每种防护机制至少尝试 **3-10 次**不同的绕过方式，才能确认防护的有效性。

在验证防护机制时，应使用这些绕过技巧来测试防护的鲁棒性。如果绕过成功，说明防护机制存在缺陷，应报告为高危漏洞。

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-expression-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

