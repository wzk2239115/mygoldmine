# PHP - SimpleXMLElement XPath 注入

## Details

### 漏洞成因
PHP 的 `SimpleXMLElement` 类提供简单的 XML 处理接口，其 `xpath()` 方法接收 XPath 表达式字符串进行节点查询。当用户输入通过字符串拼接或字符串插值（`"$var"`, `"{$var}"`）直接嵌入表达式时，攻击者可注入 XPath 语法元素来改变查询逻辑。由于 SimpleXML 的简洁性，开发者容易忽视安全验证，导致漏洞频发。常见于 RSS 解析、配置文件处理和简单的 XML 数据查询。

代码示例：
```php
$category = $_GET['category'];
$xml = simplexml_load_file('products.xml');

$query = "//product[@category='$category']";
$results = $xml->xpath($query);

foreach ($results as $product) {
    echo $product->name . "<br>";
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `simplexml_load_file()`, `simplexml_load_string()`, `new SimpleXMLElement()`
- `->xpath()` 方法调用
- 字符串拼接：`.`, `sprintf()`, `"$var"`, `"{$var}"`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`, `not()`
- 数据源：`$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`, `$_SERVER`

### 快速定位保护机制 (L2-L4)
- **输入验证** (L2 跳读) - 查找 `filter_input()`, `filter_var()`, `preg_match()`, `ctype_*()` 函数
- **白名单检查** (L2 跳读) - 检查 `in_array()`, `array_key_exists()` 等枚举值验证
- **转义函数** (L3 逐行读) - 检查自定义 `escapeXPath()` 或 `sanitize()` 函数的实现
- **框架层验证** (L3 逐行读) - 检查是否使用框架的验证机制（如表单验证类）
- **跨文件追踪** (L4) - 从请求入口到 XPath 查询的完整数据流，检查中间处理函数

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据通过字符串拼接直接嵌入 SimpleXML 的 `xpath()` 方法
2. 未实施有效的输入验证、转义或参数化机制
3. XPath 查询的 XML 数据包含敏感信息（用户数据、配置、权限）
4. 输入可以包含 XPath 特殊字符（`'`, `"`, `[`, `]`, `//`）

**误报情况**：
- 拼接的数据来自服务器端硬编码常量或配置
- 用户输入经过严格白名单验证（如 `ctype_alnum()` 返回 true）
- XPath 表达式结构固定，用户输入仅为数值型参数且经过类型转换
- XML 数据为公开的 RSS 源或产品目录，无敏感内容

**代码异味**：
- 使用 `addslashes()` 或 `mysqli_real_escape_string()` 进行转义（不适用于 XPath）
- 自定义转义函数但未处理所有 XPath 特殊字符（遗漏 `[`, `]`, `@`, `//`）
- 仅在客户端进行输入验证，服务器端未强制验证
- 使用正则表达式黑名单过滤，容易被绕过

## Low risk

### 低风险评级场景

1. **数值型强转** - 用户输入经过 `intval()`, `floatval()` 转换为数字
   - 例：`$id = intval($_GET['id']); $results = $xml->xpath("//item[@id=$id]");`

2. **枚举值验证** - 输入限制为预定义的固定选项
   - 例：`$fields = ['name', 'price']; if (!in_array($sort, $fields)) die(); $xml->xpath("//product/$sort");`

3. **公开数据查询** - XML 数据为公开的产品列表或新闻源

4. **只读操作** - XPath 查询仅用于数据展示，不涉及身份验证或授权

5. **严格长度限制** - 输入长度限制在极短范围（如 5 字符以内）

6. **结果后处理** - 查询结果经过权限检查或数据脱敏

7. **内部系统** - 代码仅在内部管理界面使用，需额外认证

8. **完整转义实现** - 使用经过测试的 XPath 转义库，正确处理所有特殊字符
