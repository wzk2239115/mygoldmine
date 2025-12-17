---
name: code-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证代码注入（Code Injection）漏洞；重点关注检测不安全的代码执行，即用户可控输入未经适当验证或过滤直接用于动态代码执行、表达式求值、动态编译等操作；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用代码注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：用户输入直接用于代码执行（eval、exec、动态编译）、表达式求值注入（用户输入作为表达式、未限制表达式功能）、动态代码加载（用户可控代码路径、远程代码加载）、反序列化执行代码（不安全的反序列化、pickle/cPickle 执行）、代码拼接构造（字符串拼接构造代码、模板字符串构造代码）、沙箱绕过（沙箱限制不足、危险函数未禁用）、反射和元编程滥用（动态调用危险函数、反射执行用户输入）、代码生成和执行（动态生成代码、代码生成器注入）

**代码注入（Code Injection）**

**Attention**
代码注入漏洞源于应用程序将用户可控输入直接用于动态代码执行、表达式求值或动态编译等操作，导致攻击者可以执行任意代码。此类漏洞通常出现在动态脚本执行、表达式计算、代码生成、插件系统、规则引擎、配置解析等涉及代码动态执行的业务模块中，需重点审计 eval、exec、compile、Function、setTimeout、反序列化等危险 API 的调用点，特别是用户输入未经过滤直接作为代码内容或代码参数的场景。

**Early exit**
若项目完全不涉及任何动态代码执行（如纯静态内容、纯数据存储、无表达式求值、无代码生成、无插件系统、无规则引擎），或所有代码执行逻辑均为静态预定义且无任何用户输入参与代码构造，则可快速退出对该漏洞类型的审计。

**Cases**

**Python**
使用 eval() 函数直接执行用户输入，详见：[Python_CodeInjection_Eval_User_Input.md](Python_CodeInjection_Eval_User_Input.md)
使用 exec() 函数执行用户可控的代码字符串，详见：[Python_CodeInjection_Exec_User_Input.md](Python_CodeInjection_Exec_User_Input.md)
使用 compile() 函数动态编译用户输入，详见：[Python_CodeInjection_Compile_User_Input.md](Python_CodeInjection_Compile_User_Input.md)
使用 __import__() 动态导入用户可控模块，详见：[Python_CodeInjection_Import_User_Input.md](Python_CodeInjection_Import_User_Input.md)
pickle/cPickle 反序列化执行用户输入，详见：[Python_CodeInjection_Pickle_Deserialize.md](Python_CodeInjection_Pickle_Deserialize.md)
使用 yaml.load() 执行用户输入，详见：[Python_CodeInjection_YAML_Load.md](Python_CodeInjection_YAML_Load.md)
使用 marshal.loads() 反序列化用户输入，详见：[Python_CodeInjection_Marshal_Loads.md](Python_CodeInjection_Marshal_Loads.md)
使用 codecs.decode() 执行用户输入，详见：[Python_CodeInjection_Codecs_Decode.md](Python_CodeInjection_Codecs_Decode.md)

**Java**
使用 ScriptEngine 执行用户输入，详见：[Java_CodeInjection_ScriptEngine_User_Input.md](Java_CodeInjection_ScriptEngine_User_Input.md)
使用 GroovyShell 执行用户可控代码，详见：[Java_CodeInjection_GroovyShell_User_Input.md](Java_CodeInjection_GroovyShell_User_Input.md)
使用反射机制动态调用危险方法，详见：[Java_CodeInjection_Reflection_Dangerous_Method.md](Java_CodeInjection_Reflection_Dangerous_Method.md)
使用 Class.forName() 动态加载用户可控类，详见：[Java_CodeInjection_ClassForName_User_Input.md](Java_CodeInjection_ClassForName_User_Input.md)
使用 Runtime.getRuntime().exec() 执行用户输入（与命令注入重叠），详见：[Java_CodeInjection_RuntimeExec_User_Input.md](Java_CodeInjection_RuntimeExec_User_Input.md)
使用 JSP EL 表达式执行用户输入，详见：[Java_CodeInjection_JSP_EL_Expression.md](Java_CodeInjection_JSP_EL_Expression.md)
使用 SpEL 表达式执行用户输入，详见：[Java_CodeInjection_SpEL_Expression.md](Java_CodeInjection_SpEL_Expression.md)
使用 OGNL 表达式执行用户输入，详见：[Java_CodeInjection_OGNL_Expression.md](Java_CodeInjection_OGNL_Expression.md)

**Go**
使用 text/template 执行用户输入（与 SSTI 重叠），详见：[Go_CodeInjection_TextTemplate_User_Input.md](Go_CodeInjection_TextTemplate_User_Input.md)
使用 reflect 包动态调用用户可控方法，详见：[Go_CodeInjection_Reflect_Dynamic_Call.md](Go_CodeInjection_Reflect_Dynamic_Call.md)
使用 plugin 包动态加载用户可控插件，详见：[Go_CodeInjection_Plugin_User_Input.md](Go_CodeInjection_Plugin_User_Input.md)
使用 go/ast 和 go/parser 解析执行用户输入，详见：[Go_CodeInjection_AST_Parser_User_Input.md](Go_CodeInjection_AST_Parser_User_Input.md)

**PHP**
使用 eval() 函数直接执行用户输入，详见：[PHP_CodeInjection_Eval_User_Input.md](PHP_CodeInjection_Eval_User_Input.md)
使用 assert() 函数执行用户输入，详见：[PHP_CodeInjection_Assert_User_Input.md](PHP_CodeInjection_Assert_User_Input.md)
使用 create_function() 创建包含用户输入的匿名函数，详见：[PHP_CodeInjection_CreateFunction_User_Input.md](PHP_CodeInjection_CreateFunction_User_Input.md)
使用 preg_replace() 的 /e 修饰符执行用户输入，详见：[PHP_CodeInjection_PregReplace_E_Modifier.md](PHP_CodeInjection_PregReplace_E_Modifier.md)
使用 call_user_func() 调用用户可控函数，详见：[PHP_CodeInjection_CallUserFunc_User_Input.md](PHP_CodeInjection_CallUserFunc_User_Input.md)
使用 include/require 包含用户可控文件，详见：[PHP_CodeInjection_Include_User_Input.md](PHP_CodeInjection_Include_User_Input.md)
使用 unserialize() 反序列化执行用户输入，详见：[PHP_CodeInjection_Unserialize_User_Input.md](PHP_CodeInjection_Unserialize_User_Input.md)

**JavaScript / TypeScript (Node.js)**
使用 eval() 函数直接执行用户输入，详见：[NodeJS_CodeInjection_Eval_User_Input.md](NodeJS_CodeInjection_Eval_User_Input.md)
使用 Function() 构造函数执行用户输入，详见：[NodeJS_CodeInjection_Function_Constructor_User_Input.md](NodeJS_CodeInjection_Function_Constructor_User_Input.md)
使用 setTimeout/setInterval 执行用户输入，详见：[NodeJS_CodeInjection_SetTimeout_User_Input.md](NodeJS_CodeInjection_SetTimeout_User_Input.md)
使用 new Function() 动态创建函数执行用户输入，详见：[NodeJS_CodeInjection_NewFunction_User_Input.md](NodeJS_CodeInjection_NewFunction_User_Input.md)
使用 vm.runInContext() 执行用户输入，详见：[NodeJS_CodeInjection_VM_RunInContext_User_Input.md](NodeJS_CodeInjection_VM_RunInContext_User_Input.md)
使用 child_process.exec() 执行用户输入（与命令注入重叠），详见：[NodeJS_CodeInjection_ChildProcessExec_User_Input.md](NodeJS_CodeInjection_ChildProcessExec_User_Input.md)
使用 require() 动态加载用户可控模块，详见：[NodeJS_CodeInjection_Require_User_Input.md](NodeJS_CodeInjection_Require_User_Input.md)

**C/C++**
使用 system() 执行用户输入（与命令注入重叠），详见：[C_CodeInjection_System_User_Input.md](C_CodeInjection_System_User_Input.md)
使用 dlopen() 动态加载用户可控库，详见：[C_CodeInjection_Dlopen_User_Input.md](C_CodeInjection_Dlopen_User_Input.md)
使用 dlsym() 获取用户可控符号，详见：[C_CodeInjection_Dlsym_User_Input.md](C_CodeInjection_Dlsym_User_Input.md)
使用 exec 系列函数执行用户输入，详见：[C_CodeInjection_Exec_User_Input.md](C_CodeInjection_Exec_User_Input.md)

**Rust**
使用 unsafe 块执行用户输入，详见：[Rust_CodeInjection_Unsafe_User_Input.md](Rust_CodeInjection_Unsafe_User_Input.md)
使用动态库加载执行用户输入，详见：[Rust_CodeInjection_DynamicLib_User_Input.md](Rust_CodeInjection_DynamicLib_User_Input.md)
使用宏展开执行用户输入，详见：[Rust_CodeInjection_Macro_User_Input.md](Rust_CodeInjection_Macro_User_Input.md)

## 审计等级定义

代码注入漏洞审计采用分层的审计等级制度，根据动态代码执行的使用方式来指导审计深度。

| 等级 | 名称 | 时间 | 代码执行特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 无动态执行：无 eval/exec/Function，无动态代码生成 |
| **L1** | 快速扫描 | 3-5 分钟 | 有动态执行 + 沙箱隔离：需验证沙箱配置和输入限制 |
| **L2** | 跳读 | 5-10 分钟 | 动态执行 + 有过滤：需验证过滤规则完整性和白名单机制 |
| **L3** | 逐行读 | 15-30 分钟 | 直接执行用户输入：eval(userInput)、exec(userInput)、Function(userInput) |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：表达式引擎、插件系统、规则引擎、反序列化 |

### 快速判断流程

**第 1 步：是否存在动态代码执行？**
- 无动态执行（eval/exec/Function/compile） → L0 跳过
- 有动态执行 → 继续第 2 步

**第 2 步：用户输入是否参与代码构造？**
- 无用户输入，仅静态代码 → **L0**
- 用户输入参与 → 继续第 3 步

**第 3 步：是否有沙箱或过滤？**
- 有沙箱隔离 → **L1**
- 有过滤白名单 → **L2**
- 直接执行用户输入 → **L3+**
- 表达式引擎或插件系统 → **L4**

### 各等级操作指南

**L0**：无动态执行
```python
# 静态代码，无动态执行
result = calculate_price(quantity, unit_price)
```

**L1**：沙箱隔离
- 是否使用了安全的沙箱（如 RestrictedPython）？
- 沙箱配置是否正确（禁用危险函数）？
- 是否限制了执行时间和资源？
- 是否限制了可访问的模块和函数？
- **遇到 Python eval/exec 沙箱限制**：详见 [bypassTricks.md - 1. eval/exec 沙箱绕过](bypassTricks.md#1-evalexec-沙箱绕过)
- **遇到 PHP eval 黑名单过滤**：详见 [bypassTricks.md - PHP eval 防护绕过](bypassTricks.md#php-eval-防护绕过)
- **遇到 Java ScriptEngine 沙箱**：详见 [bypassTricks.md - Java ScriptEngine 防护绕过](bypassTricks.md#java-scriptengine-防护绕过)
- **遇到 Node.js vm 沙箱**：详见 [bypassTricks.md - 10. Node.js vm 模块绕过](bypassTricks.md#10-nodejs-vm-模块绕过)

**L2**：有过滤
- 是否使用了白名单验证？
- 过滤规则是否覆盖所有危险字符和关键字？
- 是否限制了表达式的复杂度？
- 是否验证了输入格式？
- **遇到字符黑名单过滤**：详见 [bypassTricks.md - 9. 代码注入 WAF 绕过](bypassTricks.md#9-代码注入-waf-绕过)
- **遇到关键字过滤**：详见 [bypassTricks.md - 编码和动态加载绕过](bypassTricks.md#14-编码和动态加载绕过)

**L3**：直接执行
```python
# 直接执行用户输入
eval(user_input)  // 高风险
exec(user_code)  // 高风险
Function(user_code)()  // 高风险
compile(user_input, '<string>', 'exec')  // 高风险
```
完整分析代码执行流程，追踪数据流，确认注入点
- **遇到 eval/exec 直接执行用户输入**：详见 [bypassTricks.md - 1. eval/exec 沙箱绕过](bypassTricks.md#1-evalexec-沙箱绕过)
- **遇到 Function() 构造函数执行**：详见 [bypassTricks.md - 10. Node.js vm 模块绕过](bypassTricks.md#10-nodejs-vm-模块绕过)

**L4**：复杂链路
- 表达式引擎：SpEL、OGNL、EL、MVEL 等
  - **遇到 Spring SpEL 表达式注入**：详见 [bypassTricks.md - Spring SpEL 防护绕过](bypassTricks.md#spring-spel-防护绕过)
  - **遇到 OGNL 表达式注入**：详见 [bypassTricks.md - OGNL 防护绕过](bypassTricks.md#ognl-防护绕过)
- 插件系统：动态加载插件、用户可控插件路径
  - **遇到动态库加载限制**：详见 [bypassTricks.md - Rust 宏和 unsafe 绕过](bypassTricks.md#13-rust-宏和-unsafe-绕过)
- 规则引擎：动态规则执行、用户定义规则
- 反序列化：pickle、yaml.load、unserialize
  - **遇到 Python pickle 反序列化**：详见 [bypassTricks.md - Python pickle 防护绕过](bypassTricks.md#python-pickle-防护绕过)
  - **遇到 PHP unserialize 反序列化**：详见 [bypassTricks.md - PHP unserialize 防护绕过](bypassTricks.md#php-unserialize-防护绕过)
- 模板引擎：用户可控模板内容（SSTI）
  - **遇到 Jinja2 模板注入**：详见 [bypassTricks.md - Jinja2 模板绕过](bypassTricks.md#jinja2-模板绕过)
  - **遇到 Thymeleaf 模板注入**：详见 [bypassTricks.md - Thymeleaf 模板绕过](bypassTricks.md#thymeleaf-模板绕过)
  - **遇到 Go text/template 注入**：详见 [bypassTricks.md - 11. Go 模板注入绕过](bypassTricks.md#11-go-模板注入绕过)
  - **遇到 Ruby ERB 模板注入**：详见 [bypassTricks.md - 12. Ruby ERB 模板绕过](bypassTricks.md#12-ruby-erb-模板绕过)
- 反射：动态方法调用、动态类加载
  - **遇到 Java 反射限制**：详见 [bypassTricks.md - Java 反射限制绕过](bypassTricks.md#java-反射限制绕过)
  - **遇到动态方法调用**：详见 [bypassTricks.md - 8. 动态方法和反射调用绕过](bypassTricks.md#8-动态方法和反射调用绕过)

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 无动态代码执行 | L0 | 无风险 |
| 沙箱隔离执行 | L1 | 验证沙箱配置 |
| 白名单过滤 | L2 | 验证过滤规则 |
| 直接执行用户输入 | L3 | 高风险 |
| 表达式引擎或插件系统 | L4 | 完整追踪 |
| 不安全反序列化 | L4 | 完整追踪 |
```

## 代码注入绕过技巧

在进行代码注入漏洞审计时，特别是 L1-L4 等级的深度审计，需要验证防护机制的有效性。参考详细的绕过技巧文档：[bypassTricks.md](bypassTricks.md)

该文档包含：
- **1. eval/exec 沙箱绕过**（Python、PHP、Java）
  - **遇到 Python `__builtins__` 限制**：详见 [bypassTricks.md - 1.1 对象属性访问绕过](bypassTricks.md#11-对象属性访问绕过)
  - **遇到导入模块限制**：详见 [bypassTricks.md - 1.2 导入模块绕过](bypassTricks.md#12-导入模块绕过)
  - **遇到关键字黑名单**：详见 [bypassTricks.md - 1.4 编码和动态加载绕过](bypassTricks.md#14-编码和动态加载绕过)
  - **遇到字符串过滤**：详见 [bypassTricks.md - 1.5 bytes 和 bytearray 绕过](bypassTricks.md#15-bytes-和-bytearray-绕过)
  - **遇到格式化字符串限制**：详见 [bypassTricks.md - 1.6 格式化字符串绕过](bypassTricks.md#16-格式化字符串绕过)

- **2. 表达式注入绕过**（SpEL、OGNL、EL）
  - **遇到 Spring SpEL T() 函数限制**：详见 [bypassTricks.md - 4.1 绕过 T() 函数限制](bypassTricks.md#41-绕过-t-函数限制)
  - **遇到 OGNL 关键字黑名单**：详见 [bypassTricks.md - 5.1 使用 ClassLoader 绕过](bypassTricks.md#51-使用-classloader-绕过)

- **3. 模板注入绕过**（Jinja2、Thymeleaf、Go、Ruby）
  - **遇到 Jinja2 `__` 字符过滤**：详见 [bypassTricks.md - 6.1 属性访问绕过](bypassTricks.md#61-属性访问绕过)
  - **遇到 Thymeleaf 表达式限制**：详见 [bypassTricks.md - 7.1 使用 Spring EL 绕过](bypassTricks.md#71-使用-spring-el-绕过)
  - **遇到 Go template 反射限制**：详见 [bypassTricks.md - 16.1 反射绕过](bypassTricks.md#161-反射绕过)
  - **遇到 Ruby ERB 安全级别限制**：详见 [bypassTricks.md - 17.1 对象方法绕过](bypassTricks.md#171-对象方法绕过)

- **4. 命令注入绕过**
  - **遇到特殊字符黑名单**：详见 [bypassTricks.md - 8.1 编码绕过](bypassTricks.md#81-编码绕过)
  - **遇到变量替换限制**：详见 [bypassTricks.md - 8.2 变量替换绕过](bypassTricks.md#82-变量替换绕过)

- **5. 反序列化注入绕过**
  - **遇到 Python pickle 协议版本限制**：详见 [bypassTricks.md - 9.1 Gadget Chain 链接](bypassTricks.md#91-gadget-chain-链接)
  - **遇到 PHP unserialize allowed_classes 限制**：详见 [bypassTricks.md - 10.1 POP Chain 链接](bypassTricks.md#101-pop-chain-链接)

- **6. 文件包含注入绕过**
  - **遇到后缀白名单限制**：详见 [bypassTricks.md - 11.1 包装器和 null 字节绕过](bypassTricks.md#111-包装器和-null-字节绕过)

- **7. 动态方法和反射调用绕过**
  - **遇到 Java SecurityManager 限制**：详见 [bypassTricks.md - 13.1 MethodHandle 绕过](bypassTricks.md#131-methodhandle-绕过)

- **8. WAF 绕过技巧**
  - **遇到 WAF 规则检测**：详见 [bypassTricks.md - 14.1 多重编码](bypassTricks.md#141-多重编码)
  - **遇到大小写敏感检测**：详见 [bypassTricks.md - 14.2 大小写混合](bypassTricks.md#142-大小写混合)

- **9. Node.js vm 沙箱绕过**
  - **遇到 vm.runInNewContext 沙箱**：详见 [bypassTricks.md - 15.1 原型链污染绕过](bypassTricks.md#151-原型链污染绕过)
  - **遇到上下文隔离**：详见 [bypassTricks.md - 15.2 上下文逃逸](bypassTricks.md#152-上下文逃逸)

- **10. Rust 和底层语言绕过**
  - **遇到 Rust unsafe 限制**：详见 [bypassTricks.md - 18.1 宏展开绕过](bypassTricks.md#181-宏展开绕过)
  - **遇到 FFI 调用限制**：详见 [bypassTricks.md - 18.2 FFI 和动态库绕过](bypassTricks.md#182-ffi-和动态库绕过)

- **11. 沙箱逃逸通用技巧**
  - **遇到资源限制（CPU/内存）**：详见 [bypassTricks.md - 19.1 资源限制绕过](bypassTricks.md#191-资源限制绕过)
  - **遇到文件系统访问限制**：详见 [bypassTricks.md - 19.2 文件系统访问绕过](bypassTricks.md#192-文件系统访问绕过)
  - **遇到网络访问限制**：详见 [bypassTricks.md - 19.3 网络访问绕过](bypassTricks.md#193-网络访问绕过)

在验证防护机制时，应使用这些绕过技巧来测试防护的鲁棒性。针对不同的保护机制，选择对应章节的绕过方法进行测试。

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-code-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

