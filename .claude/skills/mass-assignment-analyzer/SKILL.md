---
name: mass-assignment-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证批量赋值（Mass Assignment）风险；重点关注对象属性在反序列化、ORM 映射或表单自动绑定时被外部输入覆盖敏感字段的路径，结合按编程语言组织的参考指南定位高危点。
---

**Attention**  
当服务端框架支持根据入参自动填充模型（表单、JSON、XML、YAML 等），而未对可写属性施加白名单或敏感字段保护时，攻击者可通过额外提交字段覆盖权限标记、金额、角色、状态等字段，触发批量赋值漏洞，导致越权操作、数据污染甚至接管账号。需重点审计所有自动绑定 DTO/实体、ORM `update`/`save`、反序列化到结构体/对象的路径，以及多租户系统中的跨租户字段。

**Early exit**

**在开始审计之前，必须首先运行批量赋值扫描脚本完成初步检索**，快速定位项目中可能存在的自动映射/自动绑定位置。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行批量赋值扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

若项目完全不使用自动映射/自动绑定（全部手动赋值）、或仅处理只读数据流、或后端已全局启用严格字段白名单并对敏感字段设置不可写属性，且经确认无任何绕过方式，则可快速结束该漏洞类型的审计。

---

## 通用批量赋值漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：自动数据绑定缺乏字段白名单（直接绑定未限制、DTO未隔离、黑名单代替白名单）、敏感字段未设置只读保护（权限角色、状态审核、金额余额、身份所有权、时间戳）、ORM批量更新接受未过滤输入（直接使用用户输入、字典/Map更新、白名单不完整）、反序列化未限制可写字段（JSON/XML反序列化、序列化器未控制）、对象合并或属性复制未验证来源（对象合并、反射赋值）、配置热更新或参数覆盖缺乏验证（配置更新、环境变量）、GraphQL输入类型未限制字段（输入包含敏感字段、直接传入ORM）、多层嵌套对象未递归验证（嵌套对象、关联对象、数组元素）

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的自动数据绑定和 ORM 实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
常见于 Spring MVC、Spring Boot、Struts、Play Framework 等使用数据绑定时，未对敏感字段设置 `@JsonIgnore`、`@JsonProperty(access = READ_ONLY)` 或 `@InitBinder` 白名单；JPA/Hibernate 的 `save`/`merge` 直接接受用户输入实体也会造成越权更新。  
- Spring 数据绑定字段白名单配置，详见：[java_spring_data_binding.md](java_spring_data_binding.md)  
- Hibernate/JPA 批量更新越权场景，详见：[java_hibernate_mass_assignment.md](java_hibernate_mass_assignment.md)  
- Jackson 反序列化保护敏感字段指南，详见：[java_jackson_mass_assignment.md](java_jackson_mass_assignment.md)

**Python**  
常见于 Django、Flask + Marshmallow/Pydantic、FastAPI 等框架使用模型序列化器或 `ModelForm`/`Schema` 自动创建对象时，未设置 `fields`/`exclude`/`read_only` 导致敏感字段被覆盖；ORM `update`/`bulk_update` 接收未经筛选的字典也会引入风险。  
- Django ModelForm/Serializer 字段白名单示例，详见：[python_django_mass_assignment.md](python_django_mass_assignment.md)  
- FastAPI/Pydantic 模型写保护配置，详见：[python_fastapi_mass_assignment.md](python_fastapi_mass_assignment.md)  
- SQLAlchemy 字典更新越权排查要点，详见：[python_sqlalchemy_mass_assignment.md](python_sqlalchemy_mass_assignment.md)

**Go**  
常见于 Gin/Echo/Beego 等框架将 JSON 请求绑定到 `struct`，或使用 `mapstructure`, `json.Unmarshal` 自动填充结构体时，未通过自定义 `binding`/`json` 标签限制字段；GORM 的 `Updates` 接收 `map` 时未过滤敏感字段也会导致越权更新。  
- Gin 绑定结构体字段控制实践，详见：[go_gin_binding_mass_assignment.md](go_gin_binding_mass_assignment.md)  
- GORM `Updates`/`Save` 过滤敏感字段指南，详见：[go_gorm_mass_assignment.md](go_gorm_mass_assignment.md)  
- 自定义解码器与反射赋值风险分析，详见：[go_reflect_mass_assignment.md](go_reflect_mass_assignment.md)

**PHP**  
常见于 Laravel、Symfony、CodeIgniter 等框架使用 `fill`、`create`、`update` 或请求自动绑定模型时，未设置 `$fillable`/`$guarded` 或 FormType 白名单；ORM 直接接受 `$_POST` 数据也会覆盖敏感字段。  
- Laravel 批量赋值保护策略，详见：[php_laravel_mass_assignment.md](php_laravel_mass_assignment.md)  
- Symfony Form/Serializer 字段控制要点，详见：[php_symfony_mass_assignment.md](php_symfony_mass_assignment.md)  
- 原生 PHP 模型 `hydrate` 越权案例分析，详见：[php_native_mass_assignment.md](php_native_mass_assignment.md)

**JavaScript (Node.js)**  
常见于 Express/Koa/Nest 搭配 Mongoose/Sequelize/Prisma 等 ORM 时，直接将 `req.body` 传入 `Model.update`/`create`；或使用类转对象工具（如 `Object.assign`, `lodash.merge`）时未过滤客户端传入的敏感属性。  
- Mongoose Schema 写保护与 `strict` 模式配置，详见：[js_mongoose_mass_assignment.md](js_mongoose_mass_assignment.md)  
- Sequelize/Prisma 更新白名单实践，详见：[js_sequelize_mass_assignment.md](js_sequelize_mass_assignment.md)  
- Node.js 对象合并导致越权更新案例，详见：[js_object_merge_mass_assignment.md](js_object_merge_mass_assignment.md)

**TypeScript**  
常见于 NestJS/TypeORM、Class-Validator/Class-Transformer 自动映射 DTO 到实体时，未使用 `@Expose`, `@Exclude`, `@IsOptional` 等限制写字段；GraphQL Resolver 将输入 `args` 直接传入 ORM 也会触发批量赋值。  
- NestJS DTO/实体字段暴露控制，详见：[ts_nest_mass_assignment.md](ts_nest_mass_assignment.md)  
- TypeORM `save`/`update` 敏感字段保护指南，详见：[ts_typeorm_mass_assignment.md](ts_typeorm_mass_assignment.md)  
- GraphQL 输入类型白名单示例，详见：[ts_graphql_mass_assignment.md](ts_graphql_mass_assignment.md)

**C/C++**  
常见于 REST 网关、JSON-RPC 服务或自研框架将 JSON/XML 自动映射到 `struct` 时，未过滤额外字段，导致权限或状态字段可被覆盖；嵌入脚本引擎时，对对象属性赋值缺少访问控制也会触发风险。  
- JSON/XML 自动映射中的字段白名单实践，详见：[c_struct_mass_assignment.md](c_struct_mass_assignment.md)  
- 嵌入式配置热更新覆盖敏感字段案例，详见：[c_config_mass_assignment.md](c_config_mass_assignment.md)  
- RPC 结构体批量更新缺乏校验的审计要点，详见：[c_rpc_payload_binding.md](c_rpc_payload_binding.md)

**Rust**  
常见于使用 `serde` 自动反序列化请求到结构体时，未使用 `#[serde(skip_deserializing)]` 或 `deny_unknown_fields`，导致敏感字段被覆盖；`actix-web`, `rocket` 等框架直接将 JSON 转为模型并调用 `diesel`/`sea-orm` 更新也存在风险。  
- Serde 反序列化字段控制实践，详见：[rust_serde_mass_assignment.md](rust_serde_mass_assignment.md)  
- Diesel/SeaORM 批量更新越权场景，详见：[rust_orm_mass_assignment.md](rust_orm_mass_assignment.md)  
- 自定义 Builder/Config 热更新检查清单，详见：[rust_builder_mass_assignment.md](rust_builder_mass_assignment.md)  

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注数据绑定和对象映射相关的实现：**

- 查阅项目文档，重点关注数据模型定义、API 接口设计和权限控制机制
- 理解业务领域和核心功能，识别涉及用户数据修改、权限变更、状态更新的场景
- 识别关键组件、模块及其关系，特别是 Web 控制器、API 层、数据访问层（DAO/ORM）
- 梳理应用流程（重点：请求数据绑定流程、模型映射流程、数据持久化流程）
- 识别关键业务功能（用户注册、信息更新、角色变更、订单修改、多租户管理等）
- 理解所用技术栈和框架（Web 框架如 Spring/Django/Express、ORM 如 Hibernate/SQLAlchemy/TypeORM、序列化库如 Jackson/Pydantic/Class-Transformer 等）
- 查阅配置文件以理解系统行为（模型字段定义、数据绑定配置、序列化器设置、白名单/黑名单规则等）
- 定位数据绑定位置（控制器方法、表单处理、JSON/XML 反序列化、GraphQL Resolver 等）
- 定位模型定义（实体类、DTO、Schema、结构体等，重点关注敏感字段：角色、权限、价格、状态、多租户ID等）
- 定位数据持久化操作（ORM 的 `save`/`update`/`merge`/`create`、批量更新操作等）
- 识别敏感字段保护机制（`@JsonIgnore`/`readonly`/`$guarded`/`#[serde(skip)]` 等注解或配置）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如完全手动赋值、仅处理只读数据、全局启用严格字段白名单且无绕过方式等），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目使用了自动数据绑定、对象映射或 ORM 批量更新机制并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅批量赋值漏洞的参考指南

批量赋值漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用批量赋值漏洞模式（所有项目必审）**

在 **通用批量赋值漏洞模式** 章节中，列举了所有使用自动数据绑定或 ORM 的应用都必须审计的安全问题：
- 自动数据绑定缺乏字段白名单（直接绑定未限制、DTO 未隔离、黑名单代替白名单）
- 敏感字段未设置只读保护（权限角色、状态审核、金额余额、身份所有权、时间戳）
- ORM 批量更新接受未过滤输入（直接使用用户输入、字典/Map 更新、白名单不完整）
- 反序列化未限制可写字段（JSON/XML 反序列化、序列化器未控制）
- 对象合并或属性复制未验证来源（对象合并、反射赋值）
- 配置热更新或参数覆盖缺乏验证（配置更新、环境变量）
- GraphQL 输入类型未限制字段（输入包含敏感字段、直接传入 ORM）
- 多层嵌套对象未递归验证（嵌套对象、关联对象、数组元素）

这些问题与编程语言无关，是自动赋值机制设计层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言数据绑定和 ORM 实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript、TypeScript、C/C++、Rust）
- 列出该语言框架或库的批量赋值典型缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用批量赋值漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `mass_auto_binding_no_whitelist.md`、`java_spring_data_binding.md`、`python_django_mass_assignment.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：用户输入（HTTP 请求体/参数）→ 自动绑定/映射 → 敏感字段被覆盖 → 持久化到数据库 → 安全影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（如字段白名单、只读属性、验证器等）
- 确认被覆盖的字段确实是敏感字段（如权限、角色、状态、价格、余额、多租户ID等）
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-mass-assignment-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板


