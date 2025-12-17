# C HTTP Location Header User Input

## Details

### 代码特征

C/C++ 应用中直接使用 HTTP 响应头 `Location` 执行重定向，核心风险在于攻击者可控制重定向目标：

```c
// 漏洞示例
const char *redirect_url = get_query_param("redirect");
printf("HTTP/1.1 302 Found\r\n");
printf("Location: %s\r\n", redirect_url);
printf("\r\n");
```

**快速定位核心操作** `(L1:关键词扫描)`

- 扫描 `Location:` 响应头的所有输出点（`printf`, `sprintf`, `fprintf`, `write` 等）
- 检查 `Location` 头后的值是否直接来自用户输入参数（`getenv("QUERY_STRING")`、`get_query_param()`、`parse_request()` 等）
- 关键参数名：`redirect`、`url`、`next`、`return`、`target`、`goto`、`back`、`referer`
- 重定向状态码：`301`, `302`, `303`, `307`, `308`

**快速定位保护机制** `(L2-L4:跳读/逐行读/跨模块追踪)`

- **L2**：检查 `Location` 赋值前后 5-10 行，查看是否调用验证函数（如 `validate_url()`, `is_safe_redirect()`, `check_whitelist()`）
- **L2**：扫描是否有 `strstr(url, "://")`、`strstr(url, "//")`、`strchr(url, ':')` 等协议检查
- **L3**：完整阅读验证函数实现，确认逻辑是否覆盖所有输入源
- **L3**：检查是否存在 URL 长度限制和缓冲区安全问题（`strcpy` vs `strncpy`）
- **L4**：追踪用户输入参数从获取到 `printf` 的完整流程，识别绕过点或多个入口

**验证机制检查清单**

| 防护方式 | 检查要点 | 审计等级 |
|---------|---------|---------|
| **白名单验证** | Location 值是否与预定义 URL 列表精确匹配 | L2 |
| **相对路径隔离** | 是否拒绝包含 `://` 和 `//` 的 URL | L2 |
| **协议限制** | 是否仅允许 http 或 https 协议 | L3 |
| **域名检查** | 域名是否验证属于本域或白名单列表 | L3 |
| **长度验证** | 参数长度是否有检查和限制 | L2 |
| **缓冲区安全** | 是否使用 strncpy/snprintf 而非 strcpy/sprintf | L2 |
| **完整链路** | 从输入源到 printf 的全路径验证 | L4 |

---

## Classify

研判漏洞/误报/代码异味的三个维度：

**数据流完整性**：追踪用户输入到 `Location` 头的完整路径
- 若输入直接使用，无任何验证 → **漏洞**
- 若输入经严格白名单校验（仅允许 `/path` 格式或预定义域名）→ **低风险**
- 若只有简单黑名单或字符替换 → **需深入分析**

**防护机制有效性**：评估现有防御的绕过可能性
- **漏洞**：无验证、黑名单可被编码绕过（如 `//example.com`、`//\/\/example.com`、协议混淆 `hTtP://`）
- **误报**：完整的 URL 解析（协议/域名/路径分离）+ 白名单 + 协议限制
- **代码异味**：部分防护但逻辑缺陷、存在明显绕过点、验证在长度检查之后

**场景合理性**：区分业务需求与真实风险
- 登录后跳转、OAuth 回调等敏感场景需要更强的验证
- 内部系统跳转（如 `/dashboard` 相对路径）可接受
- 跨域重定向需严格白名单

---

## Low risk

以下情况可评级为低风险：

**1. 精确白名单验证**
- Location 值被严格限制在明确定义的 URL 列表中
- 使用 `strcmp()` 或 `strncmp()` 进行逐字符精确匹配
- 白名单包含完整绝对 URL（如 `https://trusted.com/page`）或相对路径（如 `/dashboard`）
- 不允许任何用户参数化重定向目标

**2. 相对路径隔离**
- 应用明确检查目标为相对路径（以 `/` 开头但不以 `//` 开头）
- 检查逻辑拒绝所有包含 `://` 的 URL 和以 `//` 开头的 URL
- 实现方式：`strstr(url, "://") == NULL && strstr(url, "//") == NULL`

**3. 严格协议和域名验证**
- 仅允许 http 或 https 协议，拒绝 javascript、data、file 等特殊协议
- 使用安全字符串函数进行 URL 解析，不使用不安全的 strcpy/sprintf 直接拼接
- 域名与本域或白名单进行精确匹配

**4. 缓冲区安全**
- 所有参数拷贝使用 `strncpy()`, `strncat()` 等带长度限制的函数
- URL 长度在使用前进行检查和限制

**5. 数据源受限**
- Location 值来自受保护的配置文件或数据库（仅管理员可修改）
- 用户无法直接控制重定向参数
- 重定向用于低敏感度场景（如静态错误页面、日志记录）
