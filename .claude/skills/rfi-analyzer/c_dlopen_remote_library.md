# C/C++ 远程库加载 RFI（dlopen）

## 漏洞成因
C/C++ 应用使用 `curl`、`libcurl` 等库加载用户指定的远程库文件，通过 `dlopen()` 动态加载执行，未验证来源和完整性，导致任意代码执行。

---

## Details

### 代码示例

```c
// 危险示例 1: 下载后 dlopen 加载
#include <curl/curl.h>
#include <dlfcn.h>

void load_remote_plugin(const char *url) {
    CURL *curl = curl_easy_init();
    FILE *fp = fopen("/tmp/plugin.so", "wb");

    curl_easy_setopt(curl, CURLOPT_URL, url);  // 用户可控 URL
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
    curl_easy_perform(curl);
    fclose(fp);

    // 直接加载，无验证
    void *handle = dlopen("/tmp/plugin.so", RTLD_LAZY);
    typedef void (*func_t)(void);
    func_t func = (func_t)dlsym(handle, "execute");
    func();  // RCE
}

// 危险示例 2: 环境变量驱动
const char *lib_url = getenv("PLUGIN_URL");  // 可被污染
curl_easy_setopt(curl, CURLOPT_URL, lib_url);

// 危险示例 3: 用户参数指定库
void load_plugin(int argc, char *argv[]) {
    char *plugin_url = argv[1];  // 无验证
    // 下载并加载...
}

// 危险示例 4: 配置文件驱动
config_t cfg;
const char *lib_url = config_get_string(cfg, "plugin.url");
// 加载 lib_url...
```

### 快速定位核心操作 (L2: 跳读)
- **HTTP 库**：`curl_easy_setopt()`, `libcurl`, `wget`
- **动态加载**：`dlopen()`, `dlsym()`（Linux）或 `LoadLibrary()`（Windows）
- **文件写入**：`fopen()`, `fwrite()`, `std::ofstream`
- **URL 来源**：命令行参数、环境变量、配置文件、网络请求
- **危险流**：URL 参数 → HTTP 下载 → 临时文件 → dlopen

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - 预定义的库 URL 列表
  - 哈希白名单（SHA256）
- **URL 验证**：
  - 协议限制：`strstr(url, "https://") == url`
  - 域名检查：解析 URL 并验证域名
- **完整性检查**：
  - 计算下载文件的 SHA256/SHA512
  - 与预期哈希比对
  - GPG 签名验证
- **文件权限检查**：
  - 验证文件所有者和权限（Linux `stat()`, `getuid()`）
  - ELF 头部验证（魔数 `0x7f 'E' 'L' 'F'`）
- **沙箱隔离**：
  - 使用 `RTLD_LOCAL` 限制符号作用域
  - `seccomp` 限制系统调用

---

## Classify

### 漏洞
- 用户可控的库 URL
- 无白名单或白名单可绕过
- 下载后直接 dlopen，无完整性验证
- 跨文件场景：A 模块下载，B 模块加载

### 误报
- 库 URL 来自硬编码或受保护的配置
- 严格的白名单或哈希验证
- 签名验证（GPG）
- 文件权限和所有者检查完整

### 代码异味
- 库 URL 部分可控但有验证
- 下载与加载分离，中间步骤可被篡改
- 使用弱验证如仅检查文件扩展名

---

## Low risk

- **硬编码 URL 和哈希**：库 URL 和 SHA256 哈希都被硬编码，无法加载不同版本
- **协议 + 域名限制**：仅允许 HTTPS 且仅限特定内部域名
- **GPG 签名验证**：库被 GPG 签名，加载前验证签名
- **权限检查**：ELF 文件头验证和权限检查完整
- **本地库**：库预装包内或从受信目录加载
- **ASLR + DEP**：系统启用 ASLR 和 DEP，降低利用难度

---

## 审计重点

1. 定位所有 dlopen 和 curl 调用
2. 追踪库 URL 来源（参数、环境变量、配置）
3. 检查下载过程中是否有完整性验证
4. 验证 ELF 文件头和文件权限检查
5. 测试 URL 绕过向量（编码、重定向）
6. 检查临时文件的创建和清理
