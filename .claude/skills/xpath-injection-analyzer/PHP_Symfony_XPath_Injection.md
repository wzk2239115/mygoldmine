# PHP - Symfony 框架 XPath 注入

## Details

### 漏洞成因
Symfony 框架提供强大的 XML 处理组件（如 `DomCrawler`），但在使用原生 PHP 的 `DOMXPath` 或 `SimpleXMLElement` 进行 XML 配置解析或数据查询时，若从 Symfony 的 `Request` 对象（`$request->query->get()`, `$request->request->get()`）获取的用户输入直接拼接到 XPath 表达式，将导致注入漏洞。Symfony 的表单组件和验证器如果未正确配置，无法自动防御此类注入。常见于 XML 配置管理、SOAP 服务集成和 XML 数据导入。

代码示例：
```php
use Symfony\Component\HttpFoundation\Request;

class XmlController extends AbstractController
{
    public function search(Request $request): Response
    {
        $category = $request->query->get('category');

        $dom = new \DOMDocument();
        $dom->load('config/products.xml');
        $xpath = new \DOMXPath($dom);

        $query = "//product[@category='$category']";
        $nodes = $xpath->query($query);

        return $this->json($nodes);
    }
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `use Symfony\Component\HttpFoundation\Request`, `Request $request`
- `$request->query->get()`, `$request->request->get()`, `$request->get()`
- `new \DOMXPath()`, `->query()`, `->evaluate()`
- `simplexml_load_*()`, `->xpath()`
- 字符串拼接：`.`, `sprintf()`, `"$var"`, `"{$var}"`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **Symfony 验证器** (L2 跳读) - 检查 `Validator`, `Assert` 注解/属性, `FormType` 约束
- **表单验证** (L2 跳读) - 查找 `FormType` 类，检查字段约束（`NotBlank`, `Regex`, `Choice`）
- **ParamConverter** (L3 逐行读) - 检查是否使用 ParamConverter 进行类型转换和验证
- **自定义验证器** (L3 逐行读) - 检查自定义 Constraint 和 Validator 实现
- **服务层追踪** (L4) - 从 Controller 到 Service 的数据流，检查业务逻辑层的输入处理

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. Symfony Request 对象的用户输入通过字符串拼接嵌入 XPath 表达式
2. 未使用 Symfony 验证器或表单组件进行输入验证
3. 无有效的转义或参数化机制
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、配置）

**误报情况**：
- 用户输入通过 Symfony 表单组件验证且约束严格（如 `Regex`, `Choice`）
- 使用 Assert 注解/属性进行 DTO 验证
- 拼接的数据来自配置文件或 Symfony 参数包
- XML 数据为公开的静态资源或第三方 API 响应

**代码异味**：
- 直接使用 `$request->get()` 而非通过表单或验证器
- 验证约束存在但不严格（如仅 `NotBlank`）
- 在 Controller 中直接处理 XPath，未通过 Service 封装
- 使用 `$request->request->all()` 获取所有 POST 数据而未验证

## Low risk

### 低风险评级场景

1. **表单验证** - 使用 Symfony Form 组件且配置严格约束
   - 例：`->add('field', TextType::class, ['constraints' => [new Regex('/^[a-zA-Z0-9]+$/')]])`

2. **Assert 注解** - 在 DTO 类上使用 Assert 注解进行验证
   - 例：`#[Assert\Regex(pattern: '/^[a-zA-Z0-9]+$/')]`

3. **Choice 约束** - 使用 Choice 约束限制输入为枚举值
   - 例：`new Assert\Choice(['name', 'email', 'phone'])`

4. **ParamConverter** - 使用 ParamConverter 自动转换和验证实体
   - 例：路由参数直接转换为已验证的实体对象

5. **非敏感数据** - XML 数据为公开的配置文件或产品目录

6. **Security Voter** - 查询结果经过 Symfony Security Voter 进行权限检查

7. **服务层封装** - XPath 查询封装在 Service 层，且输入经过严格验证

8. **开发环境** - 代码仅在 `dev` 环境运行，且有额外的访问控制
