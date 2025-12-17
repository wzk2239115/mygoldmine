# Java 多行响应头解析未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `response.setHeader()` 或 `addHeader()` 传入包含 `
` 的值
- 从外部源读取头值未进行规范化
- CRLF 字符在头值中未被过滤或转义
- 多行头处理不遵循 RFC 7230

**快速定位核心操作：**
1. 搜索关键字：`
`、`
` 在头值中的使用
2. 追踪头值来源：外部 API、数据库、请求参数
3. 检查是否存在规范化处理
4. 追踪头值的转发和处理流程

**快速定位保护机制：**
- 规范化：`value.replaceAll("[\r\n]", "")`
- 验证：`if (value.contains("") || value.contains("
")) throw Exception()`
- RFC 合规：遵循 HTTP 头字段格式标准
- 框架防护：某些框架自动检测和拒绝

**代码示例：**
```java
// 危险：外部值直接设置为响应头
@GetMapping("/proxy")
public void proxy(HttpServletResponse response,
                  @RequestHeader String customHeader) {
    response.setHeader("X-Forwarded", customHeader);  // 危险：未规范化
}

// 危险：从 API 响应转发头
@GetMapping("/forward")
public void forward(HttpServletResponse response) throws IOException {
    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
    for (String key : conn.getHeaderFields().keySet()) {
        String value = conn.getHeaderField(key);
        response.setHeader(key, value);  // 危险：未规范化
    }
}

// 危险：数据库字段直接用于头
@GetMapping("/db-header")
public void dbHeader(HttpServletResponse response) {
    String headerValue = headerDao.findValue(id);
    response.setHeader("X-Custom", headerValue);  // 危险
}
```

## Classify

**漏洞（Medium）：**
- 外部源的值包含 `
` 未被规范化
- 多行值导致响应分割
- 框架未自动检测

**误报：**
- 头值硬编码
- 框架已自动规范化
- 官方 API 已处理

**代码异味（Medium）：**
- 外部来源未验证
- 仅过滤部分字符
- 间接流程

## Low risk

**以下情况评为低风险：**
- 头值硬编码
- 明确过滤 CRLF
- 框架已验证
- 内部系统来源且已验证
