---
title: C/C++ 应用缺失 CSP 响应头审计指南
description: 识别 C/C++ Web 应用中缺失 Content-Security-Policy 响应头的漏洞
---

# C/C++ 应用缺失 CSP 响应头审计指南

## Details

### 漏洞成因分析

C/C++ 作为系统级编程语言广泛应用于高性能 Web 服务（如 Nginx 扩展、Apache 模块、高并发 HTTP 服务器框架）。当使用 libcurl、boost.asio、cpp-httplib 等库构建 HTTP 服务时，开发者需要在生成 HTTP 响应时显式设置 `Content-Security-Policy` 响应头。缺失该头部导致所有返回 HTML 的响应都暴露于 XSS 攻击。

C/C++ 应用中缺失 CSP 头的典型场景：
- 完全未实现 CSP 响应头设置逻辑
- 仅在部分 HTTP 处理函数中设置 CSP，导致路由不一致
- 框架内置中间件未配置 CSP（如 FastCGI、ISAPI 扩展）
- 动态生成 HTML 时忽略了响应头的设置

### 代码示例

**危险模式 1：libcurl 中完全缺失 CSP 头**

```cpp
#include <stdio.h>
#include <string.h>
#include <curl/curl.h>

size_t write_callback(void *contents, size_t size, size_t nmemb, FILE *fp) {
    return fwrite(contents, size, nmemb, fp);
}

int main() {
    CURL *curl = curl_easy_init();
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, "http://example.com");
        struct curl_slist *headers = NULL;
        headers = curl_slist_append(headers, "Content-Type: text/html");
        // ❌ 缺失 Content-Security-Policy 头
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

        FILE *fp = fopen("output.html", "wb");
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
        curl_easy_perform(curl);
        fclose(fp);

        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
    }
    return 0;
}
```

**危险模式 2：boost.asio HTTP 服务器缺失 CSP**

```cpp
#include <boost/asio.hpp>
#include <iostream>
#include <string>

using boost::asio::ip::tcp;

int main() {
    boost::asio::io_context io_context;
    tcp::acceptor acceptor(io_context, tcp::endpoint(tcp::v4(), 8080));

    for (;;) {
        tcp::socket socket(io_context);
        acceptor.accept(socket);

        std::string response =
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            // ❌ 缺失 Content-Security-Policy 头
            "\r\n"
            "<html><body>Welcome</body></html>";

        boost::asio::write(socket, boost::asio::buffer(response));
    }
}
```

**危险模式 3：cpp-httplib 中部分路由无 CSP**

```cpp
#include "cpp-httplib/httplib.h"

int main() {
    httplib::Server svr;

    // 路由 1：有 CSP 保护
    svr.Get("/admin", [](const httplib::Request &, httplib::Response &res) {
        res.set_header("Content-Security-Policy",
                       "default-src 'self'; script-src 'self'");
        res.set_content("<html><body>Admin</body></html>", "text/html");
    });

    // 路由 2：❌ 缺失 CSP
    svr.Get("/", [](const httplib::Request &, httplib::Response &res) {
        res.set_content("<html><body>Home</body></html>", "text/html");
    });

    svr.listen("0.0.0.0", 8080);
    return 0;
}
```

**危险模式 4：FastCGI 应用响应头不完整**

```cpp
#include <fcgiapp.h>
#include <stdio.h>

int main() {
    FCGX_Request request;
    FCGX_Init();
    int sockfd = FCGX_OpenSocket("127.0.0.1:9000", 50);
    FCGX_InitRequest(&request, sockfd, 0);

    while (FCGX_Accept_r(&request) == 0) {
        FCGX_FPrintF(request.out, "Content-Type: text/html\r\n");
        // ❌ 缺失 Content-Security-Policy 头
        FCGX_FPrintF(request.out, "\r\n");
        FCGX_FPrintF(request.out, "<html><body>Content</body></html>");
    }

    FCGX_Free(&request, 1);
    close(sockfd);
    return 0;
}
```

**安全模式**

```cpp
#include "cpp-httplib/httplib.h"

// 创建一个响应头辅助函数确保一致性
void setSecurityHeaders(httplib::Response &res) {
    res.set_header("Content-Security-Policy",
                   "default-src 'self'; "
                   "script-src 'self' https://trusted-cdn.com; "
                   "style-src 'self' https://fonts.googleapis.com; "
                   "img-src 'self' https:; "
                   "font-src 'self' https://fonts.gstatic.com; "
                   "connect-src 'self'; "
                   "frame-src 'none'; "
                   "object-src 'none'; "
                   "base-uri 'self'; "
                   "form-action 'self'");
    res.set_header("X-Content-Type-Options", "nosniff");
    res.set_header("X-Frame-Options", "DENY");
    res.set_header("X-XSS-Protection", "1; mode=block");
}

int main() {
    httplib::Server svr;

    // 为所有 HTML 路由设置 CSP
    svr.Get("/", [](const httplib::Request &, httplib::Response &res) {
        setSecurityHeaders(res);
        res.set_content("<html><body>Protected</body></html>", "text/html");
    });

    svr.Get("/admin", [](const httplib::Request &, httplib::Response &res) {
        setSecurityHeaders(res);
        res.set_content("<html><body>Admin</body></html>", "text/html");
    });

    svr.listen("0.0.0.0", 8080);
    return 0;
}
```

### 快速定位技巧

**【L1:关键词扫描】- 定位核心操作**

使用关键词快速扫描 HTTP 响应头设置位置：
- `set_header` / `append_header` - C++ HTTP 库常用的响应头设置方法
- `curl_slist_append` - libcurl 响应头操作
- `FCGX_FPrintF` / `printf("Content-Type")` - FastCGI/CGI 响应头写入
- `Content-Type` - 定位所有生成 HTML 的响应位置
- `HTTP/1.1` - 查找手工拼接 HTTP 响应的地方
- `res.set_content()` / `response.write()` - 响应体写入位置

搜索这些关键词能快速定位响应头设置的代码块。

**【L2:跳读】- 定位保护机制**

快速跳读以下位置判断 CSP 配置状态：
- HTTP 处理函数的入口（如 `handleRequest()`、`process()` 回调函数）
- 框架初始化配置文件（HTTP 库的配置、中间件注册）
- 响应头设置的集中位置（如统一的响应生成函数、基类方法）
- 在响应头设置和响应体写入之间的代码段
- 搜索 `Content-Security-Policy` 在整个项目中的出现次数和位置

快速跳读这些位置可判断是否存在 CSP 配置。

**【L3:逐行读】- 验证配置有效性**

逐行审视关键细节：
- 确认所有生成 HTML 响应的函数都设置了 CSP 头（不仅仅是部分路由）
- 检查响应头设置的位置是否在响应体写入之前
- 验证 CSP 策略字符串是否正确格式化（分号分隔、无语法错误）
- 确认是否存在条件性跳过 CSP 设置的逻辑（如 `if (debug)` 条件）
- 检查是否在响应头中设置了空的或占位符的 CSP 值

**【L4:跨模块追踪】- 追踪完整流程**

对于复杂架构追踪完整的请求-响应流程：
- 从 HTTP 请求入口追踪到响应生成函数
- 跨越多个源文件跟踪响应头设置是否一致应用
- 检查是否在基类或公共响应函数中集中设置 CSP（减少遗漏风险）
- 追踪中间件或拦截器是否统一注入 CSP 头
- 检查是否存在响应头继承或覆盖的逻辑

---

## Classify

### 漏洞确认标准

确认为真实漏洞的条件（满足任一条即为漏洞）：

1. **完全缺失 CSP 配置**：应用的所有 HTML 响应都未设置 `Content-Security-Policy` 响应头

2. **部分路由缺失保护**：虽然某些路由设置了 CSP，但其他返回 HTML 的路由未设置，导致保护不一致

3. **响应头设置顺序错误**：CSP 头在响应体已发送后才设置（无效状态），或在响应体中间插入

4. **CSP 头值为空或占位符**：设置了 CSP 头但值为空字符串、`null` 或 `TODO` 等占位符

5. **条件性禁用 CSP**：存在开发环境、调试模式等条件分支跳过 CSP 设置

6. **HTTP/HTTPS 不一致**：仅在 HTTP 上设置 CSP，HTTPS 路由未设置，或反之

### 误报判定

以下情况应判定为误报：

1. **纯 API 应用**：应用仅返回 JSON（`Content-Type: application/json`），无 HTML 生成，不需要 CSP

2. **仅部分非 HTML 路由**：如果应用同时返回 API 和 HTML：
   - HTML 路由都必须有 CSP
   - 不能因部分 API 路由缺失 CSP 就判定为漏洞

3. **二进制文件传输**：返回图片、文件下载等二进制内容（`Content-Type: image/*`、`application/octet-stream`），不需要 CSP

4. **重定向响应**：仅进行 HTTP 重定向（301/302/307），无 HTML 内容生成

5. **网关/反向代理层保护**：如果在 Nginx、Apache 或 WAF 层已配置全局 CSP，可不判定为漏洞（需验证）

6. **Content-Security-Policy-Report-Only**：仅在测试环境使用 Report-Only 模式进行验证是可接受的，但生产环境必须使用强制执行

### 代码异味识别

识别为代码异味（需优化但不算漏洞）的情况：

1. **CSP 配置过于宽松**：虽然设置了 CSP，但使用了 `*`、`https:` 等过宽松的白名单

2. **缺少响应头统一管理**：CSP 在多个处理函数中重复设置，导致维护困难和遗漏风险

3. **缺少 nonce/hash 机制**：返回 HTML 中包含内联脚本但未使用 nonce 或 hash 保护

4. **缺少报告机制**：未配置 `report-uri` 或 `report-to` 导致 CSP 违规无法监控

5. **硬编码 CSP 策略**：CSP 配置硬编码在代码中，难以根据环境动态调整

---

## Low risk

### 可降低风险等级的场景

以下情况可将风险评级从高降低为中或低：

1. **内网应用或环境限制**：应用部署在完全隔离的内网或局域网环境，无外部网络访问，无 XSS 风险场景，CSP 的必要性下降

2. **已部署其他 XSS 防护层**：
   - 在反向代理层（Nginx、Apache）配置全局 CSP 头
   - 使用 WAF（Web Application Firewall）进行流量检测和过滤
   - 使用模板引擎的自动上下文转义功能确保输出编码
   - 实施严格的输入验证和输出编码库

3. **应用实现了其他防护机制**：
   - 使用了框架内置的 XSS 防护库
   - 实现了 HTTPOnly、Secure Cookie 标志
   - 使用了 X-Content-Type-Options、X-Frame-Options 等相关安全头

4. **低敏感度应用**：
   - 内容完全来自受信的内部来源，无用户生成内容（UGC）
   - 应用不涉及任何敏感业务数据（支付、认证、个人隐私信息）
   - 应用功能简单，仅展示静态或预定义的内容

5. **已知的技术限制**：
   - 应用需兼容过时浏览器而无法使用 CSP 的现代语法
   - 使用的第三方库或框架严重限制了 CSP 的兼容性
   - 依赖的 JavaScript 框架无法适配 nonce/hash 机制

6. **临时测试或演示应用**：虽然生产环境应配置 CSP，但对于明确标记的临时应用、POC、演示项目可给予宽限

### 风险缓解建议

即使存在上述低风险情况，仍应考虑以下缓解措施提高安全姿态：

- 逐步在应用层实施 CSP（即使网关层已有保护）形成纵深防御
- 在 Report-Only 模式下逐步严化 CSP 策略，积累兼容性数据
- 结合其他防护头部（X-Frame-Options、X-Content-Type-Options、Referrer-Policy）
- 实施严格的内容来源审核和依赖库检查流程
- 定期进行安全审计和动态 XSS 检测
