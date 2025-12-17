# PHP - DOMXPath 字符串直接拼接

## Details

### 漏洞成因
PHP 的 `DOMXPath` 类用于对 `DOMDocument` 对象执行 XPath 查询。其 `query()` 和 `evaluate()` 方法接收 XPath 表达式字符串。当用户输入通过字符串拼接（`.`, `sprintf()`, 字符串插值）直接嵌入表达式时，攻击者可注入 XPath 语法字符（如 `'`, `"`, `or`, `//`）来改变查询逻辑，导致身份验证绕过、数据泄露或未授权访问。常见于 XML 数据库查询和 SOAP 服务处理。

代码示例：
```php
$username = $_GET['username'];
$password = $_GET['password'];

$dom = new DOMDocument();
$dom->load('users.xml');
$xpath = new DOMXPath($dom);

$query = "//user[username='$username' and password='$password']";
$result = $xpath->query($query);

if ($result->length > 0) {
    echo "Login success";
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `new DOMXPath()`, `DOMXPath`, `->query()`, `->evaluate()`
- `new DOMDocument()`, `->load()`, `->loadXML()`
- 字符串拼接：`.`, `sprintf()`, `"{$var}"`, `"$var"`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`
- 数据源：`$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`

### 快速定位保护机制 (L2-L4)
- **参数化查询** (L2 跳读) - DOMXPath 不原生支持参数化，检查是否有自定义封装
- **输入验证** (L2 跳读) - 查找 `filter_var()`, `preg_match()`, `ctype_alnum()` 等验证函数
- **转义函数** (L3 逐行读) - 检查自定义 `escapeXPath()` 函数，验证是否转义 `'`, `"`, `\`
- **框架验证** (L3 逐行读) - 检查是否使用框架的验证机制（如 Laravel Validator）
- **数据流追踪** (L4 跨模块) - 从 `$_GET/$_POST` 到 XPath 查询的完整路径，检查中间处理层

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据（`$_GET`, `$_POST` 等）通过字符串拼接直接嵌入 XPath 表达式
2. 未使用有效的输入验证或转义机制
3. 表达式通过 `->query()` 或 `->evaluate()` 执行
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、配置）

**误报情况**：
- 拼接的数据来自服务器端常量或配置文件
- 用户输入经过严格白名单验证（如 `ctype_alnum()` 或正则 `/^[a-zA-Z0-9]+$/`）
- XPath 表达式结构固定，用户输入仅影响数值型参数
- XML 数据源为公开的静态内容，无敏感信息

**代码异味**：
- 存在自定义转义函数但未覆盖所有 XPath 特殊字符
- 使用 `htmlspecialchars()` 或 `htmlentities()` 进行转义（不适用于 XPath）
- 使用黑名单过滤而非白名单验证
- 输入验证逻辑分散在多个文件或函数中

## Low risk

### 低风险评级场景

1. **强类型验证** - 用户输入经过 `intval()`, `floatval()` 强制转换为数值
   - 例：`$id = intval($_GET['id']); $query = "//item[@id=$id]";`

2. **严格白名单** - 输入限制为预定义的枚举值
   - 例：`$allowed = ['name', 'email']; if (!in_array($field, $allowed)) exit;`

3. **完整转义** - 使用经过验证的 XPath 转义库或函数
   - 例：自定义函数转义 `'`, `"`, `\`, `[`, `]` 等所有特殊字符

4. **非敏感数据** - XML 数据仅包含公开的产品目录或静态配置

5. **只读查询** - XPath 仅用于数据检索，不涉及身份验证或授权判断

6. **内部工具** - 代码运行在内部管理系统，仅管理员可访问

7. **结果过滤** - 查询结果经过额外的权限检查或数据脱敏

8. **长度限制** - 输入长度严格限制（如 `substr($input, 0, 10)`），降低攻击面
