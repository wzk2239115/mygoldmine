---
name: insecure-file-uploads-analyzer
description: 专业的审计工作流程，通过静态与动态分析识别并验证不安全文件上传风险；聚焦文件上传、转换、分发链路中缺乏类型校验、路径管控、访问限制的场景，结合按编程语言组织的参考指南定位高危点。
---

**Attention**  
当应用允许用户上传文件（图片、文档、压缩包、脚本等）而缺乏严格的类型验证、扩展名与 MIME 校验、内容审查、存储路径隔离、执行权限限制或访问控制时，攻击者可上传恶意脚本获取代码执行、覆盖配置文件、触发反序列化漏洞、滥用存储资源或窃取敏感信息。需重点审计上传入口、后端处理链路（解压、压缩、转换、预览、异步任务）、CDN/静态资源分发策略以及权限与鉴权是否到位。

**Early exit**

**在开始审计之前，必须首先运行文件上传扫描脚本完成初步检索**，快速定位项目中可能存在的文件上传功能及其处理逻辑。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行文件上传扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

若项目完全不提供文件上传/导入功能、所有上传操作由可信离线渠道完成并经人工审核、或上传链路全程委托给安全第三方服务且确认不存在自定义处理逻辑，则可快速结束对该漏洞类型的审计。

---

## 通用文件上传漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：文件类型验证缺失或不足（仅客户端验证、仅扩展名、仅 MIME、内容验证不完整）、文件扩展名绕过技巧（大小写、特殊字符、双扩展名）、文件名处理不当导致安全风险（目录穿越、未清理、可预测）、文件存储位置不安全（Web 可访问目录、未隔离、云存储配置不当）、文件访问控制缺失（直接访问无需鉴权、访问令牌不安全）、文件大小和数量限制缺失（无大小限制、无频率限制、无配额）、文件处理过程不安全（解压缩、图片/文档处理、格式转换）、文件内容安全扫描缺失（无病毒扫描、无恶意内容检测）

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的文件上传实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
常见于 Spring MVC、Servlet、Struts 等框架使用 `MultipartFile`、`Commons FileUpload` 处理上传时，仅依赖扩展名或客户端 MIME，未验证内容；文件直接写入 Web 根目录或通过模板渲染执行。  
- Spring MultipartFile 上传安全控制，详见：[java_spring_upload_safety.md](java_spring_upload_safety.md)  
- Java 图片/文档转换链路风险分析，详见：[java_media_processing_upload.md](java_media_processing_upload.md)  
- 文件储存与访问控制最佳实践，详见：[java_storage_access_control.md](java_storage_access_control.md)

**Python**  
常见于 Django、Flask、FastAPI 等使用 `request.files`、`FileField` 上传时，缺少扩展名白名单、MIME 检测、内容扫描或隔离目录；Celery 等异步任务处理上传文件时也易暴露风险。  
- Django/Flask 上传白名单与存储隔离，详见：[python_web_upload_controls.md](python_web_upload_controls.md)  
- Python 文档/图像处理链路安全审计，详见：[python_processing_upload.md](python_processing_upload.md)  
- 临时文件与云存储访问策略，详见：[python_storage_permissions.md](python_storage_permissions.md)

**Go**  
常见于 `http.Request.FormFile`、`gin.Context.SaveUploadedFile` 等处理上传时未限制文件大小、扩展名或未隔离存储；上传后直接交给图像/文档库处理可能触发解析漏洞。  
- Go 上传大小与类型限制指南，详见：[go_upload_validation.md](go_upload_validation.md)  
- Go 文件落盘与访问控制实践，详见：[go_upload_storage_control.md](go_upload_storage_control.md)  
- 异步任务/微服务链路的文件安全，详见：[go_async_upload_pipeline.md](go_async_upload_pipeline.md)

**PHP**  
常见于 `$_FILES`、Laravel `Storage::putFile`、Symfony 上传组件中，只检查扩展名而未验证 MIME/内容；上传目录位于 Web 根路径或支持解析脚本，导致木马上传；上传后处理（图像库、压缩）缺少安全措施。  
- PHP 上传白名单与 MIME 校验，详见：[php_upload_validation.md](php_upload_validation.md)  
- Laravel/Symfony 上传存储设计，详见：[php_framework_upload_storage.md](php_framework_upload_storage.md)  
- 上传后处理与执行权限隔离，详见：[php_post_upload_processing.md](php_post_upload_processing.md)
- 大小写绕过漏洞，详见：[php_case_sensitive_bypass.md](php_case_sensitive_bypass.md)
- Windows文件流绕过(::$DATA)，详见：[php_windows_stream_bypass.md](php_windows_stream_bypass.md)
- 特殊字符绕过（空格/点号/组合），详见：[php_special_chars_bypass.md](php_special_chars_bypass.md)
- 文件头检测绕过，详见：[php_file_header_bypass.md](php_file_header_bypass.md)
- exif_imagetype()绕过，详见：[php_exif_image_bypass.md](php_exif_image_bypass.md)
- 二次渲染绕过，详见：[php_image_re_rendering_bypass.md](php_image_re_rendering_bypass.md)
- 双写绕过漏洞，详见：[php_double_extension_bypass.md](php_double_extension_bypass.md)

**JavaScript (Node.js)**  
常见于 Express/Koa/Nest 搭配 `multer`、`busboy`、`formidable` 等中间件时，仅根据文件名判断类型，或将文件直接保存至可访问目录；上传后调用图像处理库、PDF 渲染时也存在 RCE/DoS 风险。  
- Node.js 上传中间件安全配置，详见：[js_upload_middleware_security.md](js_upload_middleware_security.md)  
- 静态资源服务与访问控制策略，详见：[js_static_storage_control.md](js_static_storage_control.md)  
- 上传文件内容检测与安全扫描，详见：[js_upload_content_security.md](js_upload_content_security.md)

**TypeScript**  
常见于 NestJS/Next.js/Serverless 等 TypeScript 项目，使用 `@UploadedFile`、`multer` 适配器时缺乏扩展名/MIME 校验，或通过 `S3`/`GCS` 上传但未设置临时访问令牌、回调验证；GraphQL 上传也需注意。  
- NestJS 上传管道与验证实现，详见：[ts_nest_upload_validation.md](ts_nest_upload_validation.md)  
- TypeScript 项目云存储安全设计，详见：[ts_cloud_storage_upload.md](ts_cloud_storage_upload.md)  
- SSR/BFF 上传链路安全加固，详见：[ts_ssr_upload_protection.md](ts_ssr_upload_protection.md)

**C/C++**  
常见于网关、后端服务或桌面客户端使用 `fopen`/`write` 接收文件时未校验类型、未限制路径，或在解压/解析阶段缺乏边界检查，导致任意文件写入、目录穿越或命令执行。  
- 文件类型与路径校验实践，详见：[c_upload_validation.md](c_upload_validation.md)  
- 解压/转换流程的安全防护，详见：[c_archive_upload.md](c_archive_upload.md)  
- 附件扫描与隔离机制构建，详见：[c_sandbox_upload.md](c_sandbox_upload.md)

**Rust**  
常见于 Actix/Rocket/Axum 等框架处理 multipart 上传时，仅凭文件名写入磁盘或临时目录；使用 `image`, `pdf` 等 crate 解析上传文件时缺乏限流、隔离；或将文件交给外部程序处理导致 RCE。  
- Rust Web 上传验证与路径隔离，详见：[rust_upload_validation.md](rust_upload_validation.md)  
- Rust 文件解析与沙箱执行策略，详见：[rust_processing_upload.md](rust_processing_upload.md)  
- 云存储/对象存储访问控制，详见：[rust_storage_access.md](rust_storage_access.md)  

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注文件上传相关的实现：**

- 查阅项目文档，重点关注文件上传、导入、附件处理功能说明
- 理解业务领域和核心功能，识别涉及文件上传的场景（头像上传、文档导入、附件管理、批量导入等）
- 识别关键组件、模块及其关系，特别是上传接口、文件处理服务、存储服务、CDN/静态资源服务
- 梳理文件上传流程（重点：上传接口、验证逻辑、存储位置、后处理流程、访问方式）
- 识别关键业务功能（文件上传、文件预览、文件下载、文件转换、图片/文档处理等）
- 理解所用技术栈和框架（Web框架、上传中间件类型和版本，如 multer、Commons FileUpload、busboy、multipart 等）
- 查阅配置文件以理解系统行为（文件大小限制、允许类型、存储路径、访问权限、处理策略等）
- 定位文件上传入口位置（上传接口、路由、控制器、处理函数）
- 定位文件验证逻辑位置（类型校验、扩展名检查、MIME 验证、内容检测）
- 定位文件存储位置（本地存储路径、云存储配置、数据库存储、临时目录）
- 定位文件访问方式（直接访问URL、下载接口、预览接口、静态资源服务）
- 识别文件后处理逻辑（图片压缩、文档转换、解压缩、病毒扫描、异步任务等）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如完全不提供文件上传功能、所有上传操作由可信离线渠道完成并经人工审核、或上传链路全程委托给安全第三方服务且确认不存在自定义处理逻辑），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目存在文件上传功能并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅不安全文件上传漏洞的参考指南

文件上传漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用文件上传漏洞模式（所有项目必审）**

在 **通用文件上传漏洞模式** 章节中，列举了所有提供文件上传功能的应用都必须审计的安全问题：
- 文件类型验证缺失或不足（仅客户端验证、仅扩展名、仅 MIME、内容验证不完整）
- 文件扩展名绕过技巧（大小写、特殊字符、双扩展名）
- 文件名处理不当导致安全风险（目录穿越、未清理、可预测）
- 文件存储位置不安全（Web 可访问目录、未隔离、云存储配置不当）
- 文件访问控制缺失（直接访问无需鉴权、访问令牌不安全）
- 文件大小和数量限制缺失（无大小限制、无频率限制、无配额）
- 文件处理过程不安全（解压缩、图片/文档处理、格式转换）
- 文件内容安全扫描缺失（无病毒扫描、无恶意内容检测）

这些问题与编程语言无关，是文件上传安全设计层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言文件上传实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript、TypeScript、C/C++、Rust）
- 列出该语言框架或库的文件上传典型缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用文件上传漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `upload_extension_only_check.md`、`java_spring_upload_safety.md`、`python_web_upload_controls.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（文件上传）→ 验证逻辑 → 存储位置 → 访问方式 → 危险操作 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-insecure-uploads-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

