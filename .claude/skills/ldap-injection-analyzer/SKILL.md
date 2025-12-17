---
name: ldap-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 LDAP 注入漏洞；重点关注检测不安全的 LDAP 查询构造，即用户可控输入未经适当验证或过滤直接用于构造 LDAP 查询（DN、过滤器等）；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 LDAP 注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：LDAP 过滤器直接拼接（用户输入直接拼接到过滤器字符串）、DN（Distinguished Name）注入（用户输入直接用于构造 DN、未转义特殊字符，详见 [bypassTricks.md § 2. DN 注入绕过](bypassTricks.md#2-dndistinguished-name注入绕过)）、过滤器操作符注入（&、|、! 等逻辑操作符可控，详见 [bypassTricks.md § 1.2 逻辑操作符注入](bypassTricks.md#12-逻辑操作符注入)）、属性值注入（用户输入直接作为属性值、未转义括号和星号，详见 [bypassTricks.md § 1.3 属性值绕过](bypassTricks.md#13-属性值绕过)）、通配符注入（* 通配符可控、导致权限绕过，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)）、转义字符处理不当（反斜杠转义缺失、特殊字符未过滤，详见 [bypassTricks.md § 3. 转义和编码绕过](bypassTricks.md#3-转义和编码绕过)）、多过滤器组合注入（多个过滤器拼接、逻辑操作符滥用）、LDAP 查询参数化缺失（未使用参数化查询、直接字符串拼接，详见 [bypassTricks.md § 5. 参数化查询绕过](bypassTricks.md#5-参数化查询绕过)）、输入验证不足（仅客户端验证、黑名单不完整，详见 [bypassTricks.md § 4. 输入验证绕过](bypassTricks.md#4-输入验证绕过)）、编码绕过（URL 编码、Unicode 编码绕过过滤，详见 [bypassTricks.md § 7. 编码和规范化绕过](bypassTricks.md#7-编码和规范化绕过)）、二阶 LDAP 注入（查询结果用于构造新查询，详见 [bypassTricks.md § 6. 二阶 LDAP 注入](bypassTricks.md#6-二阶-ldap-注入)）、LDAP 查询结果处理不当（结果未验证、敏感信息泄露）

**LDAP 注入漏洞**

**Attention**  
当项目中使用了 LDAP（轻量级目录访问协议）进行用户认证、目录服务查询、组织架构管理等功能，并将用户可控输入未经安全处理直接用于构造 LDAP 查询（DN、过滤器等）时，极易引发 LDAP 注入漏洞。此类问题通常出现在用户登录认证、用户信息查询、组织架构查询、权限验证等涉及 LDAP 查询的业务模块中，需重点审计动态构造 LDAP 查询的代码路径。

**Early exit**  
若项目完全未使用 LDAP 服务（如仅使用关系型数据库进行用户认证、无目录服务功能）、或所有 LDAP 查询均通过完全参数化方式（使用参数化查询且确保无字符串拼接）、或前端为纯静态页面无后端逻辑，则可快速退出对该漏洞类型的审计。

**Cases**

**Java**
使用 javax.naming.directory.DirContext 时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[Java_DirContext_Filter_Concat.md](Java_DirContext_Filter_Concat.md)
使用 Spring LDAP 框架时，LDAP 查询中用户输入未转义直接使用，详见：[Java_Spring_LDAP_Injection.md](Java_Spring_LDAP_Injection.md)；遇到 LdapQueryBuilder 保护机制，详见 [bypassTricks.md § 9.1 Spring LDAP 框架](bypassTricks.md#91-spring-ldap-框架)
使用 UnboundID LDAP SDK 时，过滤器构造时用户输入未验证，详见：[Java_UnboundID_Filter_Injection.md](Java_UnboundID_Filter_Injection.md)
使用 Apache Directory API 时，DN 构造中用户输入未转义，详见：[Java_Apache_Directory_DN_Injection.md](Java_Apache_Directory_DN_Injection.md)；遇到 DN 转义保护机制，详见 [bypassTricks.md § 2. DN 注入绕过](bypassTricks.md#2-dndistinguished-name注入绕过)
使用 JNDI 进行 LDAP 查询时，搜索过滤器未参数化，详见：[Java_JNDI_LDAP_Search_Injection.md](Java_JNDI_LDAP_Search_Injection.md)；遇到字符串拼接保护机制，详见 [bypassTricks.md § 5.1 部分参数化](bypassTricks.md#51-部分参数化)

**Python**
使用 ldap3 库时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[Python_Ldap3_Filter_Concat.md](Python_Ldap3_Filter_Concat.md)；遇到字符串拼接保护机制，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)
使用 python-ldap 库时，LDAP 查询中用户输入未转义，详见：[Python_PythonLdap_Injection.md](Python_PythonLdap_Injection.md)；遇到转义保护机制，详见 [bypassTricks.md § 3. 转义和编码绕过](bypassTricks.md#3-转义和编码绕过)
使用 ldap.filter 时，过滤器构造时用户输入未验证，详见：[Python_LdapFilter_Injection.md](Python_LdapFilter_Injection.md)；遇到输入验证保护机制，详见 [bypassTricks.md § 4. 输入验证绕过](bypassTricks.md#4-输入验证绕过)
Django 框架中使用 LDAP 进行用户认证时，用户输入直接用于构造查询，详见：[Python_Django_LDAP_Auth_Injection.md](Python_Django_LDAP_Auth_Injection.md)；遇到 django-ldap 认证保护机制，详见 [bypassTricks.md § 9.2 Django LDAP 认证](bypassTricks.md#92-django-ldap-认证)
Flask 框架中使用 LDAP 进行目录服务查询时，过滤器未参数化，详见：[Python_Flask_LDAP_Query_Injection.md](Python_Flask_LDAP_Query_Injection.md)；遇到黑名单保护机制，详见 [bypassTricks.md § 4.2 黑名单绕过](bypassTricks.md#42-黑名单绕过)

**JavaScript (Node.js)**
使用 ldapjs 库时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[NodeJS_Ldapjs_Filter_Concat.md](NodeJS_Ldapjs_Filter_Concat.md)；遇到 ldapjs 伪参数化保护机制，详见 [bypassTricks.md § 9.3 Express/Node.js LDAP](bypassTricks.md#93-expressnodejs-ldap)
使用 activedirectory 库时，LDAP 查询中用户输入未转义，详见：[NodeJS_Activedirectory_Injection.md](NodeJS_Activedirectory_Injection.md)；遇到 Active Directory 特定保护机制，详见 [bypassTricks.md § 8.1 OpenLDAP vs Active Directory](bypassTricks.md#81-openldap-vs-active-directory)
使用 ldap-filters 库时，过滤器构造时用户输入未验证，详见：[NodeJS_LdapFilters_Injection.md](NodeJS_LdapFilters_Injection.md)；遇到过滤器验证保护机制，详见 [bypassTricks.md § 4.3 正则表达式绕过](bypassTricks.md#43-正则表达式绕过)
Express 框架中使用 LDAP 进行用户认证时，用户输入直接用于构造查询，详见：[NodeJS_Express_LDAP_Auth_Injection.md](NodeJS_Express_LDAP_Auth_Injection.md)；遇到中间件链保护机制，详见 [bypassTricks.md § 9.3 Express/Node.js LDAP](bypassTricks.md#93-expressnodejs-ldap)

**TypeScript**
使用 ldapjs 库时，类型不安全的 LDAP 过滤器构造，详见：[TypeScript_Ldapjs_Type_Unsafe.md](TypeScript_Ldapjs_Type_Unsafe.md)；遇到类型系统保护机制，详见 [bypassTricks.md § 9.3 Express/Node.js LDAP](bypassTricks.md#93-expressnodejs-ldap)
使用 @ldapjs/filters 时，过滤器构造时用户输入未验证，详见：[TypeScript_LdapjsFilters_Injection.md](TypeScript_LdapjsFilters_Injection.md)；遇到过滤器 API 保护机制，详见 [bypassTricks.md § 5.2 参数化 API 错误使用](bypassTricks.md#52-参数化-api-错误使用)
NestJS 框架中使用 LDAP 进行用户认证时，用户输入直接用于构造查询，详见：[TypeScript_NestJS_LDAP_Auth_Injection.md](TypeScript_NestJS_LDAP_Auth_Injection.md)；遇到框架注入保护机制，详见 [bypassTricks.md § 9.3 Express/Node.js LDAP](bypassTricks.md#93-expressnodejs-ldap)

**PHP**
使用 ldap_search 函数时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[PHP_LdapSearch_Filter_Concat.md](PHP_LdapSearch_Filter_Concat.md)；遇到字符串拼接保护机制，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)
使用 ldap_list 和 ldap_read 时，LDAP 查询中用户输入未转义，详见：[PHP_LdapList_Read_Injection.md](PHP_LdapList_Read_Injection.md)；遇到函数级保护机制，详见 [bypassTricks.md § 3.1 转义函数绕过](bypassTricks.md#31-转义函数绕过)
使用 ldap_escape 函数但转义不完整，详见：[PHP_LdapEscape_Incomplete.md](PHP_LdapEscape_Incomplete.md)；遇到 ldap_escape 保护机制，详见 [bypassTricks.md § 3.1 转义函数绕过](bypassTricks.md#31-转义函数绕过)
Laravel 框架中使用 LDAP 进行用户认证时，用户输入直接用于构造查询，详见：[PHP_Laravel_LDAP_Auth_Injection.md](PHP_Laravel_LDAP_Auth_Injection.md)；遇到框架级保护机制，详见 [bypassTricks.md § 4.2 黑名单绕过](bypassTricks.md#42-黑名单绕过)
Symfony 框架中使用 LDAP 进行目录服务查询时，过滤器未参数化，详见：[PHP_Symfony_LDAP_Query_Injection.md](PHP_Symfony_LDAP_Query_Injection.md)；遇到组件级保护机制，详见 [bypassTricks.md § 5.1 部分参数化](bypassTricks.md#51-部分参数化)

**Go**
使用 go-ldap 库时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[Go_GoLdap_Filter_Concat.md](Go_GoLdap_Filter_Concat.md)；遇到字符串拼接保护机制，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)
使用 ldap/v3 包时，LDAP 查询中用户输入未转义，详见：[Go_LdapV3_Injection.md](Go_LdapV3_Injection.md)；遇到转义保护机制，详见 [bypassTricks.md § 3. 转义和编码绕过](bypassTricks.md#3-转义和编码绕过)
Gin 框架中使用 LDAP 进行用户认证时，用户输入直接用于构造查询，详见：[Go_Gin_LDAP_Auth_Injection.md](Go_Gin_LDAP_Auth_Injection.md)；遇到框架级验证保护机制，详见 [bypassTricks.md § 4. 输入验证绕过](bypassTricks.md#4-输入验证绕过)
自定义 LDAP 查询构建器的不安全实现，详见：[Go_Custom_LDAP_Query_Builder.md](Go_Custom_LDAP_Query_Builder.md)；遇到自定义构建器保护机制，详见 [bypassTricks.md § 5.2 参数化 API 错误使用](bypassTricks.md#52-参数化-api-错误使用)

**C/C++**
使用 OpenLDAP 库时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[C_OpenLDAP_Filter_Concat.md](C_OpenLDAP_Filter_Concat.md)；遇到 OpenLDAP 特定保护机制，详见 [bypassTricks.md § 8.1 OpenLDAP vs Active Directory](bypassTricks.md#81-openldap-vs-active-directory)
使用 ldap_search_ext_s 函数时，LDAP 查询中用户输入未转义，详见：[C_LdapSearchExt_Injection.md](C_LdapSearchExt_Injection.md)；遇到字符串操作保护机制，详见 [bypassTricks.md § 3.2 多层转义绕过](bypassTricks.md#32-多层转义绕过)
使用 ldap_init 和 ldap_search 组合时，过滤器构造时用户输入未验证，详见：[C_LdapInit_Search_Injection.md](C_LdapInit_Search_Injection.md)；遇到缓冲区操作保护机制，详见 [bypassTricks.md § 3.3 字符编码绕过](bypassTricks.md#33-字符编码绕过)
自定义 LDAP 客户端的不安全实现，详见：[C_Custom_LDAP_Client_Injection.md](C_Custom_LDAP_Client_Injection.md)；遇到自定义实现保护机制，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)

**Rust**
使用 ldap3 库时，用户输入直接拼接到 LDAP 过滤器字符串中，详见：[Rust_Ldap3_Filter_Concat.md](Rust_Ldap3_Filter_Concat.md)；遇到字符串拼接保护机制，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)
使用 ldap-rs 库时，LDAP 查询中用户输入未转义，详见：[Rust_LdapRs_Injection.md](Rust_LdapRs_Injection.md)；遇到类型系统保护机制，详见 [bypassTricks.md § 3. 转义和编码绕过](bypassTricks.md#3-转义和编码绕过)
自定义 LDAP 查询构建器的不安全实现，详见：[Rust_Custom_LDAP_Query_Builder.md](Rust_Custom_LDAP_Query_Builder.md)；遇到自定义构建器保护机制，详见 [bypassTricks.md § 5.2 参数化 API 错误使用](bypassTricks.md#52-参数化-api-错误使用)

## LDAP 注入绕过技巧

在进行 LDAP 注入漏洞审计时，特别是验证防护机制的有效性，需要了解常见的绕过技巧。参考详细的绕过技巧文档：[bypassTricks.md](bypassTricks.md)

该文档包含：
- **LDAP 过滤器注入绕过**（逻辑操作符注入、通配符注入、过滤器组合）
  - 遇到黑名单过滤特殊字符保护，详见 [bypassTricks.md § 1.1 特殊字符过滤绕过](bypassTricks.md#11-特殊字符过滤绕过)
  - 遇到括号平衡检查保护，详见 [bypassTricks.md § 1.2 逻辑操作符注入](bypassTricks.md#12-逻辑操作符注入)
  - 遇到输入长度或模式检查保护，详见 [bypassTricks.md § 1.3 属性值绕过](bypassTricks.md#13-属性值绕过)
- **DN（Distinguished Name）注入绕过**（特殊字符注入、DN 构造绕过）
  - 遇到等号和逗号检查保护，详见 [bypassTricks.md § 2.1 DN 组件注入](bypassTricks.md#21-dn-组件注入)
  - 遇到加号和等号检查保护，详见 [bypassTricks.md § 2.2 多值 RDN 注入](bypassTricks.md#22-多值-rdn-注入)
  - 遇到基本 DN 验证保护，详见 [bypassTricks.md § 2.3 基本 DN 注入](bypassTricks.md#23-基本-dn-注入)
- **转义和编码绕过**（转义字符处理不当、编码绕过过滤）
  - 遇到 ldap_escape 等转义函数保护，详见 [bypassTricks.md § 3.1 转义函数绕过](bypassTricks.md#31-转义函数绕过)
  - 遇到单层转义保护，详见 [bypassTricks.md § 3.2 多层转义绕过](bypassTricks.md#32-多层转义绕过)
  - 遇到编码规范化保护，详见 [bypassTricks.md § 3.3 字符编码绕过](bypassTricks.md#33-字符编码绕过)
- **输入验证绕过**（黑名单绕过、正则表达式绕过）
  - 遇到客户端验证保护，详见 [bypassTricks.md § 4.1 客户端验证绕过](bypassTricks.md#41-客户端验证绕过)
  - 遇到黑名单特定字符保护，详见 [bypassTricks.md § 4.2 黑名单绕过](bypassTricks.md#42-黑名单绕过)
  - 遇到正则表达式验证保护，详见 [bypassTricks.md § 4.3 正则表达式绕过](bypassTricks.md#43-正则表达式绕过)
- **参数化查询绕过**（参数化实现缺陷、字符串拼接残留）
  - 遇到部分参数化保护，详见 [bypassTricks.md § 5.1 部分参数化](bypassTricks.md#51-部分参数化)
  - 遇到参数化 API 保护，详见 [bypassTricks.md § 5.2 参数化 API 错误使用](bypassTricks.md#52-参数化-api-错误使用)
- **二阶 LDAP 注入**（查询结果用于构造新查询）
  - 遇到数据库存储反射保护，详见 [bypassTricks.md § 6.1 数据库存储注入](bypassTricks.md#61-数据库存储注入)
  - 遇到 LDAP 结果反射保护，详见 [bypassTricks.md § 6.2 LDAP 结果反射](bypassTricks.md#62-ldap-结果反射)
- **编码和规范化绕过**（URL 编码、Unicode 编码、大小写变化）
  - 遇到 UTF-8 编码验证保护，详见 [bypassTricks.md § 7.1 编码不一致](bypassTricks.md#71-编码不一致)
  - 遇到大小写转换保护，详见 [bypassTricks.md § 7.2 大小写规范化绕过](bypassTricks.md#72-大小写规范化绕过)
- **LDAP 服务器特定绕过**（Active Directory、OpenLDAP、Apache Directory）
  - 遇到 OpenLDAP 或 Active Directory 特定保护，详见 [bypassTricks.md § 8.1 OpenLDAP vs Active Directory](bypassTricks.md#81-openldap-vs-active-directory)
  - 遇到 LDAP 版本差异保护，详见 [bypassTricks.md § 8.2 LDAP 版本差异](bypassTricks.md#82-ldap-版本差异)
  - 遇到扩展和自定义属性保护，详见 [bypassTricks.md § 8.3 扩展和自定义属性](bypassTricks.md#83-扩展和自定义属性)
- **框架特定绕过**（Java/JNDI、Python/ldap3、Node.js/ldapjs、PHP、Go）
  - 遇到 Spring LDAP 框架保护，详见 [bypassTricks.md § 9.1 Spring LDAP 框架](bypassTricks.md#91-spring-ldap-框架)
  - 遇到 Django LDAP 认证保护，详见 [bypassTricks.md § 9.2 Django LDAP 认证](bypassTricks.md#92-django-ldap-认证)
  - 遇到 Express/Node.js LDAP 保护，详见 [bypassTricks.md § 9.3 Express/Node.js LDAP](bypassTricks.md#93-expressnodejs-ldap)
- **防护机制检查清单和审计建议**
  - 高风险指标、审计步骤、验证修复，详见 [bypassTricks.md § 10-11](bypassTricks.md#10-防护机制检查清单)

在验证防护机制时，应使用这些绕过技巧来测试防护的鲁棒性。特别需要注意：
1. **黑名单过滤**：通常可通过编码、大小写混合、十六进制转义绕过
2. **客户端验证**：可通过直接 HTTP 请求或禁用 JavaScript 绕过
3. **不完整转义**：检查 DN 和过滤器是否都进行了转义
4. **部分参数化**：混合使用参数化和非参数化代码路径
5. **框架默认行为**：某些框架的参数化 API 实现可能不完整
6. **二阶注入**：检查从数据库或 LDAP 检索的数据是否再次用于构造查询

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-ldap-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

