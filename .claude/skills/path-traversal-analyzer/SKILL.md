---
name: path-traversal-analyzer
description: 专业的审计工作流程，通过静态与动态分析识别并验证路径遍历（Path Traversal）风险；聚焦用户可控路径被用于文件系统访问的链路，结合各语言参考指南定位高危点。
---

**Attention**
当项目存在"外部输入 → 文件系统访问"的路径解析时（下载/预览接口、日志调取、上传处理等），若缺乏规范化或白名单校验，用户可通过 `../`、绝对路径、符号链接等绕过限制，触发路径遍历，继而泄露敏感配置、读取系统文件。审计时需重点追踪字符串拼接构建路径、`open`/`readFile`/`send_file` 等敏感 API、上传与解压流程的落盘位置。

**Early exit**
若项目完全不涉及文件系统交互（纯内存计算服务）、所有静态资源由 CDN 托管且无本地落盘逻辑、所有文件访问统一通过成熟库并内置严格的白名单映射（经确认无自定义扩展）、或系统仅处理固定配置文件且路径硬编码不可被外界影响，则可快速结束对该漏洞类型的审计。

---

## 通用路径遍历漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：路径构建缺乏验证或过滤（用户输入直接拼接、路径规范化不完整、无白名单限制）、文件访问未验证根目录限制（未检查最终路径范围、前导斜杠/绝对路径绕过）、符号链接未检测或处理不当、特定场景路径遍历（文件下载/预览、日志查看、上传文件名、归档解压 Zip Slip、静态服务）、跨平台路径差异导致绕过（路径分隔符、大小写敏感性）

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的文件系统操作实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- 在 Spring/Servlet 文件下载接口中通过字符串拼接或 `Paths.get` 直接使用用户输入的文件名，未经白名单校验，详见：[java_path_traversal_resource_loading.md](java_path_traversal_resource_loading.md)
- 使用 `Files.readAllBytes`、`ResourceUtils.getFile` 直接访问用户可控路径的资源文件，缺乏路径归一化，详见：[java_resource_access_unsafe.md](java_resource_access_unsafe.md)

**Python**
- 在 Flask/Django 文件预览或下载接口使用 `os.path.join`/`open`/`send_file` 直接拼接用户输入，未经根目录校验，详见：[python_path_traversal_send_file.md](python_path_traversal_send_file.md)
- 日志查看功能通过用户参数读取任意日志文件，缺乏路径白名单限制，详见：[python_log_file_access.md](python_log_file_access.md)

**Go**
- 使用 `http.FileServer` 或自定义静态文件路由，直接拼接用户输入路径，未经前缀校验，详见：[go_path_traversal_fileserver.md](go_path_traversal_fileserver.md)
- 通过 `os.Open` 访问用户指定的日志或配置文件，`filepath.Clean` 使用不当或未验证根目录，详见：[go_filepath_clean_bypass.md](go_filepath_clean_bypass.md)

**PHP**
- 使用 `fopen`/`file_get_contents` 直接拼接用户控制的文件名，缺乏路径过滤，详见：[php_upload_filename_traversal.md](php_upload_filename_traversal.md)

**JavaScript / TypeScript（Node.js后端）**
- 在 Express/Koa/Nest 静态文件服务中使用 `fs.readFile`/`fs.createReadStream` 直接拼接请求参数，未经规范化，详见：[nodejs_path_traversal_static.md](nodejs_path_traversal_static.md)
- Node.js 路径遍历漏洞，详见：[js_node_path_traversal.md](js_node_path_traversal.md)
- NestJS/Next.js/BFF 服务中 `path.join` 使用不当，未验证目录白名单或忽略前导斜杠，详见：[ts_server_path_traversal.md](ts_server_path_traversal.md)

**C/C++**
- 使用 `open`/`fopen`/`std::ifstream` 直接拼接用户输入形成文件路径进行底层服务、Nginx/Apache 模块或 CLI 工具的文件操作，未经规范化验证，详见：[c_path_traversal_file_ops.md](c_path_traversal_file_ops.md)
- 归档解压后未验证目标目录，允许相对路径导致文件覆盖或遍历，详见：[c_archive_extraction.md](c_archive_extraction.md)
- 使用用户输入路径参数访问配置或日志文件，缺乏符号链接检测和沙箱限制，详见：[c_symlink_traversal.md](c_symlink_traversal.md)

**Rust**
- 在 `warp`/`actix-web` 文件下载接口中使用 `std::fs::File` 或 `tokio::fs` 直接拼接用户输入路径，缺乏 `canonicalize` 验证，详见：[rust_path_traversal_file_access.md](rust_path_traversal_file_access.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注文件系统交互相关的实现：**

- 查阅项目文档，重点关注文件处理、资源访问、静态文件服务的说明
- 理解业务领域和核心功能，识别涉及文件读取、下载、预览、上传的场景
- 识别关键组件、模块及其关系，特别是文件服务模块、静态资源网关、反向代理配置
- 梳理应用流程（重点：文件上传流程、文件下载/预览流程、资源分发逻辑）
- 识别关键业务功能（文件下载、日志查看、报告导出、归档解压等）
- 理解所用技术栈和框架（Web框架、文件处理库，如 Spring、Express、Django 等）
- 查阅配置文件以理解系统行为（静态文件根目录、上传目录配置、符号链接处理策略）
- 定位文件路径的构建位置（路径拼接函数、`os.path.join`、`Paths.get`、`path.join`、字符串拼接等）
- 定位文件访问的执行位置（`open`、`fopen`、`readFile`、`send_file` 等）
- 识别用户输入如何影响文件路径（URL参数、请求体、文件名、Cookie、HTTP Header等）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件，可立即退出该漏洞类型的审计，无需继续深入分析。

### 步骤 1：查阅路径遍历漏洞的参考指南

在 **通用路径遍历漏洞模式** 章节中，列举了所有涉及文件系统操作的应用都必须审计的安全问题：
- 路径构建缺乏验证或过滤（用户输入直接拼接、路径规范化不完整、无白名单限制）
- 文件访问未验证根目录限制（未检查最终路径范围、前导斜杠绕过、绝对路径覆盖）
- 符号链接未检测或处理不当（符号链接指向受限目录、硬链接绕过）
- 特定场景路径遍历（文件下载/预览、日志查看、上传文件名、归档解压、静态服务）
- 跨平台路径差异导致绕过（路径分隔符、大小写敏感性）

这些问题与编程语言无关，是文件系统操作安全设计层面的通用缺陷，任何 Web 应用都需要检查。

**语言特定实现：**

在 **语言特定实现** 章节中，按编程语言组织了各语言文件系统操作实现方式的特定问题。根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用路径遍历漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

路径遍历漏洞审计采用分层的审计等级制度，根据文件系统交互的方式来指导审计深度。

| 等级 | 名称 | 时间 | 文件访问特征 |
|------|------|------|------------|
| **L0** | 快速跳过 | 1-2 分钟 | 无文件系统交互：纯内存计算、CDN 托管、所有路径硬编码、或禁用动态路径访问 |
| **L1** | 快速扫描 | 3-5 分钟 | 有文件访问 + 完整白名单映射：需确认白名单完整性和绕过可能性 |
| **L2** | 跳读 | 5-10 分钟 | 有文件访问 + 路径规范化验证：验证规范化完整性和根目录限制有效性 |
| **L3** | 逐行读 | 15-30 分钟 | 直接使用用户输入的路径：无防护、规范化不完整、根目录限制缺失 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：符号链接、Zip Slip、上传→存储→访问、跨平台差异 |

### 快速判断流程

**第 1 步：是否存在文件系统交互？**
- 无文件系统交互（纯内存计算、CDN 托管、无本地文件访问） → **L0 跳过**
- 有文件系统交互（open、readFile、send_file 等） → 继续第 2 步

**第 2 步：文件路径是否可控？**
- 完全不受用户输入影响，仅硬编码或配置控制 → **L0**
- 用户通过参数、请求体、URL 影响文件路径 → 继续第 3 步

**第 3 步：是否有路径验证？**
- 严格的白名单映射（已知安全的完整文件或目录列表） → **L1**
- 路径规范化 + 根目录限制验证（canonicalize、realpath 等） → **L2**
- 无防护或防护可绕过（无路径规范化、无根目录检验、黑名单不完整） → **L3+**
- 复杂链路（上传→存储→访问、符号链接、Zip Slip、跨平台） → **L4**
- 支持流协议（php://、data://、file://）且可控 → **L3+**

### 各等级操作指南

**L0**：无文件系统交互

```java
// Java - 硬编码文件路径
@GetMapping("/download/invoice")
public ResponseEntity<Resource> downloadInvoice() {
    String filePath = "/var/app/resources/invoices/standard.pdf"; // 硬编码
    Resource resource = new FileSystemResource(filePath);
    return ResponseEntity.ok(resource);
}

// Python - CDN 托管，无本地文件
@app.route('/download/<file_id>')
def download(file_id):
    cdn_url = f"https://cdn.company.com/files/{file_id}"
    return redirect(cdn_url)

// Node.js - 硬编码配置
const filePaths = {
    'terms': '/static/legal/terms.pdf',
    'privacy': '/static/legal/privacy.pdf'
};

app.get('/legal/:doc', (req, res) => {
    if (req.params.doc in filePaths) {
        res.download(filePaths[req.params.doc]);
    }
});
```

审计要点：
- 确认是否存在任何动态文件路径构建
- 验证是否禁用了远程协议包含（allow_url_fopen、allow_url_include）
- 检查是否所有文件访问都通过白名单或硬编码

**L1**：有完整白名单保护

- 确认白名单是否为硬编码或从受保护的数据库读取
- 验证白名单是否包含完整的文件路径或目录
- 检查白名单匹配是否使用严格比对（=== 或 in_array(..., true)）
- 验证是否禁用了符号链接（symlink 检测）
- 确认白名单是否可通过 URL 编码、双重编码、Unicode 编码被绕过（遇到编码保护机制，详见 [bypassTricks.md](bypassTricks.md) **目录遍历编码** 部分）

```go
// Go - 严格的白名单映射
var AllowedDocuments = map[string]string{
    "invoice":    "/secure/invoices/2024.pdf",
    "receipt":   "/secure/receipts/payment.pdf",
    "contract":  "/secure/contracts/agreement.pdf",
}

func DownloadDocument(w http.ResponseWriter, r *http.Request) {
    docID := r.URL.Query().Get("id")

    // 严格白名单检查
    filePath, exists := AllowedDocuments[docID]
    if !exists {
        http.Error(w, "Document not found", http.StatusNotFound)
        return
    }

    http.ServeFile(w, r, filePath)
}
```

**L2**：有路径规范化和根目录限制

- 定位路径规范化逻辑：是否使用 realpath、canonicalize、path.resolve 等
- 核实规范化的完整性：
  - 是否处理了 `../` 相对路径（遇到过滤保护机制，详见 [bypassTricks.md](bypassTricks.md) **目录遍历编码** 部分）
  - 是否处理了绝对路径前缀（leading slash 绕过，详见 [bypassTricks.md](bypassTricks.md) **前导斜杠绕过** 部分）
  - 是否处理了双重编码（%252e%252e%252f，详见 [bypassTricks.md](bypassTricks.md) **目录遍历编码** 部分）
  - 是否处理了 Unicode 编码（..%c0%af，详见 [bypassTricks.md](bypassTricks.md) **目录遍历编码** 部分）
  - 是否处理了大小写差异（..\\ vs ../ on Windows，详见 [bypassTricks.md](bypassTricks.md) **Windows路径差异** 部分）
- 验证根目录限制的有效性：
  - 最终路径是否在允许的目录范围内
  - 是否检查了符号链接（readlink、lstat，遇到符号链接保护机制，详见 [bypassTricks.md](bypassTricks.md) **符号链接绕过检查** 部分）
  - 是否禁用了 null bytes 和流协议（遇到扩展名验证保护机制，详见 [bypassTricks.md](bypassTricks.md) **Null Byte截断** 部分）

```python
# Python - 路径规范化 + 根目录验证
import os
from pathlib import Path

BASE_DIR = Path('/var/app/uploads')

def safe_file_download(user_filename):
    # 规范化路径
    requested_path = (BASE_DIR / user_filename).resolve()

    # 根目录限制：确保在 BASE_DIR 内
    if not str(requested_path).startswith(str(BASE_DIR)):
        raise ValueError('Path traversal detected!')

    # 符号链接检测
    if requested_path.is_symlink():
        raise ValueError('Symlink not allowed!')

    # 文件存在检查
    if not requested_path.exists():
        raise FileNotFoundError('File not found')

    return requested_path
```

**L3**：直接使用用户输入的路径

- 用户可直接通过参数指定文件路径
- 无路径规范化或规范化不完整
- 无根目录限制或限制可绕过
- 可能支持相对路径遍历（../）、绝对路径、符号链接

```php
// PHP - 高风险的路径遍历
$file = $_GET['file']; // 用户直接控制
readfile($file); // 无任何验证

// 或者
$filepath = "/uploads/" . $_GET['filename']; // 字符串拼接
$content = file_get_contents($filepath); // 无规范化
```

审计要点：
- 追踪用户输入到文件访问的完整数据流
- 验证是否存在任何过滤或验证（即使很弱）
- 检查框架是否自动提供了保护（Spring Security、Express 中间件等）
- 测试各种路径遍历技巧（遇到黑名单过滤保护机制，详见 [bypassTricks.md](bypassTricks.md) **黑名单绕过** 部分；遇到路径拼接保护机制，详见 [bypassTricks.md](bypassTricks.md) **平台特定绕过** 部分）

**L4**：复杂链路追踪

- 涉及多个步骤的攻击链：文件上传 → 存储位置 → 访问接口
- 符号链接指向受限目录的绕过
- Zip Slip 攻击：解压到限制目录外
- 跨平台差异导致的绕过：Windows 路径分隔符、大小写敏感性
- 环境变量污染：BASE_DIR、UPLOAD_DIR 来自用户可控源

```java
// Java - L4 场景：上传 → 解压 → 访问链路
@PostMapping("/upload")
public void uploadZip(@RequestParam MultipartFile file) throws IOException {
    String uploadDir = System.getenv("UPLOAD_DIR"); // 环境变量

    // 问题1：环境变量可被污染
    ZipInputStream zis = new ZipInputStream(file.getInputStream());
    ZipEntry entry;
    while ((entry = zis.getNextEntry()) != null) {
        // 问题2：Zip Slip - 没有验证 entry.getName()
        String filePath = uploadDir + "/" + entry.getName(); // 包含 ../
        Files.write(Paths.get(filePath), zis.readAllBytes());
    }
}

@GetMapping("/file")
public ResponseEntity<Resource> getFile(@RequestParam String path) {
    // 问题3：访问时无根目录限制
    File file = new File(uploadDir + "/" + path);
    return ResponseEntity.ok(new FileSystemResource(file));
}
```

审计要点：
- 回溯文件的完整生命周期：上传 → 存储 → 访问
- 绘制数据流图，标注每个环节的风险点
- 检查是否存在间接控制（环境变量、配置参数）
- 验证解压、复制、移动等操作的安全性（遇到归档解压保护机制，详见 [bypassTricks.md](bypassTricks.md) **归档解压 (Zip Slip)** 部分）
- 考虑跨平台差异（Windows vs Linux 的路径处理，详见 [bypassTricks.md](bypassTricks.md) **平台特定绕过** 部分）
- 检查是否有竞态条件（TOCTOU）

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信输入）→ 路径构建 → 文件操作 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（路径规范化、白名单校验、沙箱限制等）
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-path-traversal-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
