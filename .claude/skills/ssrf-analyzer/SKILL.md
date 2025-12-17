---
name: ssrf-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 SSRF（服务器端请求伪造）漏洞；重点关注检测不安全的服务端网络请求构造，即用户可控输入（URL、主机名、IP地址等）未经适当验证或过滤直接用于发起服务端请求；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
当项目中存在由用户可控输入（如URL、主机名、IP地址、路径等）触发服务端发起网络请求的逻辑时，需重点审计对应代码。此类漏洞常见于文件下载、Webhook回调、第三方服务集成、图片/资源预览、API代理等涉及服务端主动发起HTTP(S)、FTP、file://等协议请求的业务模块。

---

**Early exit**

**在开始审计之前，必须首先运行 SSRF 扫描脚本完成初步检索**，快速定位项目中是否存在可疑的服务端网络请求代码。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行 SSRF 扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

若项目代码中完全不包含任何由用户输入驱动的服务端网络请求行为（例如无HTTP客户端调用、无curl/fetch/URLConnection等封装、无外部资源加载逻辑），则可快速退出对该目标的SSRF审计。

---

## 通用 SSRF 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：用户输入直接用于构造请求 URL（URL/主机名/IP/端口可控）、协议验证缺失或不足（未限制协议、file:// 未禁止）、内网地址过滤不足（未验证内网地址、过滤可被绕过）、云环境 Metadata 服务访问（AWS/GCP/Azure/Kubernetes）、特定业务场景 SSRF（Webhook/OAuth 回调/图片预览/API 代理/文件下载）、URL 解析和验证缺陷（解析不一致、白名单不严格）、请求跟随重定向未限制、响应数据未过滤直接返回

查看详细说明：
- AWS IMDSv1 服务访问漏洞，详见：[ssrf_aws_imdsv1.md](ssrf_aws_imdsv1.md)

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的 HTTP 客户端实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
- 使用 RestTemplate 处理用户提供的 URL，未实施白名单或内网地址过滤，详见：[Java_RestTemplateUserURL.md](Java_RestTemplateUserURL.md)  
- HttpURLConnection 直接使用用户输入构造请求，缺少目标验证，详见：[Java_HttpURLConnectionSSRF.md](Java_HttpURLConnectionSSRF.md)  
- OAuth 回调处理中未校验重定向目标地址，详见：[Java_OAuthCallbackProxy.md](Java_OAuthCallbackProxy.md)

**Python**  
- 使用 requests/urllib/aiohttp 等库发起用户可控 URL 请求，未校验目标地址，详见：[Python_UserControlledURLFetch.md](Python_UserControlledURLFetch.md)  
- Webhook 回调代理场景中直接使用用户输入构造请求目标，详见：[Python_WebhookProxySSRF.md](Python_WebhookProxySSRF.md)  
- 图片预览功能从用户提供的 URL 加载资源，未过滤协议或内网地址，详见：[Python_ImagePreviewFromURL.md](Python_ImagePreviewFromURL.md)

**Go**  
- 使用 net/http 包的 http.Get/http.Post 直接拼接用户输入，未校验目标主机或协议，详见：[Go_HTTPClientFromUserInput.md](Go_HTTPClientFromUserInput.md)  
- 微服务通信代理场景中转发用户控制的请求目标，详见：[Go_ServiceProxySSRF.md](Go_ServiceProxySSRF.md)  
- 外部数据拉取功能使用用户输入作为请求地址，缺少安全验证，详见：[Go_ExternalDataFetcher.md](Go_ExternalDataFetcher.md)

**PHP**  
- 使用 curl_exec() 处理用户输入的 URL，未限制协议或目标地址，详见：[PHP_CurlUserURL.md](PHP_CurlUserURL.md)  
- file_get_contents() 直接读取用户提供的 URL，缺少协议和地址校验，详见：[PHP_FileGetContentsSSRF.md](PHP_FileGetContentsSSRF.md)  
- 图片处理功能从用户 URL 加载远程图片，未过滤内网地址，详见：[PHP_RemoteImageProcessor.md](PHP_RemoteImageProcessor.md)

**JavaScript / TypeScript (Node.js)**  
- 使用 axios/node-fetch 发起用户控制的请求，缺乏对目标地址的过滤，详见：[NodeJS_FetchUserProvidedURL.md](NodeJS_FetchUserProvidedURL.md)  
- API 网关转发场景中直接使用用户输入构造上游请求，详见：[NodeJS_APIGatewaySSRF.md](NodeJS_APIGatewaySSRF.md)  
- 服务端渲染（SSR）预取资源时使用用户提供的 URL，未限制协议或地址，详见：[NodeJS_SSRResourcePrefetch.md](NodeJS_SSRResourcePrefetch.md)

**C/C++**  
- 使用 libcurl 直接处理用户输入构造请求目标，未做地址合法性校验，详见：[C_LibcurlUserControl.md](C_LibcurlUserControl.md)  
- 自实现 socket 连接使用用户控制的主机和端口参数，缺少安全验证，详见：[C_CustomSocketSSRF.md](C_CustomSocketSSRF.md)

**Rust**  
- 使用 reqwest/hyper 等库发起用户输入决定的请求，未实施安全策略（如禁止内网IP、限制协议），详见：[Rust_ReqwestUserURL.md](Rust_ReqwestUserURL.md)  
- 异步任务调度器中使用用户参数构造请求目标，缺少地址验证，详见：[Rust_AsyncTaskProxy.md](Rust_AsyncTaskProxy.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注服务端请求与网络交互相关的实现：**

- 查阅项目文档，重点关注外部资源访问、第三方服务集成、Webhook 处理等说明
- 理解业务领域和核心功能，识别涉及服务端发起网络请求的场景
- 识别关键组件、模块及其关系，特别是 HTTP 客户端、API 代理、文件下载器、Webhook 处理器
- 梳理应用流程（重点：外部资源获取流程、回调处理流程、第三方服务调用链）
- 识别关键业务功能（文件下载、图片预览、Webhook 回调、数据拉取、API 转发、第三方认证回调等）
- 理解所用技术栈和框架（Web 框架、HTTP 客户端库类型和版本，如 requests、RestTemplate、axios、curl 等）
- 查阅配置文件以理解系统行为（白名单配置、代理配置、超时设置、允许的协议等）
- 定位服务端请求的发起位置（HTTP 客户端调用、URL 构造、主机名拼接）
- 定位输入验证位置（URL 校验函数、协议过滤、内网地址检查、白名单验证）
- 识别用户输入传递方式（请求参数、请求体字段、Header、文件内容等）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如不包含任何由用户输入驱动的服务端网络请求行为），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目存在由用户输入控制的服务端请求功能并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 SSRF 漏洞的参考指南

SSRF 漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 SSRF 漏洞模式（所有项目必审）**

在 **通用 SSRF 漏洞模式** 章节中，列举了所有涉及服务端发起网络请求的应用都必须审计的 SSRF 问题：
- 用户输入直接用于构造请求 URL（URL 完全可控、主机名/IP/端口可控）
- 协议验证缺失或不足（未限制协议、file:// 未禁止、协议白名单不完整）
- 内网地址过滤不足（未验证内网地址、过滤可被绕过）
- 云环境 Metadata 服务访问（AWS、GCP、Azure、Kubernetes）
- 特定业务场景 SSRF（Webhook、OAuth 回调、图片/资源预览、API 代理、文件下载）
- URL 解析和验证缺陷（解析不一致、白名单不严格）
- 请求跟随重定向未限制（重定向到内网、次数未限制、目标未重新验证）
- 响应数据未过滤直接返回（内网响应返回、错误信息泄露）

这些问题与编程语言无关，是服务端请求安全设计层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言 HTTP 客户端实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript/TypeScript、C/C++、Rust）
- 列出该语言 HTTP 客户端库的典型 SSRF 缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 SSRF 漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `ssrf_user_url_direct.md`、`Python_UserControlledURLFetch.md`、`Java_RestTemplateUserURL.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（用户可控输入）→ URL/主机构造 → 服务端请求发起 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（如白名单、协议过滤、内网地址拦截等）

### 绕过技巧参考

遇到以下保护机制时，参考 [bypassTricks.md](bypassTricks.md) 中的对应章节：

**协议限制绕过**
- 遇到协议白名单/黑名单验证 → 详见 [bypassTricks.md 协议滥用章节](bypassTricks.md#协议滥用)
- 遇到 file:// 协议过滤 → 详见 [bypassTricks.md file:// 协议利用](bypassTricks.md#file-协议利用)

**内网地址过滤绕过**
- 遇到 127.0.0.1、localhost 黑名单 → 详见 [bypassTricks.md IP地址表示法和解析行为理解](bypassTricks.md#ip地址表示法和解析行为理解)
- 遇到 10.x、192.168.x、172.16.x 私有IP过滤 → 详见 [bypassTricks.md 私有IP范围识别](bypassTricks.md#私有ip范围识别)
- 遇到 IP 地址格式检查 → 详见 [bypassTricks.md IP地址编码绕过](bypassTricks.md#ip地址编码绕过)
- 遇到域名解析后IP验证 → 详见 [bypassTricks.md 增强IP地址验证的完整性](bypassTricks.md#增强ip地址验证的完整性)

**重定向和DNS验证绕过**
- 遇到重定向跟随限制 → 详见 [bypassTricks.md 302跳转绕过技术详解](bypassTricks.md#302跳转绕过技术详解)
- 遇到 DNS 解析验证 → 详见 [bypassTricks.md DNS重绑定绕过技术](bypassTricks.md#dns重绑定绕过技术)

**URL 解析验证绕过**
- 遇到 URL 正则匹配验证 → 详见 [bypassTricks.md HTTP基本身份认证格式绕过](bypassTricks.md#http基本身份认证格式绕过)
- 遇到 parse_url() 等函数验证 → 详见 [bypassTricks.md URL解析库差异](bypassTricks.md#url解析库差异)

**白名单/黑名单绕过**
- 遇到域名黑名单 → 详见 [bypassTricks.md 绕过黑名单章节](bypassTricks.md#绕过黑名单)
- 遇到开放重定向点 → 详见 [bypassTricks.md 开放重定向链](bypassTricks.md#开放重定向链)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-ssrf-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
