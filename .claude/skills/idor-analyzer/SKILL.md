---
name: idor-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证不安全的直接对象引用（IDOR）漏洞；重点关注检测Web应用中通过用户可控参数直接访问资源而缺乏权限校验的问题，包括通过ID、UUID、文件名等标识符访问数据库记录、文件、API接口时未验证当前用户是否拥有该资源的访问权限、未校验资源所有权、未实施基于角色的访问控制、权限校验逻辑缺失或可被绕过、序列化ID可预测或可枚举等，从而导致攻击者通过修改参数值越权访问或操作其他用户的敏感数据、个人资料、订单信息、文件资源等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当项目中存在通过用户可控参数直接或间接访问资源（如文件、数据库记录、API接口等）而缺乏权限校验的逻辑时，需重点审计。此类漏洞常见于用户资料查看、订单查询、文件下载、数据导出等涉及资源标识符（如ID、UUID、文件名）传递的业务模块。

**常见保护机制及绕过技巧**：
- 遇到整数ID/UUID保护 → 详见 [bypassTricks.md - 直接ID遍历](bypassTricks.md#直接id遍历)
- 遇到参数校验保护 → 详见 [bypassTricks.md - 隐藏参数和二级ID](bypassTricks.md#隐藏参数和二级id)
- 遇到编码/哈希保护 → 详见 [bypassTricks.md - 编码和格式变换](bypassTricks.md#编码和格式变换)
- 遇到令牌/会话保护 → 详见 [bypassTricks.md - 令牌预测和重放](bypassTricks.md#令牌预测和重放)
- 遇到批量操作保护 → 详见 [bypassTricks.md - JSON和数据格式差异](bypassTricks.md#json和数据格式差异)

**Early exit**  
若项目完全不涉及基于用户输入的资源访问（例如所有资源访问均为静态、无用户参数传递、或所有数据访问均通过严格的角色/所有权验证中间件强制过滤），则可快速退出对该漏洞类型的审计。

---

## 通用 IDOR 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：直接对象引用缺乏权限校验（数据库/文件/云存储资源访问未验证）、所有权验证缺失或不足（未验证归属关系/仅验证身份/缺乏租户隔离）、资源标识符可预测或可枚举（连续ID/可预测模式/ID泄露，遇到ID序列保护机制详见 [bypassTricks.md - 直接ID遍历](bypassTricks.md#直接id遍历)、UUID保护详见 [bypassTricks.md - UUID/GUID爆破](bypassTricks.md#uuidguid爆破)）、权限校验逻辑缺陷（可被绕过/验证不完整/RBAC不足，遇到参数校验保护详见 [bypassTricks.md - 隐藏参数和二级ID](bypassTricks.md#隐藏参数和二级id)、编码保护详见 [bypassTricks.md - 编码和格式变换](bypassTricks.md#编码和格式变换)）、批量操作缺乏权限校验（批量查询/修改/删除未逐项验证，遇到数组处理保护详见 [bypassTricks.md - JSON数组注入](bypassTricks.md#json数组注入)）、间接对象引用未实施（直接暴露内部ID/未使用临时令牌，遇到令牌保护详见 [bypassTricks.md - 令牌预测和重放](bypassTricks.md#令牌预测和重放)）

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的资源访问实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- 通过路径参数（@PathVariable）或请求参数（@RequestParam）获取ID直接查询数据库，未校验当前用户权限，详见：[java_rest_id_injection.md](java_rest_id_injection.md)  
- 根据用户传入的文件ID或名称直接提供附件下载，缺乏所有权验证，详见：[java_file_download_idor.md](java_file_download_idor.md)  
- 从请求体中提取用户ID直接访问用户资料或敏感数据，未验证访问权限，详见：[java_user_profile_access.md](java_user_profile_access.md)

**Python**
- 在Django视图中通过URL参数或表单字段获取对象ID直接进行ORM查询，未校验用户权限，详见：[python_django_model_access.md](python_django_model_access.md)  
- 使用Flask路由中的参数直接读取文件或资源，缺乏所有权验证，详见：[python_flask_file_retrieval.md](python_flask_file_retrieval.md)  
- API接口通过JSON字段中的ID直接暴露对象数据，未验证当前用户访问权限，详见：[python_api_object_exposure.md](python_api_object_exposure.md)

**Go**
- 从HTTP处理器的URL路径或查询参数中提取ID直接查询数据库，未经权限检查，详见：[go_http_handler_idor.md](go_http_handler_idor.md)  
- 根据用户传入的对象Key直接访问S3或云存储资源，缺乏所有权验证，详见：[go_s3_object_access.md](go_s3_object_access.md)  
- 使用Header或请求参数中的用户ID直接检索用户记录，未验证访问权限，详见：[go_user_record_query.md](go_user_record_query.md)

**PHP**
- 通过$_GET或$_REQUEST获取ID后直接拼接SQL查询语句或用于数据库查询，未校验用户权限，详见：[php_get_id_direct_query.md](php_get_id_direct_query.md)  
- 根据$_GET中的文件名或ID直接进行文件下载或包含操作，缺乏所有权验证，详见：[php_file_download_by_name.md](php_file_download_by_name.md)  
- 后台管理页面使用$_POST中的记录ID直接查看或修改数据，未验证管理员权限范围，详见：[php_admin_record_view.md](php_admin_record_view.md)

**JavaScript / TypeScript（Node.js后端）**
- 从Express路由的req.params或req.query中提取ID直接查询数据库，未验证当前用户访问权限，详见：[nodejs_express_id_param.md](nodejs_express_id_param.md)  
- 使用req.body中的ObjectId直接访问MongoDB文档，缺乏所有权验证，详见：[nodejs_mongodb_id_access.md](nodejs_mongodb_id_access.md)  
- 根据用户传入的Key直接提供S3或云存储下载，未检查当前会话用户权限，详见：[nodejs_s3_download_unchecked.md](nodejs_s3_download_unchecked.md)

**C/C++**
- 通过命令行参数或用户输入直接拼接文件路径进行文件操作，未校验访问权限，详见：[c_insecure_file_access.md](c_insecure_file_access.md)  
- 使用用户提供的配置文件路径或ID直接读取配置资源，缺乏所有权验证，详见：[c_config_idor.md](c_config_idor.md)  
- 根据用户传入的日志ID或名称直接检索日志文件，未验证用户权限，详见：[c_log_retrieval_by_id.md](c_log_retrieval_by_id.md)

**Rust**
- 在Actix-web处理器中从路径或查询参数解析资源ID直接获取数据，缺乏所有权校验，详见：[rust_actix_resource_fetch.md](rust_actix_resource_fetch.md)  
- 使用Rocket路由参数中的文件名或路径直接提供文件服务，未验证用户权限，详见：[rust_rocket_file_serve_idor.md](rust_rocket_file_serve_idor.md)  
- 通过请求参数中的ID直接使用Diesel进行数据库查询，缺乏角色或所有权验证，详见：[rust_diesel_record_access.md](rust_diesel_record_access.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注资源访问与权限控制相关的实现：**

- 查阅项目文档，重点关注资源访问和权限控制机制说明
- 理解业务领域和核心功能，识别涉及用户资源访问的场景
- 识别关键组件、模块及其关系，特别是权限验证模块、访问控制中间件、资源管理层
- 梳理应用流程（重点：资源访问流程、权限校验流程、所有权验证机制）
- 识别关键业务功能（用户资料查看、订单查询、文件下载、数据导出、记录修改等）
- 理解所用技术栈和框架（Web框架、ORM框架、权限控制库，如 Spring Security、Django Permissions、RBAC 中间件等）
- 查阅配置文件以理解系统行为（权限规则配置、ACL配置、角色定义、资源所有权标识等）
- 定位资源访问入口（API端点、路由处理器、控制器方法中的参数接收）
- 定位权限校验位置（所有权验证函数、ACL检查逻辑、角色权限验证实现）
- 识别资源标识符传递方式（URL路径参数、查询参数、请求体字段、Header等）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如所有资源访问均通过严格的权限验证中间件强制过滤、无用户可控的资源标识符、所有数据访问已自动基于当前用户上下文过滤等），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目存在基于用户可控参数的资源访问功能并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 IDOR 漏洞的参考指南

IDOR 漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 IDOR 漏洞模式（所有项目必审）**

在 **通用 IDOR 漏洞模式** 章节中，列举了所有涉及资源访问的 Web 应用都必须审计的 IDOR 问题：
- 直接对象引用缺乏权限校验（数据库、文件、云存储资源访问未验证）
- 所有权验证缺失或不足（未验证归属关系、仅验证身份、缺乏租户隔离）
  - 遇到此类保护机制，参考 [bypassTricks.md - 缺少操作校验](bypassTricks.md#缺少操作校验)
- 资源标识符可预测或可枚举（连续 ID、可预测模式、ID 泄露）
  - 遇到整数ID保护，参考 [bypassTricks.md - 整数ID序列](bypassTricks.md#整数id序列)
  - 遇到UUID保护，参考 [bypassTricks.md - UUID/GUID爆破](bypassTricks.md#uuidguid爆破)
  - 遇到顺序递增模式，参考 [bypassTricks.md - 顺序递增的"随机"ID](bypassTricks.md#顺序递增的随机id)
- 权限校验逻辑缺陷（可被绕过、验证不完整、RBAC 不足）
  - 遇到参数注入绕过，参考 [bypassTricks.md - 额外参数注入](bypassTricks.md#额外参数注入)
  - 遇到编码绕过，参考 [bypassTricks.md - 编码和格式变换](bypassTricks.md#编码和格式变换)
- 批量操作缺乏权限校验（批量查询/修改/删除未逐项验证）
  - 遇到批量操作保护，参考 [bypassTricks.md - JSON数组注入](bypassTricks.md#json数组注入) 和 [重复参数](bypassTricks.md#重复参数)
- 间接对象引用未实施（直接暴露内部 ID、未使用临时令牌）
  - 遇到令牌保护，参考 [bypassTricks.md - 令牌预测和重放](bypassTricks.md#令牌预测和重放)

这些问题与编程语言无关，是资源访问控制设计层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言资源访问实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript/TypeScript、C/C++、Rust）
- 列出该语言框架或 ORM 的 IDOR 典型缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 IDOR 漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `idor_direct_db_query_by_id.md`、`java_rest_id_injection.md`、`python_django_model_access.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

IDOR 漏洞审计采用分层的审计等级制度，根据权限校验机制的完备性来指导审计深度。

| 等级 | 名称 | 时间 | 权限校验特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整验证：所有权校验 + 角色验证 + 资源过滤，无直接对象引用 |
| **L1** | 快速扫描 | 3-5 分钟 | 有验证 + 需确认：需验证所有资源访问点是否都有权限校验 |
| **L2** | 跳读 | 5-10 分钟 | 部分验证：仅身份验证或部分资源有所有权校验，需验证覆盖范围 |
| **L3** | 逐行读 | 15-30 分钟 | 无验证或明显缺陷：直接对象引用、无所有权校验、可预测 ID |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：批量操作、多租户、间接引用、多文件追踪 |

### 快速判断流程

**第 1 步：是否存在资源访问？**
- 无用户可控资源访问 → L0 跳过
- 有资源访问 → 继续第 2 步

**第 2 步：是否有权限校验？**
- 无权限校验或仅身份验证 → **L3+**
- 有所有权校验 → 继续第 3 步

**第 3 步：权限校验是否完整？**
- 所有资源访问都有所有权校验 → **L0-L1**
- 部分资源有校验 → **L2**
- 批量操作或多租户场景 → **L3-L4**

### 各等级操作指南

**L0**：完整验证
```java
// 所有权校验
Order order = orderRepository.findById(orderId);
if (order.getUserId() != currentUser.getId()) {
    throw new ForbiddenException();
}

// ORM 自动过滤
@Where(clause = "user_id = :currentUserId")
List<Order> orders = orderRepository.findAll();

// 间接对象引用
String token = generateTemporaryToken(fileId);
return token;  // 不暴露实际 ID
```

**L1**：有验证 + 需确认
- 所有资源访问端点是否都有所有权校验？
- 是否使用了权限验证中间件或装饰器？
- 批量操作是否逐项验证？（遇到批量操作场景详见 [bypassTricks.md - JSON数组注入](bypassTricks.md#json数组注入)）
- 是否实施了基于角色的访问控制（RBAC）？（遇到权限绕过详见 [bypassTricks.md - 额外参数注入](bypassTricks.md#额外参数注入)）

**L2**：部分验证
- 哪些资源有所有权校验？哪些没有？
- 是否仅验证了身份但未验证所有权？（遇到此类保护详见 [bypassTricks.md - 缺少操作校验](bypassTricks.md#缺少操作校验)）
- 多租户环境是否有租户隔离？（遇到多租户绕过详见 [bypassTricks.md - 嵌套资源ID](bypassTricks.md#嵌套资源id)）
- 资源 ID 是否可预测或可枚举？（遇到ID预测详见 [bypassTricks.md - 直接ID遍历](bypassTricks.md#直接id遍历)）

**L3**：无验证或明显缺陷
```java
// 直接对象引用，无所有权校验（利用技巧详见 bypassTricks.md - 直接ID遍历）
@GetMapping("/api/order/{id}")
public Order getOrder(@PathVariable Long id) {
    return orderRepository.findById(id).orElse(null);  // 存在 IDOR 风险
}

// 仅验证身份，未验证所有权（绕过方法详见 bypassTricks.md - 缺少操作校验）
if (user != null) {  // 只要已登录就能访问
    return fileService.getFile(fileId);  // 存在 IDOR 风险
}

// 连续 ID 可枚举（枚举技巧详见 bypassTricks.md - 整数ID序列）
/api/user/1, /api/user/2, /api/user/3...
```
完整分析资源访问和权限校验流程，追踪数据流，确认越权点（常见绕过技巧详见 [bypassTricks.md](bypassTricks.md)）

**L4**：复杂链路
- 批量操作：是否逐项验证所有权？（遇到批量操作绕过详见 [bypassTricks.md - JSON数组注入](bypassTricks.md#json数组注入)、[多个ID参数](bypassTricks.md#多个id参数)）
- 多租户场景：租户 ID 校验是否完整？（遇到租户隔离绕过详见 [bypassTricks.md - 嵌套资源ID](bypassTricks.md#嵌套资源id)）
- 间接对象引用：是否使用临时令牌或映射？（遇到令牌绕过详见 [bypassTricks.md - 令牌预测和重放](bypassTricks.md#令牌预测和重放)）
- 多文件追踪：用户输入 → 资源定位 → 权限校验 → 资源返回（遇到路径遍历结合IDOR详见 [bypassTricks.md - 通过关联获取其他数据](bypassTricks.md#通过关联获取其他数据)）
- 云存储访问：S3/OSS 预签名 URL 是否限制访问？（遇到导出功能IDOR详见 [bypassTricks.md - 导出功能中的IDOR](bypassTricks.md#导出功能中的idor)）

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 完整所有权校验 + RBAC | L0 | 无风险 |
| 有验证 + 需确认覆盖范围 | L1 | 验证所有端点 |
| 部分验证或仅身份验证 | L2 | 验证所有权 |
| 无所有权校验 | L3 | 高风险 |
| 直接对象引用 + 可预测 ID | L3 | 高风险 |
| 批量操作或多租户 | L4 | 完整追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（用户可控的资源标识符）→ 资源访问逻辑 → 权限校验缺失/不足 → 越权影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（如 ORM 过滤器、权限装饰器、中间件拦截等）
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)
  - 遇到整数ID保护：详见 [直接ID遍历](bypassTricks.md#直接id遍历)
  - 遇到UUID/GUID保护：详见 [UUID/GUID爆破](bypassTricks.md#uuidguid爆破)
  - 遇到参数校验保护：详见 [隐藏参数和二级ID](bypassTricks.md#隐藏参数和二级id)
  - 遇到编码/哈希保护：详见 [编码和格式变换](bypassTricks.md#编码和格式变换)
  - 遇到JSON处理保护：详见 [JSON和数据格式差异](bypassTricks.md#json和数据格式差异)
  - 遇到令牌/会话保护：详见 [令牌预测和重放](bypassTricks.md#令牌预测和重放)
  - 遇到嵌套资源保护：详见 [通过关联获取其他数据](bypassTricks.md#通过关联获取其他数据)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-idor-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
