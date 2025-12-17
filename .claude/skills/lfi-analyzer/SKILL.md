---
name: lfi-analyzer
description: 专业的审计工作流程，通过静态与动态分析识别并验证本地文件包含（LFI）风险；聚焦动态文件包含和资源加载的链路，结合各语言参考指南定位高危点。
---

**Attention**
当项目使用动态文件包含（`include/require`、模板加载、插件加载、配置读取等）接收用户可控的文件路径参数时，若缺乏白名单校验，攻击者可通过 `../` 相对路径或绝对路径包含系统敏感文件、日志、配置等，甚至结合日志注入实现远程代码执行。审计时需重点追踪所有文件包含点、路径验证逻辑、日志注入点。

**Early exit**
若项目不使用动态文件包含、所有包含路径硬编码且不受用户输入影响、模板/配置加载仅支持白名单内的资源、或系统禁用了危险协议（`php://`、`data://`），则可快速结束对该漏洞类型的审计。

---

## 通用 LFI 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：动态文件包含未限制（include/require 接受用户输入）、包含敏感文件（/etc/passwd、配置文件、密钥）、日志注入 + 包含 RCE（日志可写入代码并动态包含）、模板引擎动态加载、插件/配置路径可控、路径构建缺陷（字符串拼接、规范化不完整、无白名单）、符号链接绕过、远程文件包含 (RFI)、跨平台绕过（路径分隔符、大小写敏感性）

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的文件系统操作实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- JSP/Velocity/FreeMarker 模板引擎的动态 include 允许用户控制模板路径，演化为 LFI，详见：[java_template_inclusion.md](java_template_inclusion.md)

**PHP**
- 使用 `include`/`require`/`include_once`/`require_once` 直接拼接用户控制的文件名，缺乏路径过滤，详见：[php_file_include_traversal.md](php_file_include_traversal.md)

**JavaScript / TypeScript（Node.js后端）**
- 模板引擎加载器允许用户控制模板路径，通过相对路径包含任意文件，详见：[nodejs_template_loader_lfi.md](nodejs_template_loader_lfi.md)
- SSR/CLI 工具使用 `require` 或 `import()` 动态加载用户输入的相对路径，形成本地文件包含，详见：[nodejs_dynamic_require_lfi.md](nodejs_dynamic_require_lfi.md)

**Rust**
- 插件系统通过 `DynamicLibrary` 加载用户指定的外部资源，未校验根目录限制，详见：[rust_plugin_dynamic_load.md](rust_plugin_dynamic_load.md)
- 使用 `include_str!` 或配置加载器读取用户可控路径的配置文件，缺乏符号链接检测，详见：[rust_config_path_inclusion.md](rust_config_path_inclusion.md)

**Python**
- 使用 `open()` 或 `pathlib.Path()` 直接拼接用户输入的文件路径，缺乏路径验证，详见：[python_open_path_traversal.md](python_open_path_traversal.md)
- 动态导入：`__import__()` 或 `importlib.import_module()` 动态加载用户可控模块，详见：[python_dynamic_import_lfi.md](python_dynamic_import_lfi.md)
- Jinja2/Mako 模板引擎允许用户控制模板路径，动态加载任意模板文件，详见：[python_template_path_lfi.md](python_template_path_lfi.md)
- 使用 `exec()` 或 `eval()` 执行从文件读取的用户可控代码，详见：[python_exec_file_content_lfi.md](python_exec_file_content_lfi.md)

**Go**
- 使用 `os.Open()` 或 `ioutil.ReadFile()` 的文件路径直接拼接用户输入，缺乏路径校验，详见：[go_os_open_path_traversal.md](go_os_open_path_traversal.md)
- 动态插件加载：`plugin.Open()` 加载用户指定路径的插件库，未校验插件来源，详见：[go_plugin_open_lfi.md](go_plugin_open_lfi.md)
- 模板引擎（text/template、html/template）动态加载用户指定的模板文件，详见：[go_template_file_lfi.md](go_template_file_lfi.md)

**C/C++**
- 使用 `fopen()`、`open()` 等函数直接拼接用户输入的文件路径，缺乏路径过滤，详见：[c_fopen_path_traversal.md](c_fopen_path_traversal.md)
- 动态库加载：`dlopen()` 加载用户可控路径的动态库，未验证库来源，详见：[c_dlopen_path_injection.md](c_dlopen_path_injection.md)
- 配置文件加载通过用户输入的相对路径，允许目录遍历，详见：[c_config_file_traversal.md](c_config_file_traversal.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注动态文件包含相关的实现：**

- 查阅项目文档，重点关注模板加载、配置读取、插件加载的说明
- 理解业务领域和核心功能，识别涉及模板渲染、动态配置、插件系统的场景
- 识别关键组件、模块及其关系，特别是模板引擎、插件加载器、配置管理模块
- 梳理应用流程（重点：模板渲染流程、配置加载流程、插件加载流程）
- 识别关键业务功能（模板渲染、动态加载、配置管理等）
- 理解所用技术栈和框架（模板引擎类型、插件架构等）
- 查阅配置文件以理解系统行为
- 定位所有 include/require/import 的位置
- 识别用户输入如何影响文件路径（URL参数、请求体、配置参数等）

### 步骤 1：查阅 LFI 漏洞的参考指南

在 **通用 LFI 漏洞模式** 章节中，列举了所有涉及动态文件包含的应用都必须审计的安全问题：
- 动态文件包含未限制（include/require 接受用户输入）
- 包含敏感文件（/etc/passwd、配置文件、密钥）
- 日志注入 + 包含 RCE（日志可写入代码并动态包含）
- 模板引擎动态加载
- 插件/配置路径可控

**语言特定实现：**

在 **语言特定实现** 章节中，按编程语言组织了各语言动态包含实现方式的特定问题。根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 LFI 漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

LFI 漏洞审计采用分层的审计等级制度，根据动态文件包含的使用方式来指导审计深度。

| 等级 | 名称 | 时间 | 包含特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 无动态包含：无 include/require/fopen 等，所有文件路径硬编码，或禁用危险协议 |
| **L1** | 快速扫描 | 3-5 分钟 | 有动态包含 + 白名单验证：需确认白名单完整性和白名单绕过可能性 |
| **L2** | 跳读 | 5-10 分钟 | 动态包含 + 路径过滤：需验证过滤规则完整性和黑名单绕过技巧 |
| **L3** | 逐行读 | 15-30 分钟 | 直接包含用户输入：无防护、黑名单不完整、过滤可绕过 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：日志注入+包含RCE、模板动态加载、符号链接、多文件追踪 |

### 快速判断流程

**第 1 步：是否存在动态文件包含？**
- 无包含操作（include/require/fopen/file_get_contents）或全部硬编码 → **L0 跳过**
- 有动态包含 → 继续第 2 步

**第 2 步：包含的文件路径是否可控？**
- 完全不受用户输入影响，仅框架/配置控制 → **L0**
- 用户输入影响路径参数 → 继续第 3 步

**第 3 步：是否有防护措施？**
- 完整的白名单验证（已知安全文件列表） → **L1**
- 路径过滤或规范化处理 → **L2**
- 无防护或防护可绕过 → **L3+**
- 日志注入、模板动态加载、符号链接、插件系统 → **L4**
- 支持流协议（php://、data://、file://）且可控 → **L3+**

### 各等级操作指南

**L0**：完全无动态包含

```php
// PHP - 硬编码包含路径
include '/path/to/header.php';
require TEMPLATE_DIR . 'fixed_name.html';

// 白名单完全验证
$allowed = ['header', 'footer', 'sidebar'];
if (in_array($template, $allowed, true)) {
    include 'templates/' . $template . '.php';
}
```

**L1**：有白名单保护

- 确认白名单是否为硬编码或受控数据库
- 验证白名单匹配是否使用了严格比较（=== 或 in_array(..., true)）
- 检查白名单是否覆盖所有包含点
- 验证是否禁用了流协议（php://、data://、file://）
- 遇到以下白名单保护机制时，参考 [bypassTricks.md](bypassTricks.md) 的相应章节：
  - **白名单目录限制** → 详见 [路径遍历绕过白名单](bypassTricks.md#1-路径遍历绕过白名单)
  - **白名单扩展名检查** → 详见 [白名单扩展名绕过](bypassTricks.md#4-白名单扩展名绕过空字节双扩展名)
  - **realpath() 验证** → 详见 [白名单目录绕过（realpath前后）](bypassTricks.md#5-白名单目录绕过realpath前后)
  - **basename() 验证** → 详见 [basename绕过](bypassTricks.md#6-basename绕过)
  - **符号链接** → 详见 [符号链接绕过](bypassTricks.md#2-符号链接绕过)

**L2**：有路径过滤但需验证

- 定位过滤逻辑：黑名单还是白名单？
- 核实过滤规则是否覆盖所有绕过技巧
- 遇到以下保护机制时，参考 [bypassTricks.md](bypassTricks.md) 的相应章节：
  - **协议黑名单**（禁用 php://、file:// 等） → 详见 [协议黑名单绕过](bypassTricks.md#1-协议黑名单绕过)
  - **路径遍历过滤**（禁用 ../、..\ 等） → 详见 [关键字过滤绕过](bypassTricks.md#2-关键字过滤绕过)
  - **点号过滤**（禁用 . 字符） → 详见 [点号过滤绕过](bypassTricks.md#3-点号过滤绕过)
  - **斜杠过滤**（禁用 / 或 \ 字符） → 详见 [斜杠过滤绕过](bypassTricks.md#4-斜杠过滤绕过)
  - **正则表达式过滤** → 详见 [Regex绕过](bypassTricks.md#regex绕过正则表达式缺陷)
  - **特定路径黑名单**（如禁止 /etc/passwd） → 详见 [路径黑名单绕过](bypassTricks.md#6-路径黑名单绕过)
  - **多层编码**（URL编码、Unicode编码） → 详见 [多层编码绕过](bypassTricks.md#多层编码绕过)
- 验证路径规范化（realpath）是否已使用
- 检查符号链接是否被验证

**L3**：直接包含用户输入

```php
// 高风险示例 - 直接包含
include $_GET['page'];  // 严重漏洞
include 'pages/' . $_GET['page'];  // 路径遍历

// 高风险示例 - 模板动态加载
$template = $_POST['template'];
include 'templates/' . $template;  // 无任何防护

// 高风险示例 - 配置路径可控
$config = $_GET['config_file'];
include_once $config;  // RFI 风险
```

完整分析包含路径构造和执行流程，追踪数据流，确认注入点

**利用技巧参考**：
- **PHP伪协议利用** → 详见 [bypassTricks.md - PHP伪协议利用](bypassTricks.md#php-伪协议利用)
- **目录遍历编码** → 详见 [bypassTricks.md - 目录遍历编码](bypassTricks.md#目录遍历编码)
- **文件包含技术** → 详见 [bypassTricks.md - 文件包含技术](bypassTricks.md#文件包含技术)

**L4**：复杂链路

- **日志注入 + 包含 RCE**：用户输入写入日志，日志文件被动态包含并执行
  - 详见 [日志文件包含](bypassTricks.md#日志文件包含)
  - 详见 [日志注入 + 包含](bypassTricks.md#日志注入--包含)
- **Session文件包含**：通过Session机制写入恶意代码，再包含Session文件
  - 详见 [Session文件包含](bypassTricks.md#session文件包含)
  - 详见 [Session包含 + 上传](bypassTricks.md#session包含--上传)
- **模板动态加载**：模板引擎根据用户输入加载模板，模板内容可控
  - 详见 [模板引擎 LFI](bypassTricks.md#模板引擎-lfi)
- **临时文件竞争**：在临时文件被删除前包含执行
  - 详见 [临时文件包含](bypassTricks.md#临时文件包含)
- **符号链接攻击**：通过符号链接指向系统文件，绕过路径检查
  - 详见 [符号链接绕过](bypassTricks.md#2-符号链接绕过)
- **插件系统**：用户可控的插件路径或插件内容
- **多步骤追踪**：用户输入 → 数据处理 → 路径构造 → 包含执行
- **环境变量包含**：通过环境变量注入恶意代码
  - 详见 [环境变量/控制符号包含](bypassTricks.md#环境变量控制符号包含)
- **邮件/数据库日志包含**：通过邮件或数据库日志写入恶意代码
  - 详见 [邮件文件包含](bypassTricks.md#邮件文件包含)
  - 详见 [数据库文件包含](bypassTricks.md#数据库文件包含)
- **上传文件包含**：上传包含恶意代码的文件（图片、文档等）
  - 详见 [上传文件包含](bypassTricks.md#上传文件包含)
- **死亡代码绕过**：绕过 `<?php die('...'); ?>` 保护
  - 详见 [php://filter 写入绕过死亡代码](bypassTricks.md#phpfilter-写入绕过死亡代码)

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 所有文件路径硬编码 | L0 | 无风险 |
| 完整的白名单验证 | L1 | 验证白名单完整性 |
| 路径过滤或规范化 | L2 | 验证过滤规则，考虑绕过技巧 |
| 直接包含用户输入 | L3 | 高风险，立即修复 |
| 日志注入 + 包含 | L4 | 完整追踪，两个漏洞的组合 |
| 模板动态加载 | L4 | 完整追踪，验证模板来源 |
| 支持 RFI（php:// 等协议） | L3+ | 远程代码执行风险，更高风险 |
| 符号链接未验证 | L3+ | 能否逃逸目录限制 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信输入）→ 路径参数 → 动态包含 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（白名单校验、路径检查等）
- **绕过技巧**：审计过程中遇到各种保护机制时，参考 [bypassTricks.md](bypassTricks.md) 获取详细的绕过方法
  - 快速查找表：[遇到保护机制时的绕过索引](bypassTricks.md#快速查找遇到保护机制时的绕过索引)
  - 白名单绕过：[白名单绕过技巧](bypassTricks.md#白名单绕过技巧)
  - 黑名单绕过：[黑名单绕过技巧](bypassTricks.md#黑名单绕过技巧)
  - 协议利用：[PHP伪协议利用](bypassTricks.md#php-伪协议利用)
  - 文件包含：[文件包含技术](bypassTricks.md#文件包含技术)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-lfi-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
