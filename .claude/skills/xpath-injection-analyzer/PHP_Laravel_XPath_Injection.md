# PHP - Laravel 框架 XPath 注入

## Details

### 漏洞成因
Laravel 框架虽然提供强大的数据库 ORM 和验证机制，但在处理 XML 数据时，开发者仍可能使用原生 PHP 的 `DOMXPath` 或 `SimpleXMLElement`。当从 Laravel 的 `Request` 对象（`$request->input()`, `$request->get()`）获取的用户输入直接拼接到 XPath 表达式时，将导致注入漏洞。Laravel 的验证规则如果未正确配置，无法防御 XPath 注入。常见于 XML 配置管理、SOAP API 集成和 XML 数据导入功能。

代码示例：
```php
use Illuminate\Http\Request;

class XmlController extends Controller
{
    public function search(Request $request)
    {
        $username = $request->input('username');

        $xml = simplexml_load_file(storage_path('users.xml'));
        $query = "//user[username='$username']";
        $results = $xml->xpath($query);

        return response()->json($results);
    }
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `use Illuminate\Http\Request`, `Request $request`
- `$request->input()`, `$request->get()`, `$request->post()`, `$request->query()`
- `simplexml_load_*()`, `new DOMXPath()`, `->xpath()`, `->query()`
- 字符串拼接：`.`, `sprintf()`, `"$var"`, `"{$var}"`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **Laravel 验证** (L2 跳读) - 检查 `$request->validate()`, `Validator::make()`, 表单请求类
- **验证规则** (L2 跳读) - 查找验证规则：`alpha_num`, `alpha_dash`, `regex`, `in` 等
- **中间件验证** (L3 逐行读) - 检查自定义验证中间件或全局中间件
- **转义函数** (L3 逐行读) - 检查自定义 helper 函数或 service 类中的转义逻辑
- **跨层追踪** (L4) - 从 Controller 到 Service/Repository 层的数据流，检查中间处理

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. Laravel Request 对象的用户输入通过字符串拼接嵌入 XPath 表达式
2. 未使用 Laravel 验证或验证规则不严格（如仅 `required`）
3. 无有效的转义或参数化机制
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、配置）

**误报情况**：
- 用户输入通过 Laravel 验证且规则严格（如 `alpha_num|max:10`）
- 使用表单请求类（Form Request）进行强制验证
- 拼接的数据来自配置文件或已认证用户的会话数据
- XML 数据为公开的静态资源

**代码异味**：
- 验证规则存在但不充分（如仅 `string|max:255`）
- 在 Controller 中直接处理 XPath，未通过 Service 层封装
- 使用 `$request->all()` 获取所有输入而未验证
- 自定义转义函数但未覆盖所有 XPath 特殊字符

## Low risk

### 低风险评级场景

1. **强验证规则** - 使用 Laravel 验证且规则严格
   - 例：`$request->validate(['field' => 'alpha_num|max:20']);`

2. **表单请求类** - 使用专门的 Form Request 类进行集中验证
   - 例：`public function search(SearchRequest $request)`

3. **枚举值验证** - 使用 `in` 验证规则限制输入为固定选项
   - 例：`'sort' => 'required|in:name,email,created_at'`

4. **数值型强转** - 在 Service 层进行类型转换
   - 例：`$id = (int) $request->input('id');`

5. **非敏感数据** - XML 数据为公开的产品目录或配置

6. **中间件保护** - 自定义中间件对所有 XML 相关输入进行清理

7. **结果过滤** - 使用 Laravel 的资源类或策略类对查询结果进行权限控制

8. **内部 API** - 路由通过 `auth:sanctum` 或 `auth:api` 中间件保护，仅认证用户可访问
