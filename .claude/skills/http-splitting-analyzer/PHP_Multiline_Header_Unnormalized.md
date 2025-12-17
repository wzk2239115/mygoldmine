# PHP 多行响应头未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `header()` 传入包含 `
` 的值
- 从外部源读取头值未规范化
- 响应头转发时未过滤

**快速定位核心操作：**
1. 搜索关键字：`header(`、`
` 在值中
2. 追踪头值来源：外部 API、数据库、请求头
3. 检查是否存在规范化
4. 追踪头值转发流程

**快速定位保护机制：**
- 规范化：`$value = str_replace(["", "
"], "", $value)`
- 验证：`if (strpos($value, "") !== false || strpos($value, "
") !== false)`
- 框架防护：某些框架自动检测

**代码示例：**
```php
// 危险：外部值直接设置为响应头
$custom = $_SERVER['HTTP_X_CUSTOM'] ?? '';
header("X-Forwarded: " . $custom);  // 危险

// 危险：API 响应转发
$api_header = curl_getinfo($handle, CURLINFO_HEADER_OUT);
header($api_header);  // 危险

// 危险：数据库字段
$header_val = $db->getValue('headers', 'value', ['id' => $id]);
header("X-Custom: " . $header_val);  // 危险
```

## Classify

**漏洞（Medium）：**
- 外部值包含 `
` 未规范化
- 导致响应分割
- 框架未自动检测

**误报：**
- 头值硬编码
- 框架已规范化

**代码异味（Medium）：**
- 外部来源未验证
- 仅过滤部分字符
- 间接流程

## Low risk

**以下情况评为低风险：**
- 头值硬编码
- 明确过滤 CRLF
- 框架已验证
- 内部来源且已验证

## 审计专业技巧

### 1. 头值来源追踪方法论

**第一步：来源识别关键字列表**
```
外部源标记符：
- $_GET, $_POST, $_REQUEST, $_COOKIE
- $_SERVER['HTTP_*']
- file_get_contents('php://input')
- curl_exec(), file_get_contents($url)
- $mysqli->query(), $db->fetch()
- json_decode($data)
```

**第二步：追踪数据流**
- 从 `header()` 调用处反向追踪头值变量
- 标记所有中间赋值和转换操作
- 检查是否存在隐式类型转换（如 `(string)$value`）

**第三步：规范化检查清单**
```php
// 检查这些过滤方式
strval($header)           // 不过滤 CRLF
strip_tags($header)       // 不过滤 CRLF
htmlspecialchars($header) // 不过滤 CRLF
trim($header)             // 不过滤 CRLF
preg_replace('/[^a-z]/') // 根据情况判断
```

### 2. 真实漏洞特征签名

**特征一：框架检测绕过**
```php
// Symfony/Laravel 框架会检测 \r\n
// 但开发者自定义 header() 可能绕过
class CustomHeaderHandler {
    public function setHeader($name, $value) {
        header($name . ": " . $value);  // 绕过框架检测
    }
}

// 风险等级：HIGH
// 原因：框架检测在顶层，但自定义处理器直接调用原生 header()
```

**特征二：二次编码漏洞**
```php
// 攻击者输入：X-Custom: value\r\n\r\nSet-Cookie: admin=1
$value = rawurldecode($_GET['custom']);  // 解码
header("X-Custom: " . $value);           // 直接传入

// 漏洞原因：URL 解码后包含 CRLF
// 真实案例：某电商网站日志系统，日志字段未规范化
```

**特征三：多层转发链**
```php
// 跨服务转发未规范化
$api_response = curl_exec($handle);
foreach (explode("\n", $api_response) as $header) {
    header($header);  // 直接转发原始响应头
}

// 风险：如果上游 API 被污染或信任链断裂
```

### 3. 误报识别经验

**误报案例一：框架自动检测**
```php
// Laravel 中
Route::get('/test', function() {
    header("X-Custom: " . request('value'));
});

// 分析：
// - Laravel 的 middleware 会检测响应头中的 CRLF
// - Response::header() 方法自动过滤
// - 但原生 header() 不过滤
// - 判断：需要查看是否真的调用原生 header()
```

**误报案例二：格式验证**
```php
// API 返回的头值已验证为格式
$bearer_token = $_GET['token'];  // 值格式必须 ^[A-Za-z0-9-_.]+$

if (!preg_match('/^[A-Za-z0-9-_.]+$/', $bearer_token)) {
    http_response_code(400);
    exit('Invalid token');
}
header("Authorization: Bearer " . $bearer_token);

// 分析：
// - 严格的白名单验证排除了 CRLF
// - 判定为不是漏洞（False Positive）
```

**误报案例三：隐含的框架防护**
```php
// 某些框架在启动时自动检测
class Application {
    public function send_headers($headers) {
        foreach ($headers as $key => $value) {
            // 框架在此检测 CRLF
            if (strpos($value, "\r") !== false || strpos($value, "\n") !== false) {
                throw new InvalidHeaderException();
            }
            header($key . ": " . $value);
        }
    }
}

// 分析：虽然代码看起来危险，但框架已防护
```

### 4. 高级检测技巧

**技巧一：追踪间接赋值**
```php
// 危险的间接赋值模式
$headers = array();
$headers['custom'] = $_GET['value'];  // 间接来源
$h = $headers['custom'];
header("X-Custom: " . $h);            // 间接漏洞

// 审计建议：追踪数组变量的所有赋值点
```

**技巧二：识别分支覆盖**
```php
// 某些分支可能过滤，某些不过滤
if (DEBUG_MODE) {
    header("X-Debug: " . $_GET['debug']);  // 只在调试模式，真实漏洞
} else {
    $clean = sanitize($_GET['debug']);
    header("X-Debug: " . $clean);
}

// 审计建议：检查所有可能的执行路径
```

**技巧三：序列化与反序列化陷阱**
```php
// 数据库存储被序列化的头值
$header = unserialize($db_value);  // $header = "X-Custom: test\r\n\r\n"
header($header);                    // 漏洞

// 审计建议：追踪反序列化的数据源
```

### 5. 真实案例与识别

**案例一：电商网站日志污染（真实）**
```
漏洞原因：用户搜索关键词未规范化，直接存入数据库
$search = $_GET['q'];
$db->log("search", $search);  // 存储带 CRLF 的搜索词
$keyword = $db->getLastSearch();
header("X-Last-Search: " . $keyword);  // 读取时注入

识别特征：
✓ 两步操作（存储 + 读取）
✓ 中间环节假设信任（数据库内容）
✓ 没有规范化验证

严重程度：MEDIUM（需要管理员访问日志）
```

**案例二：API Gateway 头转发（真实）**
```
漏洞原因：直接转发上游服务头，未验证
function proxy_request($upstream_url) {
    $response = curl_exec($upstream_url);
    $headers = curl_getinfo($ch, CURLINFO_HEADER_OUT);

    foreach ($headers as $h) {
        header($h);  // 直接转发，可被投毒
    }
}

识别特征：
✓ 直接转发外部响应
✓ 无验证过程
✓ 信任链中断

严重程度：HIGH（直接污染）
```

### 6. 检测工具链使用建议

**Step 1：静态扫描筛选**
```bash
# 粗筛：找出所有 header() 调用
grep -r "header(" --include="*.php"

# 精筛：筛选可能的动态值
grep -r "header.*\$" --include="*.php"
```

**Step 2：数据流分析**
- 使用 IDE 的"查找所有引用"功能
- 追踪赋值链上的所有变量
- 检查每个变量的约束条件

**Step 3：上下文验证**
- 检查变量初始化前是否有验证
- 检查框架级别的防护
- 确认规范化函数的完整性

### 7. 常见误诊原因

| 误诊类型 | 原因 | 避免方法 |
|---------|------|---------|
| 过度报告 | 未检查框架防护 | 学习框架源码的防护位置 |
| 漏报 | 间接赋值追踪不完整 | 使用静态分析工具辅助 |
| 错误分级 | 未区分输入源 | 区分直接/间接/转发链 |
| 伪阴性 | 忽视序列化数据 | 检查所有数据库读取操作 |
