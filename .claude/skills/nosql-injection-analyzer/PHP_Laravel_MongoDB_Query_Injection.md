# PHP Laravel MongoDB Query Injection

## Details

**漏洞成因**：Laravel 通过 Eloquent ORM 支持 MongoDB（使用 jenssegers/mongodb 扩展）。当使用 Eloquent 的查询方法时，若参数由用户输入动态构造且未通过模型验证，攻击者可注入 MongoDB 操作符绕过查询逻辑。

**代码审计焦点**：
- 是否使用 Eloquent 的 `where()`、`whereRaw()` 等方法
- `whereRaw()` 方法是否包含用户输入
- 是否使用了模型的 `fillable` 或 `guarded` 属性进行字段限制
- 查询条件的验证机制

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `.where(`、`whereRaw(`、`request()->input` 等关键字
- **(L2: 跳读)** 检查 `whereRaw()` 是否包含用户输入，确认是否使用了绑定参数
- **(L3: 逐行读)** 追踪参数从接收到查询执行的过程，确认是否进行了验证
- **(L4: 跨模块追踪)** 检查是否通过多个控制器或服务组合查询

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 Eloquent 的参数化查询方法
- **(L2: 跳读)** 验证模型是否定义了 `fillable` 或 `guarded` 属性
- **(L3: 逐行读)** 确认是否使用了 Laravel 的 validator 或 FormRequest
- **(L4: 跨模块追踪)** 检查 MongoDB 连接是否启用认证

## Classify

**漏洞研判**：
1. 若 `whereRaw()` 包含用户输入且未使用绑定参数 → 漏洞
2. 若模型未定义 `fillable`，允许批量赋值 → 漏洞
3. 若查询条件未通过验证 → 漏洞

**误报风险**：
1. 使用 Eloquent 的参数化查询 → 低风险
2. 模型定义了 `fillable` 属性 → 低风险
3. 使用 FormRequest 或 validator 验证 → 低风险

## Low risk

- 仅使用 Eloquent 的参数化查询方法
- 模型定义了 `fillable` 或 `guarded` 属性
- 使用 Laravel FormRequest 或 validator 验证
- 字段名使用常量或白名单映射
- MongoDB 连接启用认证

