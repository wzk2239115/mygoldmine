# PHP | 数据库数据用于用户输入处理漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否从数据库读取数据后再用于处理用户输入（如搜索、过滤）？
- [ ] 数据库中的数据是否可能被污染（来自用户之前的输入）？
- [ ] 是否对这些数据进行了验证和清理？
- [ ] 是否在SQL查询中直接使用了这些数据？

## Details

### 漏洞成因
二阶SQL注入的一种形式：先将恶意输入存储到数据库（可能被验证或清理），后续在使用该数据时作为新的查询条件或SQL构造。如果数据库中的数据（如用户设置、保存的查询条件、配置等）被再次用于SQL构造而未进行参数化，可能导致SQL注入。此问题常见于搜索过滤、用户偏好设置、报表配置等场景。

### 代码示例

```php
// 漏洞1：从数据库读取的搜索条件直接用于SQL查询
<?php

class SearchController extends Controller {
    public function search($userId) {
        // 从数据库获取用户保存的搜索条件
        $searchPrefs = DB::select(
            'SELECT filters FROM user_preferences WHERE user_id = ?',
            [$userId]
        );

        if (empty($searchPrefs)) {
            return [];
        }

        $filters = $searchPrefs[0]->filters;  // "'; DROP TABLE products; --"

        // 问题：直接拼接数据库读取的filters到SQL
        $query = "SELECT * FROM products WHERE {$filters}";

        $products = DB::select($query);

        return $products;
    }
}

// 攻击场景：
// 1. 攻击者首先通过某个输入点保存恶意的filter值
// 2. 该值被存储到user_preferences表
// 3. 后续搜索时，从数据库读取filter并直接拼接到SQL
```

```php
// 漏洞2：从数据库读取的配置用于WHERE子句
<?php

class ReportController extends Controller {
    public function generateReport($reportId) {
        // 从数据库读取报表配置
        $report = DB::table('reports')->find($reportId);

        if (!$report) {
            return null;
        }

        // 问题：report->where_clause来自用户之前的输入
        // 虽然经过了某种验证，但仍可能包含SQL注入代码
        $whereClause = $report->where_clause;  // "user_id = 1 OR 1=1"

        $sql = "SELECT * FROM data WHERE {$whereClause}";

        $data = DB::select($sql);

        return $data;
    }
}
```

```php
// 漏洞3：用户保存的列表字段用于select
<?php

class DataController extends Controller {
    public function getData($userId) {
        // 获取用户保存的要查询的列
        $config = DB::table('user_configs')
            ->where('user_id', $userId)
            ->first();

        if (!$config) {
            return [];
        }

        // 问题：columns来自用户之前的输入
        $columns = $config->columns;  // "id, name, email"或恶意输入

        // 直接在SELECT中使用
        $sql = "SELECT {$columns} FROM users";

        $results = DB::select($sql);

        return $results;
    }
}
```

### 快速定位核心操作
- **关键词扫描**：`DB::select()`, `DB::table()`, `->first()`, 数据库查询后跟字符串拼接
- **两步查询**：先查询数据库获取值，后在另一个SQL中使用这个值
- **字符串拼接**：`"{$variable}"`, `.` 拼接, 来自数据库的 `->attribute`
- **缺少参数化**：后续SQL无 `?` 或绑定参数

### 快速定位保护机制
- **参数化所有查询**：即使是"来自数据库"的值也要参数化
- **数据验证**：验证从数据库读取的数据合法性
- **白名单**：对于列名、表名等不可参数化的部分使用白名单
- **避免二阶注入**：不要假设数据库中的数据是"安全的"

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **两步SQL：先查询后拼接**：`DB::select(...); 拼接结果到新SQL`
2. **缺少参数化**：新SQL无 `?` 或绑定参数
3. **数据来源混杂**：用户输入存储→从库读取→再用于SQL
4. **配置或偏好拼接**：用户设置的搜索条件、列名等直接用于SQL

**典型漏洞特征**：
- `$row = DB::table(...)->first(); ... DB::select("... WHERE {$row->field} ...")`
- `$config = $model->config; DB::select("SELECT {$config} FROM ...")`
- 缺少参数化的后续查询
- 两个不同的SQL操作，中间有数据传递

### 误报排除
- ✗ 后续查询使用参数化：`DB::select("... WHERE col = ?", [$value])`
- ✗ 从数据库读取的数据经过严格白名单验证
- ✗ 使用ORM方法而不是拼接
- ✗ 列名/表名验证后再使用

### 代码异味（需进一步验证）
- △ 有参数化但不完整
- △ 有验证但验证不够严格

---

## Low Risk

给予低风险评级的场景：
1. 所有后续查询都使用参数化
2. 从数据库读取的数据经过白名单验证
3. 使用ORM方法避免直接SQL拼接

---

## 安全实现

```php
<?php
namespace App\Services;

use Illuminate\Support\Facades\DB;

class SecureDbService
{
    // 方法1：直接使用用户输入，参数化处理
    public function searchSafe($userId, $keyword) {
        if (!is_numeric($userId) || !is_string($keyword) ||
            strlen($keyword) > 100 || empty($keyword)) return [];
        return DB::table('products')
            ->where('user_id', $userId)
            ->where('name', 'like', "%{$keyword}%")
            ->get()->toArray();
    }

    // 方法2：验证数据库读取的过滤条件
    public function searchWithSavedFilters($userId) {
        if (!is_numeric($userId) || $userId <= 0) return [];

        $config = DB::table('user_filters')
            ->where('user_id', $userId)->first();
        if (!$config) return [];

        $filters = $this->validateFilters(
            json_decode($config->filters, true) ?? []
        );

        $query = DB::table('products');
        foreach ($filters as $field => $value) {
            if ($this->isAllowedField($field) &&
                $this->isValidValue($field, $value)) {
                $query->where($field, $value);
            }
        }
        return $query->get()->toArray();
    }

    private function validateFilters($data) {
        if (!is_array($data)) return [];
        $allowed = ['category_id', 'price_min', 'price_max', 'status'];
        return array_intersect_key(array_flip($allowed), array_flip(array_keys($data)));
    }

    private function isAllowedField($field) {
        return in_array($field, ['category_id', 'price_min', 'price_max', 'status']);
    }

    private function isValidValue($field, $value) {
        switch ($field) {
            case 'category_id':
            case 'price_min':
            case 'price_max':
                return is_numeric($value) && $value >= 0;
            case 'status':
                return in_array($value, ['active', 'inactive', 'pending']);
            default:
                return false;
        }
    }

    // 方法3：预定义报表模板
    public function generateReportSafe($reportType, $userId) {
        $allowed = ['sales', 'inventory', 'users'];
        if (!in_array($reportType, $allowed) || !is_numeric($userId)) return null;

        $templates = [
            'sales' => 'SELECT * FROM orders WHERE user_id = ?',
            'inventory' => 'SELECT * FROM products WHERE owner_id = ?',
            'users' => 'SELECT id, name, email FROM users WHERE account_id = ?'
        ];

        if (!isset($templates[$reportType])) return null;
        return DB::select($templates[$reportType], [$userId]);
    }

    // 方法4：white-listed列选择
    public function getDataWithColumns($userId) {
        if (!is_numeric($userId) || $userId <= 0) return [];

        $allowed = ['id', 'name', 'email', 'created_at', 'status'];
        $config = DB::table('user_config')->where('user_id', $userId)->first();

        $selected = $allowed;
        if ($config && !empty($config->columns)) {
            $cols = json_decode($config->columns, true);
            $selected = array_intersect($cols ?? [], $allowed) ?: $allowed;
        }

        return DB::table('users')->select($selected)
            ->where('account_id', $userId)->get()->toArray();
    }
}
```

## 修复优先级

1. **立即修复（当天）**：停止直接拼接从数据库读取的值到SQL
2. **快速修复（3天内）**：使用参数化处理所有来自数据库的值
3. **短期改善（1周内）**：实施白名单验证，特别是列名、表名、排序字段
4. **长期改进（1个月）**：审计所有多步查询，完整的安全测试
