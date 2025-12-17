# C/C++ Curl 远程脚本执行 RFI

## 漏洞成因
C/C++ 应用使用 `curl` 从用户可控的远程 URL 拉取配置文件或脚本，经过解析后执行（如通过 `system()` 或 `exec()`），缺乏白名单和协议限制，导致任意代码执行。

---

## Details

### 代码示例

```c
// 危险示例 1: 拉取远程脚本并执行
#include <curl/curl.h>
#include <stdlib.h>

size_t write_callback(void *contents, size_t size, size_t nmemb, FILE *fp) {
    return fwrite(contents, size, nmemb, fp);
}

void execute_remote_script(const char *url) {
    CURL *curl = curl_easy_init();
    FILE *fp = fopen("/tmp/script.sh", "wb");

    curl_easy_setopt(curl, CURLOPT_URL, url);  // 用户可控
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
    curl_easy_perform(curl);
    fclose(fp);

    // 直接执行，无验证
    system("bash /tmp/script.sh");  // RCE
}

// 危险示例 2: 拉取配置文件并 eval 执行
void load_and_execute_config(const char *config_url) {
    char *config_text = curl_get_content(config_url);

    // 配置可能包含要执行的命令
    char cmd[1024];
    sprintf(cmd, "%s", config_text);
    system(cmd);  // RCE
}

// 危险示例 3: 环境变量驱动的远程执行
const char *script_url = getenv("SCRIPT_URL");  // 可被污染
execute_remote_script(script_url);

// 危险示例 4: 命令行参数直接拉取
int main(int argc, char *argv[]) {
    if (argc > 1) {
        execute_remote_script(argv[1]);  // 无验证
    }
}
```

### 快速定位核心操作 (L2: 跳读)
- **HTTP 库**：`curl_easy_setopt()`, `libcurl`, `fopen()` + `curl`
- **执行函数**：`system()`, `exec()`, `popen()`, `fork()` + `execve()`
- **脚本处理**：Bash、Python、Perl 等脚本解释器调用
- **URL 来源**：命令行、环境变量、配置文件、网络请求
- **危险流**：URL 参数 → HTTP 下载 → 文件保存 → system/exec

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - 预定义的允许 URL 列表
  - `static const char *allowed[] = {"https://trusted.com/...", NULL};`
- **URL 验证**：
  - 协议限制：仅 `https://`
  - 域名白名单：`parse_url()` 后检查 host
- **脚本内容验证**：
  - 签名验证（HMAC、GPG）
  - 内容白名单（允许的命令列表）
  - 脚本大小限制
- **执行沙箱**：
  - `seccomp` 限制系统调用
  - `chroot()` 或容器隔离
  - 禁止危险命令（`rm`, `dd` 等）
- **文件权限**：
  - 检查脚本文件权限（仅所有者可读写）
  - 临时目录安全（`/tmp` 权限检查）

---

## Classify

### 漏洞
- 用户可控的脚本/配置 URL
- 无白名单或白名单可绕过
- 拉取内容后直接执行，无签名验证
- 脚本/配置内容可被污染导致命令注入

### 误报
- 脚本 URL 完全硬编码或来自受保护的配置
- 严格白名单验证（URL 和内容）
- 脚本签名被验证（HMAC 或 GPG）
- 执行前脚本内容被验证为合法

### 代码异味
- 脚本 URL 部分可控但有验证
- 拉取与执行分离，中间可被篡改
- 使用弱验证如仅检查文件扩展名

---

## Low risk

- **硬编码 URL 和签名**：脚本 URL 和加密签名都硬编码，无法加载不同脚本
- **协议 + 域名限制**：仅允许 HTTPS 且仅限特定内部域名
- **HMAC/GPG 验证**：脚本被签名或 HMAC 保护，执行前验证
- **内容白名单**：脚本仅支持预定义命令列表，无任意执行
- **权限隔离**：以低权限用户运行，系统调用被 seccomp 限制
- **本地脚本**：脚本预装包内或从本地目录加载

---

## 审计重点

1. 定位所有 curl 和 system/exec 调用
2. 追踪脚本/配置 URL 来源
3. 检查拉取过程中是否有签名或内容验证
4. 检查脚本执行的沙箱隔离
5. 测试 URL 绕过向量
6. 检查环境变量污染和命令注入向量
7. 验证临时文件的权限和清理
