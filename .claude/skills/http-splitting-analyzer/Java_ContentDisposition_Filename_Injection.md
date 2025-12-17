# Java Content-Disposition 文件名注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `response.setHeader("Content-Disposition", value)` 直接设置
- `response.addHeader("Content-Disposition", value)`
- `FileDownloadUtil.setFilename()` 等工具类
- 文件名直接拼接：`"attachment; filename=" + filename`

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`filename=`、`attachment`
2. 追踪文件名来源：`getParameter()`、数据库、上传文件名
3. 检查是否使用双引号包装
4. 查看是否过滤特殊字符

**快速定位保护机制：**
- 特殊字符过滤：移除 `;`、`,`、``、`
`
- 双引号转义：`"` → `"`
- 白名单验证：正则表达式检查
- RFC 5987 编码：使用标准编码方式

**代码示例：**
```java
// 危险：用户文件名直接用于下载
@GetMapping("/download")
public void download(HttpServletResponse response,
                     @RequestParam String file) throws IOException {
    response.setHeader("Content-Disposition",
        "attachment; filename=" + file);  // 危险
    // 读取文件
}

// 危险：URL 参数直接使用
@PostMapping("/export")
public void export(HttpServletResponse response,
                   @RequestParam String name) {
    String header = "attachment; filename=" + name;
    response.setHeader("Content-Disposition", header);  // 危险
}

// 危险：数据库字段未验证
@GetMapping("/file/{id}")
public void getFile(HttpServletResponse response, @PathVariable int id) {
    File file = fileDao.findById(id);
    response.setHeader("Content-Disposition",
        "attachment; filename=" + file.getOriginalName());  // 危险
}
```

## Classify

**漏洞（High）：**
- 用户提供的文件名未验证
- 文件名包含特殊字符导致头分割
- 允许目录遍历

**误报：**
- 文件名系统生成
- 经过白名单验证
- 使用安全 API

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接来源

## Low risk

**以下情况评为低风险：**
- 文件名硬编码
- 严格白名单验证
- 使用框架安全方法
- RFC 合规编码

## 审计专业技巧

### 1. 真实漏洞的特征识别

**头分割型漏洞（HTTP Response Splitting）：**
```java
// 真实漏洞：CRLF字符未过滤导致头分割
String filename = request.getParameter("name");  // 可控输入
response.setHeader("Content-Disposition", "attachment; filename=" + filename);
// 攻击：name=test.pdf%0d%0aSet-Cookie:admin=true
// 结果：注入任意HTTP头
```

**目录遍历漏洞：**
```java
// 真实漏洞：路径符号未限制
String file = request.getParameter("file");
File downloadFile = new File("/downloads/" + file);  // 可能：../../config/database.properties
```

**文件名编码注入：**
```java
// 真实漏洞：仅转义部分字符，遗漏CRLF
String filtered = filename.replace("\"", "\\\"");  // 只转义双引号
// 攻击：name=test.pdf%0d%0aX-Injected-Header: value
// 结果：%0d%0a未被处理，仍可注入
```

### 2. 常见误报场景

**场景1：数据库字段已审核**
```java
// 容易被误判为漏洞，但实际安全：
@GetMapping("/download/{id}")
public void download(HttpServletResponse response, @PathVariable Long id) {
    Document doc = documentDao.findById(id);  // 来自数据库
    String filename = doc.getFilename();  // 数据库字段由管理员上传，已审核
    response.setHeader("Content-Disposition",
        "attachment; filename=" + filename);
}
// 误报原因：来源是数据库，不是用户直接输入
```

**场景2：系统自动生成的文件名**
```java
// 容易误报，但实际安全：
LocalDateTime now = LocalDateTime.now();
String filename = "report_" +
    DateTimeFormatter.ofPattern("yyyy-MM-dd_HHmmss").format(now) + ".xlsx";
response.setHeader("Content-Disposition",
    "attachment; filename=" + filename);
// 误报原因：格式完全由系统生成，无用户可控部分
```

**场景3：URI路径参数带有校验**
```java
// 容易误报，但若有完整校验则安全：
@GetMapping("/file/{uuid}")
public void getFile(@PathVariable String uuid, HttpServletResponse response) {
    // UUID格式严格校验（128位16进制数字）
    if (!uuid.matches("[a-f0-9\\-]{36}")) {
        throw new BadRequestException("Invalid UUID");
    }
    File file = new File("/safe/uploads/" + uuid);  // UUID无特殊字符，安全
    response.setHeader("Content-Disposition",
        "attachment; filename=" + file.getName());
}
// 误报原因：输入被强制转换为安全格式
```

### 3. 区分真实漏洞 vs 误报的审计检查清单

| 检查项 | 真实漏洞 | 误报信号 |
|-----|--------|--------|
| **输入来源** | 用户参数、表单、URL | 常量、数据库、系统生成 |
| **传入点** | `getParameter()`、`getHeader()` | 配置文件、常量定义 |
| **过滤机制** | 无、不完整、黑名单 | 白名单、UUID校验、正则匹配 |
| **编码方式** | 直接拼接 | RFC 5987编码、URLEncoder |
| **信任边界** | 跨越信任边界 | 在信任边界内 |
| **字符集限制** | 无限制（含CRLF） | 字母数字、下划线、点、横线 |

### 4. 深度审计技巧

**技巧1：追踪文件名的完整链路**
```
检查流程：
1. 入口点：@RequestParam 或 @PathVariable
2. 传递过程：是否经过任何过滤？
   - StringUtils.trim()（不安全）
   - replaceAll()（需检查表达式）
   - Apache Commons Lang（需检查具体方法）
3. 最终使用：setHeader() 前是否最后一次校验？
4. 双引号处理：是否包装在双引号内？
```

**技巧2：识别不完整的过滤**
```java
// 常见陷阱1：仅过滤部分字符
String safe = filename.replace("/", "").replace("\\", "");
// 漏洞：未过滤 CRLF (%0d%0a)、分号等

// 常见陷阱2：黑名单遗漏
String[] blacklist = {";", ","};
for (String char : blacklist) {
    filename = filename.replace(char, "");
}
// 漏洞：遗漏 \r、\n、空格等特殊字符

// 常见陷阱3：转义不完整
String escaped = filename.replace("\"", "\\\"");
// 漏洞：仅转义双引号，CRLF仍可被利用

// 正确方式：白名单 + RFC 5987
if (!filename.matches("^[a-zA-Z0-9._\\-]+$")) {
    throw new IllegalArgumentException("Invalid filename");
}
// 或使用标准库
String encoded = URLEncoder.encode(filename, "UTF-8");
response.setHeader("Content-Disposition",
    "attachment; filename*=UTF-8''" + encoded);
```

**技巧3：识别隐藏的用户输入**
```java
// 隐蔽漏洞：文件名来自数据库，但数据库由用户控制
@PostMapping("/upload")
public String upload(MultipartFile file) {
    String uploadedName = file.getOriginalFilename();  // 用户上传时的文件名
    fileDao.save(new FileEntity(uploadedName));  // 保存到数据库
    return "success";
}

@GetMapping("/download/{id}")
public void download(@PathVariable Long id, HttpServletResponse response) {
    FileEntity entity = fileDao.findById(id);
    response.setHeader("Content-Disposition",
        "attachment; filename=" + entity.getName());  // 危险！来自用户上传的文件名
}
// 审计要点：追踪数据来源，即使是数据库也要检查初始输入
```

**技巧4：识别绕过编码的攻击**
```java
// 双编码绕过：
String filename = URLDecoder.decode(request.getParameter("name"));
// 如果只URLEncode一次，可以用 %252F 绕过

// Unicode编码绕过：
// 某些框架可能不处理 \u000d\u000a 形式的CRLF

// 多重编码：
// Base64编码的CRLF可能被某些过滤器遗漏
```

### 5. 实战检查模板

```
审计步骤：
□ 步骤1：定位所有 Content-Disposition 设置位置
  grep -r "Content-Disposition" --include="*.java"

□ 步骤2：检查每个位置的文件名来源
  - 用户参数？@RequestParam @RequestBody
  - 上传文件？MultipartFile.getOriginalFilename()
  - URL路径？@PathVariable

□ 步骤3：检查过滤逻辑
  - 有过滤吗？
  - 是白名单还是黑名单？
  - 黑名单是否包含 %0d、%0a、\r、\n？

□ 步骤4：检查编码方式
  - 是否使用 RFC 5987 编码？
  - 是否使用 URLEncoder？
  - 是否手工转义？转义是否完整？

□ 步骤5：检查双引号包装
  - filename 是否被包装在双引号内？
  - 双引号内的引号是否转义？

□ 步骤6：测试验证
  - 尝试注入：filename=test.pdf%0d%0aX-Injected-Header:value
  - 尝试目录遍历：filename=../../../etc/passwd
  - 尝试双编码：filename=%252e%252e%252fetc%252fpasswd
```
