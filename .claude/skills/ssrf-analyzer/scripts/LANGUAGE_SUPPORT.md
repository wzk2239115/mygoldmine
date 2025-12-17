# SSRF Sink Detector - Language Support

## 支持的编程语言

本工具支持以下 **9 种编程语言**的 SSRF 漏洞检测：

### 1. PHP

**文件扩展名**: `.php`

**检测的 Sinks**:
- `file_get_contents()` - 读取远程文件
- `fopen()` - 打开远程文件
- `readfile()` - 读取并输出文件
- `curl_exec()` - 执行 CURL 请求
- `curl_multi_exec()` - 批量 CURL 请求
- `fsockopen()` - 打开 Socket 连接
- `pfsockopen()` - 持久 Socket 连接

**示例**:
```php
$url = $_GET['url'];
$content = file_get_contents($url);  // VULNERABLE
```

---

### 2. Python

**文件扩展名**: `.py`

**检测的 Sinks**:
- `requests.get/post/put/delete/patch/request()` - HTTP 请求
- `urllib.urlopen()` - URL 打开
- `urllib.urlretrieve()` - URL 下载
- `HTTPConnection/HTTPSConnection()` - HTTP 连接
- `socket` - Socket 操作

**示例**:
```python
import requests
url = input("Enter URL: ")
response = requests.get(url)  # VULNERABLE
```

---

### 3. Java

**文件扩展名**: `.java`

**检测的 Sinks**:
- `URL.openConnection()` - 打开 URL 连接
- `URL.openStream()` - 打开 URL 流
- `URLConnection.getInputStream()` - 获取输入流
- `RestTemplate.exchange/getForObject/getForEntity/postForObject()` - REST 请求
- `OkHttpClient.newCall/execute()` - OkHttp 请求
- `HttpClient.send/execute()` - HTTP 客户端请求

**示例**:
```java
URL url = new URL(userInput);
URLConnection conn = url.openConnection();  // VULNERABLE
```

---

### 4. JavaScript

**文件扩展名**: `.js`, `.jsx`, `.mjs`

**检测的 Sinks**:
- `http.request/get()` - Node.js HTTP 请求
- `https.request/get()` - Node.js HTTPS 请求
- `axios.get/post/put/delete/patch/request()` - Axios HTTP 请求
- `fetch()` - 浏览器/Node.js 原生 Fetch
- `XMLHttpRequest` - XHR 请求
- `got.get/post/put/delete/patch/stream()` - Got HTTP 客户端
- `superagent.end/pipe()` - Superagent 请求

**示例**:
```javascript
const url = req.query.url;
fetch(url)  // VULNERABLE
```

---

### 5. TypeScript

**文件扩展名**: `.ts`, `.tsx`

**检测的 Sinks**:
- 与 JavaScript 相同的所有 Sinks
- http/https 模块
- axios 库
- fetch 函数
- XMLHttpRequest

**示例**:
```typescript
async function fetchData(userUrl: string) {
  const response = await fetch(userUrl);  // VULNERABLE
}
```

---

### 6. C

**文件扩展名**: `.c`, `.h`

**检测的 Sinks**:
- `curl_easy_perform()` - CURL 执行
- `curl_easy_init()` - CURL 初始化
- `socket()` - 创建 Socket
- `connect()` - 连接
- `getaddrinfo()` - 获取地址信息
- `gethostbyname()` - DNS 查询
- `inet_addr()` - IP 地址转换
- `fopen()` - 打开文件

**示例**:
```c
CURL *curl = curl_easy_init();
curl_easy_perform(curl);  // VULNERABLE
```

---

### 7. C++

**文件扩展名**: `.cc`, `.cpp`, `.cxx`, `.hpp`, `.h`

**检测的 Sinks**:
- `curl_easy_perform()` - CURL 执行
- `std::ifstream/std::ofstream/std::fstream()` - 文件流
- `socket()` - 创建 Socket
- `connect()` - 连接
- `getaddrinfo()` - 获取地址信息
- `gethostbyname()` - DNS 查询
- ASIO 库相关操作

**示例**:
```cpp
std::ifstream file(userPath);  // VULNERABLE
std::string content((std::istreambuf_iterator<char>(file)),
                    std::istreambuf_iterator<char>());
```

---

### 8. Go

**文件扩展名**: `.go`

**检测的 Sinks**:
- `http.Get/Post/Put/Delete/Head/Do()` - HTTP 请求
- `net.Dial/DialTCP/DialUDP/DialUnix()` - 网络连接
- `net.Listen()` - 监听端口
- `net.LookupIP/LookupHost/LookupAddr/LookupCNAME/LookupSRV/LookupMX()` - DNS 查询
- `url.Parse()` - URL 解析

**示例**:
```go
resp, err := http.Get(userURL)  // VULNERABLE
```

---

### 9. Rust

**文件扩展名**: `.rs`

**检测的 Sinks**:
- `reqwest::Client` - HTTP 客户端
- `reqwest.get/post/put/delete/patch/head()` - HTTP 请求
- `hyper::client::Client` - Hyper 客户端
- `http::Request` - HTTP 请求对象
- `tokio::net::TcpStream` - 异步 TCP 连接
- `std::net::TcpStream` - 同步 TCP 连接
- `std::net::UdpSocket` - UDP Socket

**示例**:
```rust
let client = reqwest::Client::new();
let response = client.get(user_url).send().await;  // VULNERABLE
```

---

## 使用示例

### 扫描特定语言

```bash
# 扫描 PHP 代码
bash scan.sh --lang php /path/to/php/code

# 扫描 Go 项目
bash scan.sh --lang go /path/to/go/project

# 扫描 Rust 代码
bash scan.sh --lang rust /path/to/rust/src
```

### 扫描多种语言

```bash
# 扫描所有支持的语言
bash scan.sh --all /path/to/mixed/project

# 扫描 TypeScript 和 JavaScript
bash scan.sh /path/to/node/project
```

### 生成报告

```bash
# JSON 格式报告
python3 cli.py --lang python --output json /path/to/python

# SARIF 格式报告（用于 IDE 集成）
python3 cli.py --lang go --output sarif /path/to/go

# 同时输出多种格式
python3 cli.py --all --output both \
  --json-out report.json \
  --sarif-out report.sarif \
  /path/to/code
```

---

## 扩展支持新语言

要添加新语言支持，请按以下步骤操作：

1. **更新配置** (`config/languages.yaml`):
```yaml
newlang:
  extensions:
    - .nl
  tree_sitter_module: tree_sitter_newlang
  priority: 10
  sink_query_file: languages/newlang/queries/sinks.scm
```

2. **创建查询文件** (`languages/newlang/queries/sinks.scm`):
```scm
;; NewLang SSRF Sink Detection
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(dangerous_func1|dangerous_func2)$")
)
```

3. **更新 scanner.py** - 在 `sinks_by_lang` 字典中添加新语言

4. **更新 cli.py** - 在 `--lang` 选项中添加新语言

5. **测试** - 创建测试样例验证检测功能

---

## 技术细节

### 检测方法

- **行基扫描**: 简单高效的基于行的搜索
- **Pattern matching**: 支持精确函数名匹配
- **Comment filtering**: 忽略注释行中的检测

### Sink 分类

所有检测到的 Sinks 都被标记为 `high` 严重等级，因为：
- 它们直接进行网络或文件操作
- 用户输入可能直接到达这些调用
- 需要进一步的数据流分析来判断是否真正有漏洞

---

## 统计信息

| 语言 | 支持扩展名 | 检测 Sinks 数 | Parser 状态 |
|------|----------|-----------|-----------|
| PHP | 1 | 7+ | ✅ 支持 |
| Python | 1 | 10+ | ✅ 支持 |
| Java | 1 | 10+ | ✅ 支持 |
| JavaScript | 3 | 10+ | ✅ 支持 |
| TypeScript | 2 | 10+ | ✅ 支持 |
| C | 2 | 8+ | ⚠️ 可选 |
| C++ | 5 | 8+ | ⚠️ 可选 |
| Go | 1 | 10+ | ⚠️ 可选 |
| Rust | 1 | 10+ | ⚠️ 可选 |

**✅ 支持** = 已安装并测试
**⚠️ 可选** = 可用，但需安装相应 tree-sitter 模块

---

## 已知限制

1. **数据流分析**: 不追踪变量赋值和传播
2. **上下文敏感**: 不分析代码上下文
3. **False Positives**: 可能报告安全代码
4. **False Negatives**: 可能遗漏某些变体
5. **Parser 依赖**: 某些语言需要额外安装

---

## 许可证

MIT License
