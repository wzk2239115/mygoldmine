# PHP | Eloquent模型数据用于原生SQL漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否使用了DB::raw()或whereRaw()？
- [ ] 是否在raw SQL中拼接Eloquent模型的属性值？
- [ ] 是否使用了参数化的raw SQL（使用绑定）？
- [ ] Eloquent模型数据是否来自用户输入？

## Details

### 漏洞成因
Laravel的Eloquent ORM通常是安全的，但raw()、whereRaw()、DB::select()等方法允许直接SQL查询。如果在raw SQL中拼接Eloquent模型的属性值（特别是来自用户输入的字段），可能导致SQL注入。这类问题常见于需要复杂查询或特定数据库功能的场景。

### 代码示例

```php
// 漏洞1：在whereRaw中拼接模型属性
<?php

class ProductController extends Controller {
    public function search($categoryId) {
        // 获取类别模型
        $category = Category::find($categoryId);

        // 问题：直接拼接category->name到SQL
        $products = Product::whereRaw(
            "category_name = '{$category->name}'"
        )->get();

        return $products;
    }
}

// 攻击场景：
// 如果category->name包含 "'; DROP TABLE products; --"
// 会导致SQL注入
```

```php
// 漏洞2：在DB::select中使用字符串拼接
<?php

class OrderController extends Controller {
    public function getUserOrders($userId) {
        // 获取用户
        $user = User::find($userId);

        // 问题：直接拼接user->status到SQL
        $query = "SELECT * FROM orders WHERE user_id = {$userId} AND status = '{$user->status}'";

        $orders = DB::select($query);

        return $orders;
    }
}
```

```php
// 漏洞3：在joinRaw中拼接值
<?php

class ReportController extends Controller {
    public function generateReport($reportType) {
        // 获取报表配置
        $config = ReportConfig::where('type', $reportType)->first();

        // 问题：在joinRaw中拼接config值
        $data = Order::joinRaw(
            "JOIN report_mappings ON report_mappings.id = '{$config->mapping_id}'"
        )->get();

        return $data;
    }
}
```

```php
// 漏洞4：在selectRaw中使用模型数据
<?php

class AnalyticsController extends Controller {
    public function analyze($userId) {
        // 获取用户分析配置
        $config = AnalyticsConfig::where('user_id', $userId)->first();

        // 问题：selectRaw中拼接config->metric_name
        $stats = Order::selectRaw(
            "SUM(amount) as total, {$config->metric_name} as metric"
        )->where('user_id', $userId)->get();

        return $stats;
    }
}
```

### 快速定位核心操作
- **关键词扫描**：`whereRaw()`, `DB::select()`, `DB::insert()`, `DB::update()`, `joinRaw()`, `selectRaw()`
- **字符串拼接**：`"{$variable}"`, `.` 拼接运算符, `sprintf()`
- **模型数据使用**：`$model->attribute`, `->name`, `->status` 等
- **缺少绑定**：无绑定参数，如 `?` 占位符或命名参数

### 快速定位保护机制
- **参数化raw()**：使用绑定参数 `whereRaw("... = ?", [$value])`
- **使用Eloquent方法**：`where()`, `whereBetween()` 等代替raw
- **绑定变量**：使用 `whereRaw("... = :value", ['value' => $data])`
- **验证模型数据**：验证从数据库获取的数据合法性

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **whereRaw中拼接模型属性**：`whereRaw("... = '{$model->attribute}'")`
2. **DB::select中拼接用户数据**：`DB::select("SELECT * FROM ... WHERE col = '{$data}'")`
3. **joinRaw/selectRaw中字符串拼接**：无参数绑定
4. **缺少绑定参数**：raw SQL无 `?` 或命名参数

**典型漏洞特征**：
- `whereRaw("column = '{$variable}'")`
- `DB::select("SELECT * FROM ... WHERE ... = '{$modelData}'")`
- `joinRaw("... ON ... = '{$value}'")`
- 缺少 `whereRaw("... = ?", [$value])`

### 误报排除
- ✗ 使用参数化的whereRaw：`whereRaw("column = ?", [$value])`
- ✗ 使用Eloquent的where()方法
- ✗ 使用命名参数：`whereRaw("... = :value", ['value' => $data])`
- ✗ 验证raw SQL中的模型数据

### 代码异味（需进一步验证）
- △ 有参数绑定但仍有部分字符串拼接
- △ 模型数据有验证但验证不完整

---

## Low Risk

给予低风险评级的场景：
1. 使用参数化的whereRaw：`whereRaw("... = ?", [$value])`
2. 仅使用Eloquent的where()等安全方法
3. 从数据库获取的数据经过白名单验证

---

## 安全实现

```php
<?php
namespace App\Services;

use Illuminate\Support\Facades\DB;
use App\Models\Product;
use App\Models\Category;
use App\Models\Order;

class SecureQueryService
{
    // 方法1：完全使用Eloquent（最安全）
    public function searchProductsSafe($categoryId) {
        if (!is_numeric($categoryId) || $categoryId <= 0) return [];
        return Product::where('category_id', $categoryId)->get()->toArray();
    }

    // 方法2：参数化的whereRaw
    public function searchWithWhereRawSafe($categoryId, $status) {
        $validStatuses = ['active', 'inactive', 'pending'];
        if (!is_numeric($categoryId) || !in_array($status, $validStatuses)) return [];
        return Product::whereRaw('category_id = ? AND status = ?',
            [$categoryId, $status])->get()->toArray();
    }

    // 方法3：获取ID后使用而非名称
    public function searchByCategory($categoryName) {
        if (empty($categoryName) || strlen($categoryName) > 100) return [];
        $category = Category::where('name', $categoryName)->first();
        if (!$category) return [];
        return Product::where('category_id', $category->id)->get()->toArray();
    }

    // 方法4：动态过滤with白名单
    public function filterProductsSafe($filters) {
        $allowed = ['category_id', 'price_min', 'price_max', 'status'];
        $query = Product::query();

        foreach ($filters as $key => $value) {
            if (!in_array($key, $allowed)) continue;

            switch ($key) {
                case 'category_id':
                    if (is_numeric($value) && $value > 0) {
                        $query->where('category_id', $value);
                    }
                    break;
                case 'status':
                    if (in_array($value, ['active', 'inactive'])) {
                        $query->where('status', $value);
                    }
                    break;
            }
        }
        return $query->get()->toArray();
    }

    // 方法5：参数化的DB::select
    public function complexQuerySafe($userId, $status) {
        $valid = ['pending', 'completed', 'cancelled'];
        if (!is_numeric($userId) || !in_array($status, $valid)) return [];
        $sql = 'SELECT * FROM orders WHERE user_id = ? AND status = ?';
        return DB::select($sql, [$userId, $status]);
    }
}
```

## 修复优先级

1. **立即修复（当天）**：停止在raw SQL中拼接Eloquent模型属性
2. **快速修复（3天内）**：使用参数化的whereRaw()或改为Eloquent方法
3. **短期改善（1周内）**：审计所有raw()、DB::select()的使用
4. **长期改进（1个月）**：尽量使用Eloquent ORM方法，避免原生SQL
