# Go | 数据库查询结果用于SQL构造漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否从database/sql查询结果中提取数据？
- [ ] 提取的数据是否直接用于后续SQL构造？
- [ ] 是否使用了参数化查询处理这些数据？
- [ ] 是否验证了查询结果的合法性？

## Details

### 漏洞成因
Go的database/sql包支持参数化查询，但当查询结果（特别是来自用户或不可信来源的数据）被用于后续SQL构造时，仍然可能导致二阶SQL注入。此问题常见于需要动态SQL构造或链式查询的场景。

### 代码示例

```go
// 漏洞1：查询结果直接用于SQL字符串拼接
package main

import (
    "database/sql"
    "fmt"
)

func searchProducts(db *sql.DB, categoryID int64) ([]string, error) {
    // 第一步：查询类别名称
    var categoryName string
    err := db.QueryRow(
        "SELECT name FROM categories WHERE id = ?",
        categoryID,
    ).Scan(&categoryName)

    if err != nil {
        return nil, err
    }

    // 问题：直接拼接categoryName到SQL
    // 虽然categoryName来自数据库，但仍需参数化
    query := fmt.Sprintf(
        "SELECT * FROM products WHERE category_name = '%s'",
        categoryName,
    )

    rows, err := db.Query(query)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    // ... 处理结果
    return []string{}, nil
}
```

```go
// 漏洞2：使用QueryRow结果的字符串拼接
func getUserOrders(db *sql.DB, userID int64) ([]string, error) {
    var userStatus string
    err := db.QueryRow(
        "SELECT status FROM users WHERE id = ?",
        userID,
    ).Scan(&userStatus)

    if err != nil {
        return nil, err
    }

    // 问题：userStatus可能包含SQL特殊字符
    // 直接拼接会导致注入
    query := "SELECT * FROM orders WHERE status = '" + userStatus + "'"

    rows, err := db.Query(query)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    return []string{}, nil
}
```

```go
// 漏洞3：在WHERE子句中拼接查询结果
func filterProducts(db *sql.DB, userFilter string) ([]string, error) {
    // 第一步：从查询获取过滤条件
    var filterValue string
    err := db.QueryRow(
        "SELECT filter_value FROM user_filters WHERE user_id = ? LIMIT 1",
        getCurrentUserID(),
    ).Scan(&filterValue)

    if err != nil {
        return nil, err
    }

    // 问题：直接在WHERE子句中使用
    whereClause := fmt.Sprintf(
        "price > %s AND category IN (%s)",
        userFilter,
        filterValue, // 问题：未参数化
    )

    query := "SELECT * FROM products WHERE " + whereClause

    rows, err := db.Query(query)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    return []string{}, nil
}
```

### 快速定位核心操作
- **关键词扫描**：`QueryRow()`, `Query()`, `Scan()`, `fmt.Sprintf()`, 字符串拼接 `+` 或 `fmt.Sprintf`
- **查询操作**：`db.Query(`, `db.QueryRow(`, `rows.Scan(`
- **字符串构造**：`"SELECT * FROM" +`, `fmt.Sprintf("...")`，来自Scan变量
- **缺少参数**：无 `?` 占位符或参数列表

### 快速定位保护机制
- **参数化查询**：所有后续查询使用 `?` 占位符
- **Scan数据验证**：验证扫描结果的合法性
- **避免字符串拼接**：不使用 `fmt.Sprintf()` 或 `+` 构造SQL

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **Scan结果用于字符串拼接**：`fmt.Sprintf("... = '%s'", scannedValue)`
2. **Scan结果直接拼接**：`"WHERE ... = '" + scannedValue + "'"`
3. **缺少参数化**：后续查询无 `?` 占位符
4. **未验证Scan结果**：无对数据合法性的检查

**典型漏洞特征**：
- `db.QueryRow(...).Scan(&var)`后跟 `fmt.Sprintf("... '%s'", var)`
- `"SELECT * FROM ... WHERE col = '" + scannedValue + "'"`
- 缺少 `db.Query(sql, param)` 形式的参数传递
- 链式查询中的中间结果直接拼接

### 误报排除
- ✗ 所有后续查询使用参数化：`db.Query("SELECT * FROM ... WHERE id = ?", scannedID)`
- ✗ 验证Scan结果（白名单）
- ✗ 使用ORM或查询构建器
- ✗ Scan结果用于非SQL场景

### 代码异味（需进一步验证）
- △ 有参数化但仍有部分字符串拼接
- △ Scan结果有某种验证

---

## Low Risk

给予低风险评级的场景：
1. 使用参数化查询处理所有Scan结果
2. Scan结果经过严格白名单验证
3. 使用ORM或查询构建器避免直接SQL拼接

---

## 安全实现

```go
package data

import (
    "database/sql"
    "fmt"
    "strings"
)

type SecureQueryExecutor struct {
    db *sql.DB
}

// 方法1：查询后使用ID而不是名称
func (s *SecureQueryExecutor) SearchByCategory(categoryName string) ([]string, error) {
    if len(categoryName) > 100 {
        return nil, fmt.Errorf("input too long")
    }

    var categoryID int64
    err := s.db.QueryRow(
        "SELECT id FROM categories WHERE name = ?",
        categoryName,
    ).Scan(&categoryID)
    if err != nil {
        return nil, err
    }

    query := "SELECT name FROM products WHERE category_id = ?"
    rows, err := s.db.Query(query, categoryID)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var products []string
    for rows.Next() {
        var name string
        if err := rows.Scan(&name); err != nil {
            continue
        }
        products = append(products, name)
    }
    return products, nil
}

// 方法2：动态过滤with参数化
func (s *SecureQueryExecutor) FilterProducts(filters map[string]interface{}) ([]string, error) {
    allowed := map[string]bool{"category_id": true, "status": true}
    var conditions []string
    var args []interface{}

    for key, value := range filters {
        if !allowed[key] {
            continue
        }
        switch key {
        case "category_id":
            if id, ok := value.(int64); ok {
                conditions = append(conditions, "category_id = ?")
                args = append(args, id)
            }
        case "status":
            if status, ok := value.(string); ok {
                if isValidStatus(status) {
                    conditions = append(conditions, "status = ?")
                    args = append(args, status)
                }
            }
        }
    }

    query := "SELECT * FROM products"
    if len(conditions) > 0 {
        query += " WHERE " + strings.Join(conditions, " AND ")
    }

    rows, err := s.db.Query(query, args...)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var products []string
    for rows.Next() {
        var name string
        if err := rows.Scan(&name); err != nil {
            continue
        }
        products = append(products, name)
    }
    return products, nil
}

// 方法3：排序字段white-listed后使用
func (s *SecureQueryExecutor) ListWithSort(categoryID int64, sortColumn string) ([]string, error) {
    allowed := map[string]bool{"id": true, "name": true, "created_at": true, "price": true}
    if !allowed[sortColumn] {
        sortColumn = "id"
    }

    query := fmt.Sprintf(
        "SELECT name FROM products WHERE category_id = ? ORDER BY %s",
        sortColumn,
    )

    rows, err := s.db.Query(query, categoryID)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var products []string
    for rows.Next() {
        var name string
        if err := rows.Scan(&name); err != nil {
            continue
        }
        products = append(products, name)
    }
    return products, nil
}

func isValidStatus(status string) bool {
    valid := map[string]bool{"active": true, "inactive": true, "pending": true}
    return valid[status]
}
```

## 修复优先级

1. **立即修复（当天）**：停止拼接查询结果到SQL字符串
2. **快速修复（3天内）**：使用参数化查询处理所有数据库操作
3. **短期改善（1周内）**：验证查询结果的合法性，实施白名单
4. **长期改进（1个月）**：使用ORM或查询构建器，完整的安全审计
