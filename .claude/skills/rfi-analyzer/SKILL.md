---
name: rfi-analyzer
description: 专业的审计工作流程，通过静态与动态分析识别并验证远程文件包含（RFI）风险；聚焦远程 URL 加载和资源获取的链路，结合各语言参考指南定位高危点。
---

**Attention**
当项目允许从用户可控的 URL 加载和执行远程文件（如 PHP 的 `allow_url_include`、`urllib.request` 等），或允许拉取远程模板、脚本、配置等资源时，攻击者可指向恶意服务器执行远程代码或注入恶意内容，导致远程代码执行（RCE）。审计时需重点追踪所有远程资源加载点、URL 验证逻辑、协议限制。

**Early exit**
若项目未使用任何远程文件包含或加载功能、所有资源访问都限制为本地或白名单 URL、或系统禁用了危险协议（`http://`、`ftp://`）的包含，则可快速结束对该漏洞类型的审计。

---

## 通用 RFI 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：允许远程 URL 包含（PHP `allow_url_include` 启用、`include/require` 支持远程协议）、用户可控 URL（参数指定远程 URL、Webhook 回调、API 调用）、远程资源验证缺失、URL 来源未检验、协议限制缺失（http://、ftp://、file:// 可用）、包装器协议结合（php://、data://）、环境变量污染、DNS 重绑定和 HTTP 重定向绕过

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的文件系统操作实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- JSP/Velocity/FreeMarker 模板引擎的动态模板加载允许用户控制远程模板 URL，未校验来源和协议限制，演化为 RFI，详见：[java_template_remote_inclusion.md](java_template_remote_inclusion.md)

**Go**
- 拉取远程模板后写入临时目录并执行，未校验 URL 来源和目标路径，触发 RFI，详见：[go_template_remote_fetch.md](go_template_remote_fetch.md)

**PHP**
- 当 `allow_url_include`/`allow_url_fopen` 启用时，用户可通过远程 URL 包含导致 RFI 执行恶意代码，详见：[php_remote_url_inclusion.md](php_remote_url_inclusion.md)
- PHP 协议包装器（`php://input`、`php://filter` 等）与远程包含结合的 RFI 风险，详见：[php_protocol_wrappers_rfi.md](php_protocol_wrappers_rfi.md)

**Python**
- 允许 `urllib.request`/`requests` 拉取用户提供的远程 URL 并写入临时目录，引入 RFI 风险，详见：[python_remote_file_inclusion.md](python_remote_file_inclusion.md)

**JavaScript / TypeScript（Node.js后端）**
- `require()` 或动态 `import()` 加载用户可控的远程脚本 URL，未验证来源和协议限制，详见：[nodejs_remote_require_rfi.md](nodejs_remote_require_rfi.md)
- 模板引擎（EJS、Handlebars、Pug 等）允许用户控制远程模板 URL，动态加载并执行，详见：[nodejs_template_remote_rfi.md](nodejs_template_remote_rfi.md)

**Rust**
- 插件系统通过 `reqwest`/`hyper` 等 HTTP 客户端加载用户指定的远程插件库，未校验来源和完整性，详见：[rust_plugin_remote_load.md](rust_plugin_remote_load.md)
- 配置加载器允许从用户可控的远程 URL 拉取配置文件，缺乏协议和来源限制，详见：[rust_config_remote_load.md](rust_config_remote_load.md)

**C/C++**
- 使用 `curl`/`libcurl` 等库加载用户指定的远程库文件，通过 `dlopen()` 执行，未验证来源，详见：[c_dlopen_remote_library.md](c_dlopen_remote_library.md)
- 配置或脚本文件通过 `curl` 从用户可控的远程 URL 拉取并执行，缺乏白名单和协议限制，详见：[c_curl_remote_execution.md](c_curl_remote_execution.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注远程资源加载相关的实现：**

- 查阅项目文档，重点关注远程资源加载、Webhook、API 调用的说明
- 理解业务领域和核心功能，识别涉及远程模板加载、远程配置获取、远程脚本执行等的场景
- 识别关键组件、模块及其关系，特别是远程资源加载模块
- 梳理应用流程（重点：远程资源加载流程、Webhook 处理流程、API 调用流程）
- 识别关键业务功能（远程模板加载、远程配置获取、Webhook 回调、第三方 API 调用等）
- 理解所用技术栈和框架（HTTP 客户端库、模板加载方式等）
- 查阅配置文件以理解系统行为（是否启用远程协议、白名单配置等）
- 定位所有远程资源加载点（`urllib`、`requests`、`include`、`require` 等）
- 识别用户输入如何影响 URL 参数（URL 参数、请求体、配置参数等）

### 步骤 1：查阅 RFI 漏洞的参考指南

在 **通用 RFI 漏洞模式** 章节中，列举了所有涉及远程资源加载的应用都必须审计的安全问题：
- 允许远程 URL 包含（PHP `allow_url_include` 启用、`include/require` 支持远程协议）
- 用户可控 URL（参数指定远程 URL、Webhook 回调、API 调用）
- 远程资源验证缺失
- URL 来源未检验

这些问题与编程语言无关，是远程资源加载安全设计层面的通用缺陷。

**语言特定实现：**

在 **语言特定实现** 章节中，按编程语言组织了各语言远程资源加载实现方式的特定问题。根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 RFI 漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

RFI 漏洞审计采用分层的审计等级制度，根据远程资源加载的方式来指导审计深度。

| 等级 | 名称 | 时间 | 远程加载特征 |
|------|------|------|------------|
| **L0** | 快速跳过 | 1-2 分钟 | 无远程资源加载：无远程 URL 拉取、所有资源路径硬编码、或禁用危险协议 |
| **L1** | 快速扫描 | 3-5 分钟 | 有远程加载 + 完整白名单验证：需确认白名单完整性和绕过可能性 |
| **L2** | 跳读 | 5-10 分钟 | 有远程加载 + URL 来源验证：验证协议限制和来源校验的有效性 |
| **L3** | 逐行读 | 15-30 分钟 | 直接加载用户可控 URL：无防护、协议限制不完整、来源检验缺失 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：包装器协议结合、环境变量污染、Webhook 回调链、多文件追踪 |

### 快速判断流程

**第 1 步：是否存在远程资源加载？**
- 无远程资源加载逻辑（无 urllib、requests、include、require 等远程加载 API）→ **L0 跳过**
- 有远程资源加载或支持远程协议 → 继续第 2 步

**第 2 步：远程 URL 是否可控？**
- 完全不受用户输入影响，仅框架/配置控制 → **L0**
- 用户通过参数、配置、请求体影响 URL → 继续第 3 步

**第 3 步：是否有防护措施？**
- 完整的 URL 白名单验证（已知安全的完整 URL 列表） → **L1**
- URL 来源检验 + 协议限制（仅允许 https://、内部域名） → **L2**
- 无防护或防护可绕过（无协议限制、无来源检验、黑名单不完整），绕过技巧详见：[bypassTricks.md](bypassTricks.md) → **L3+**
- 包装器协议结合、环境变量注入、Webhook 回调链、符号链接、插件系统 → **L4**
- 支持流协议（php://、data://、file://）且可控，详见：[bypassTricks.md - PHP 远程协议利用](bypassTricks.md#php-远程协议利用) → **L3+**

### 各等级操作指南

**L0**：完全无远程资源加载

```php
// PHP 示例 - 硬编码 URL
$apiUrl = 'https://internal-api.company.com/data'; // 硬编码
$content = file_get_contents($apiUrl);

// Node.js 示例 - 环境变量受控且配置严格
const config = require('./config.json');
const trustedUrls = config.apis; // 从配置文件读取，不受用户控制
fetch(trustedUrls.data);

// Python 示例 - 白名单硬编码
TRUSTED_URLS = {
    'user_service': 'https://api.company.com/users',
    'product_service': 'https://api.company.com/products'
}
url = TRUSTED_URLS.get(service_name)
response = requests.get(url)
```

审计要点：
- 确认所有远程资源 URL 是否硬编码或来自不可控的配置
- 验证是否禁用了远程协议包含（allow_url_include、allow_url_fopen）
- 检查是否不支持用户指定 URL 的功能

**L1**：有完整白名单保护

- 确认白名单是否为硬编码或从受保护的数据库读取
- 验证白名单匹配是否使用严格比对（=== 或 in_array(..., true)）
- 检查白名单中的 URL 是否覆盖所有包含点
- 验证是否禁用了流协议（php://、data://、file://）和危险协议（ftp://、file://）
- 确认白名单是否可通过参数、环境变量被绕过
- **遇到白名单保护**，详见：[bypassTricks.md - 绕过 URL 白名单](bypassTricks.md#绕过-url-白名单)

```php
// PHP - 正确的白名单实现
$allowed = [
    'api' => 'https://trusted.company.com/api',
    'cdn' => 'https://cdn.company.com'
];

$service = $_GET['service'];
if (isset($allowed[$service])) {
    $url = $allowed[$service];
    include $url;
} else {
    throw new Exception('Service not allowed');
}
```

**L2**：有 URL 来源验证和协议限制但需验证

- 定位 URL 验证逻辑：是否检查 domain、protocol、port
- 核实协议限制的完整性：
  - 仅允许 https:// 且禁用 http://
  - 禁用流协议（php://、data://）
  - 禁用文件协议（file://）
  - **遇到协议限制**，详见：[bypassTricks.md - PHP 远程协议利用](bypassTricks.md#php-远程协议利用)、[编码和格式绕过](bypassTricks.md#编码和格式绕过)
- 验证来源校验是否完善：
  - 硬编码白名单 domain vs 动态检验
  - 是否可绕过（如 HTTP 重定向、DNS 重绑定）
  - **遇到来源检验**，详见：[bypassTricks.md - 绕过 URL 白名单](bypassTricks.md#绕过-url-白名单)
- 检查是否有其他绕过向量（environment variables、Webhook 参数）

```python
# Python - URL 来源验证实现
from urllib.parse import urlparse
import requests

def load_remote_config(url):
    parsed = urlparse(url)

    # 协议限制
    if parsed.scheme not in ['https']:
        raise ValueError('Only HTTPS allowed')

    # 来源限制（白名单 domain）
    allowed_domains = ['api.company.com', 'config.company.com']
    if parsed.netloc not in allowed_domains:
        raise ValueError('Domain not allowed')

    return requests.get(url).json()
```

**L3**：直接加载用户可控 URL

- 用户可直接通过参数指定 URL
- 无协议限制或协议限制不完整（允许 http://、ftp://、file:// 等）
- 无来源检验（任意 domain 都可访问）
- 可能支持包装器协议（php://、data://）
- **遇到用户可控 URL**，详见：[bypassTricks.md - 常见 RFI 场景](bypassTricks.md#常见-rfi-场景)

```php
// PHP - 高风险的 RFI 实现
$url = $_GET['template']; // 用户直接控制
include $url; // 无任何验证

// 或者
$config = simplexml_load_file($_GET['config_url']); // 允许用户指定 URL
```

审计要点：
- 追踪用户输入到 URL 参数的完整数据流
- 验证是否存在任何过滤或验证（即使很弱）
- 检查框架是否自动提供了保护
- 测试各种协议和编码绕过，详见：[bypassTricks.md - 编码和格式绕过](bypassTricks.md#编码和格式绕过)、[PHP 远程协议利用](bypassTricks.md#php-远程协议利用)

**L4**：复杂链路追踪

- 追踪 URL 来源的间接数据流（环境变量、配置文件、Webhook 参数）
- 检查多层代理或包装器的组合（如 php://filter + remote URL）
- 验证完整的利用链：URL 来源 → 参数传递 → 资源加载 → 执行
- 可能涉及：
  - 环境变量注入（URL 来自 $_ENV、getenv()）
  - Webhook 回调（攻击者控制的 Webhook URL）
  - 符号链接追踪（临时文件符号链接）
  - 插件系统（动态加载远程插件库）
- **遇到复杂利用链**，详见：[bypassTricks.md - 隐蔽 RFI 利用](bypassTricks.md#隐蔽-rfi-利用)、[代码执行路径](bypassTricks.md#代码执行路径)

```python
# Python - L4 场景：环境变量 + 远程加载
import os
import importlib.util

# 攻击者可通过修改环境变量控制 URL
plugin_url = os.getenv('PLUGIN_URL')
spec = importlib.util.spec_from_loader(
    'plugin',
    loader=urllib.request.urlopen(plugin_url)
)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin) # RCE！
```

审计要点：
- 回溯所有可能影响 URL 的数据源（参数、环境变量、配置、数据库）
- 绘制完整的数据流图
- 检查是否存在间接的用户控制（如通过 Webhook 回调）
- 验证每一步的防护措施
- 考虑多阶段攻击（先污染数据，后触发加载）

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信 URL）→ 远程加载 → 执行 → 影响
- 每一步都需要函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（URL 白名单、协议限制、来源检验等）
- 绕过技巧总览，详见：[bypassTricks.md - 快速定位](bypassTricks.md#快速定位)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-rfi-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
