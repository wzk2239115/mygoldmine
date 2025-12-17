# PHP Content-Disposition 文件名注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `header("Content-Disposition: attachment; filename=" . $name)` 直接设置
- 用户上传的文件名直接使用
- 数据库查询返回的文件名未验证

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`filename=`、`attachment`
2. 追踪文件名来源：`$_GET`、`$_POST`、`$_FILES`、数据库
3. 检查是否使用双引号包装
4. 查看是否过滤特殊字符

**快速定位保护机制：**
- 特殊字符过滤：`str_replace([";", ",", "", "
"], "", $name)`
- 双引号转义：`str_replace('"', '\"', $name)`
- 白名单验证：`preg_match('/^[a-zA-Z0-9\-_.]+$/', $name)`
- RFC 编码：使用 RFC 5987 格式

**代码示例：**
```php
// 危险：用户文件名直接用于下载
$file = $_GET['file'] ?? '';
header("Content-Disposition: attachment; filename=" . $file);  // 危险

// 危险：POST 文件名
$export_name = $_POST['name'] ?? 'export';
header("Content-Disposition: attachment; filename=" . $export_name);  // 危险

// 危险：数据库字段
$name = $db->query("SELECT name FROM files WHERE id=" . $id)[0];
header("Content-Disposition: attachment; filename=" . $name);  // 危险
```

## Classify

**漏洞（High）：**
- 用户文件名未验证
- 文件名包含特殊字符导致头分割
- 允许目录遍历

**误报：**
- 文件名系统生成
- 经过白名单验证
- 使用安全方法

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接来源

## Low risk

**以下情况评为低风险：**
- 文件名硬编码
- 严格白名单验证
- RFC 合规编码
- 内部来源且已验证

## 审计专业技巧

### 1. 真实漏洞特征识别

**关键红旗：**
- 用户输入**直接无转义**拼接到 `header()` 的值中
- 使用**双引号分隔符**却未转义内部引号：`header("Content-Disposition: attachment; filename=\"$var\"")`
- **换行符 `\r\n`** 未过滤，可进行 CRLF 注入
- 文件名来自 **`$_GET`、`$_POST`、`$_FILES['name']`** 等直接用户输入
- 数据库内容**用户可控制**（如评论、自定义字段）

**审计思路（3层检查）：**

1. **信息来源审查**
   - 追踪变量来源：`strpos(file_get_contents($path), '$_GET')` 检查原始输入
   - 检查中间传递是否有过滤：参数 → 函数参数 → header
   - 数据库数据是否来自用户：`INSERT INTO ... VALUES($_POST)`

2. **编码方式审查**
   - 是否使用 RFC 5987 编码（`filename*=UTF-8''...`）
   - 是否使用 `rawurlencode()` 或 URL 编码
   - 是否仅用 `basename()` 而未验证

3. **特殊字符处理审查**
   - 检查 `\r`、`\n`、`\r\n` 是否被过滤
   - 检查引号 `"` 和 `'` 是否转义
   - 检查分号 `;` 是否过滤（分隔符）
   - 检查 `=` 是否过滤（参数分隔符）

### 2. 真实漏洞 vs 误报的区分经验

**真实漏洞示例：**
```php
// 案例 1：经典直接注入 - 高危
$filename = $_GET['file'];  // 无任何处理
header("Content-Disposition: attachment; filename=" . $filename);

// 测试：file=test.txt%0d%0aContent-Type:text/html
// 结果：成功注入新的 HTTP 头
```

```php
// 案例 2：双引号包装但未转义 - 高危
$filename = $_GET['download_name'];
header("Content-Disposition: attachment; filename=\"$filename\"");

// 测试：download_name=test".php  或  download_name=test%22.php
// 结果：字符串提前结束，可突破双引号限制
```

```php
// 案例 3：仅过滤部分字符 - 中危
$filename = str_replace([';', ','], '', $_GET['file']);
header("Content-Disposition: attachment; filename=" . $filename);

// 测试：使用 %0d%0a（CRLF）绕过
// 结果：分号、逗号被过滤，但 CRLF 未过滤
```

**常见误报案例：**
```php
// 误报 1：使用 basename() - 安全
$filename = basename($_GET['file']);
header("Content-Disposition: attachment; filename=" . $filename);
// basename() 去除路径，虽然 CRLF 需要关注，但整体风险低

// 误报 2：严格白名单 - 安全
if (preg_match('/^[a-zA-Z0-9._-]+$/', $_GET['file'])) {
    header("Content-Disposition: attachment; filename=" . $_GET['file']);
} else {
    exit("Invalid filename");
}
// 白名单验证会拒绝特殊字符，安全

// 误报 3：RFC 5987 编码 - 安全
$filename = $_GET['file'];
$encoded = rawurlencode($filename);
header("Content-Disposition: attachment; filename*=UTF-8''" . $encoded);
// rawurlencode 进行了正确编码，%0d%0a 无法注入

// 误报 4：系统生成 - 安全
$timestamp = time();
$filename = "export_" . $timestamp . ".csv";
header("Content-Disposition: attachment; filename=" . $filename);
// 完全由系统生成，无用户输入
```

### 3. 审计检查清单

**快速判定步骤：**

| 检查项 | 判定逻辑 | 优先级 |
|--------|---------|--------|
| 用户输入？ | 来自 `$_GET/$_POST/$_FILES` 等直接用户输入 | P0 |
| 无任何过滤？ | 直接拼接到 `header()` 值 | P0 |
| 未转义特殊字符？ | 未处理 `\r\n` 或 `"` | P0 |
| 黑名单过滤？ | 使用 `str_replace` 部分字符 | P1 |
| 有白名单？ | 使用 `preg_match` 限制字符集 | 低风险 |
| RFC 编码？ | 使用 `rawurlencode` 或 `urlencode` | 低风险 |
| 来源验证？ | 数据库来源但用户无法修改 | 低风险 |

### 4. 实战审计技巧

**文件搜索策略：**
```bash
# 搜索所有 Content-Disposition 使用
grep -rn "Content-Disposition" .

# 搜索 filename 相关赋值
grep -rn "filename\s*=" .

# 追踪 GET/POST 变量到 header 的调用链
grep -rn "\$_GET\|\$_POST" . | grep -v "isset\|empty"

# 检查是否有转义函数
grep -rn "rawurlencode\|urlencode\|addslashes\|htmlspecialchars" .
```

**危险模式识别：**
- 参数 → 变量 → `header()` 的一条链（无中间处理）
- 循环拼接文件名：`for` 循环中处理用户输入
- 条件判断缺失：`if` 没有白名单检查就直接 `header()`

**环境特殊考量：**
- PHP 版本：`php.ini` 的 `auto_prepend_file` 可能隐藏过滤
- 框架框架：Laravel、Symfony 等框架可能有全局过滤
- Web 服务器：Nginx 对某些特殊字符的处理与 Apache 不同
