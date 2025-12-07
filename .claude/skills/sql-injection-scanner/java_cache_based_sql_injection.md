# Java | 缓存数据用于SQL构造漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟

## 🚀 30秒快速清单
- [ ] 缓存数据是否直接拼接SQL？
- [ ] 缓存来源是否可被污染？
- [ ] 是否验证了缓存数据？
- [ ] 是否使用了参数化查询？

## Details

### 漏洞成因
二阶SQL注入：缓存或数据库中的数据被用于后续SQL构造。如果缓存数据来自用户输入且未参数化，可能导致SQL注入。

### 代码示例

```java
// 漏洞1：缓存数据直接拼接SQL
@Service
public class UserService {
    public String generateReport(Long userId) {
        // 从缓存获取用户信息
        User user = cache.get("user:" + userId);

        // 问题：直接拼接user.getName()到SQL
        String sql = "SELECT * FROM orders WHERE user_name = '" + user.getName() + "'";

        return jdbcTemplate.queryForObject(sql, String.class);
    }
}
```

```java
// 漏洞2：Redis缓存的SQL模板
@Service
public class ReportService {
    public List<?> executeReport(String reportType) {
        // 从Redis获取SQL模板
        String sqlTemplate = redis.opsForValue().get("report:" + reportType);

        // 问题：直接执行可能被污染的SQL
        return jdbcTemplate.query(sqlTemplate);
    }
}
```

```java
// 漏洞3：缓存过滤条件
@Service
public class SearchService {
    public List<Product> search(Long userId) {
        // 缓存用户之前的搜索条件
        Map<String, String> filters = cache.get("filters:" + userId);

        String whereClause = "";
        for (Map.Entry<String, String> e : filters.entrySet()) {
            // 问题：直接拼接缓存的过滤条件
            whereClause += " AND " + e.getKey() + " = '" + e.getValue() + "'";
        }

        String sql = "SELECT * FROM products WHERE 1=1" + whereClause;
        return jdbcTemplate.query(sql);
    }
}
```

### 快速定位
- **缓存获取**：`cache.get()`, `redis.opsForValue().get()`
- **SQL拼接**：`"SELECT ... " + cached_data`, `f"... {value}"`
- **缺少参数化**：无 `?` 占位符或参数列表
- **来源**：用户输入→缓存→SQL

### 保护机制
- **参数化**：`query(sql, params)`, 所有缓存数据都参数化
- **验证**：缓存数据的白名单验证
- **避免拼接**：使用ORM方法代替字符串拼接
- **缓存隔离**：不同数据源使用不同缓存key

---

## Classify

### 确认漏洞
1. 缓存数据直接拼接SQL
2. 缺少参数化
3. 缓存来源不可信
4. 无数据验证

### 误报排除
- ✗ 参数化查询处理缓存数据
- ✗ 缓存数据白名单验证
- ✗ 使用ORM方法
- ✗ 缓存来源可信（系统生成）

---

## Low Risk

1. **参数化**：所有缓存数据用参数化
2. **验证**：白名单检查缓存值
3. **来源可信**：缓存仅包含系统生成数据
4. **定期清理**：防止旧恶意数据

---

## 安全实现

```java
@Service
@RequiredArgsConstructor
public class SecureCacheQueryService {
    private final JdbcTemplate jdbcTemplate;
    private final RedisTemplate<String, Object> redis;

    // 方法1：参数化处理缓存
    public List<Order> searchSafe(Long userId) {
        String cacheKey = "filters:" + userId;
        Map<String, String> filters = getCachedFilters(cacheKey);

        // 验证过滤条件
        if (!validateFilters(filters)) {
            return new ArrayList<>();
        }

        // 使用参数化查询
        StringBuilder sql = new StringBuilder("SELECT * FROM orders WHERE user_id = ?");
        List<Object> params = new ArrayList<>();
        params.add(userId);

        for (Map.Entry<String, String> e : filters.entrySet()) {
            if (isValidFilterKey(e.getKey())) {
                sql.append(" AND ").append(e.getKey()).append(" = ?");
                params.add(e.getValue());
            }
        }

        return jdbcTemplate.query(sql.toString(), params.toArray());
    }

    // 方法2：使用缓存ID而非值
    public List<Product> getProductsById(Long categoryId) {
        String cacheKey = "category:" + categoryId;
        Long cachedId = (Long) redis.opsForValue().get(cacheKey);

        if (cachedId == null) {
            return new ArrayList<>();
        }

        // 使用ID（而非名称）进行参数化查询
        String sql = "SELECT * FROM products WHERE category_id = ?";
        return jdbcTemplate.query(sql, new Object[]{cachedId});
    }

    // 方法3：预定义SQL模板
    public List<?> executeReport(String reportType) {
        // 使用白名单，不从缓存读取SQL
        String sql = getReportSql(reportType);
        if (sql == null) {
            return new ArrayList<>();
        }
        return jdbcTemplate.query(sql);
    }

    private String getReportSql(String type) {
        switch(type) {
            case "sales": return "SELECT * FROM orders WHERE status = ?";
            case "inventory": return "SELECT * FROM products WHERE stock > ?";
            default: return null;
        }
    }

    private boolean validateFilters(Map<String, String> filters) {
        if (filters == null || filters.size() > 10) {
            return false;
        }
        for (Map.Entry<String, String> e : filters.entrySet()) {
            if (!isValidFilterKey(e.getKey()) || !isValidValue(e.getValue())) {
                return false;
            }
        }
        return true;
    }

    private boolean isValidFilterKey(String key) {
        return key.matches("[a-z_]+");
    }

    private boolean isValidValue(String value) {
        return value != null && value.length() > 0 && value.length() <= 100;
    }

    private Map<String, String> getCachedFilters(String key) {
        // 返回缓存数据
        return new HashMap<>();
    }
}
```

## 修复优先级

1. **当天**：停止拼接缓存数据，使用参数化
2. **3天**：验证缓存数据，实施白名单
3. **1周**：使用预定义SQL模板
4. **2周**：完整的缓存数据验证策略
