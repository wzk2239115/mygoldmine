# TypeScript | 缓存数据用于SQL构造漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否使用了Redis、内存缓存或其他缓存系统？
- [ ] 缓存中的数据是否直接用于SQL查询构造？
- [ ] 是否验证了缓存数据的合法性？
- [ ] 缓存中的数据来源是否可被污染？
- [ ] 是否使用了参数化查询处理缓存数据？

## Details

### 漏洞成因
TypeScript应用（特别是使用TypeORM、Sequelize等ORM框架的应用）可能使用Redis或内存缓存来提高性能。如果缓存中的数据（来自用户输入、外部API或不可信来源）被直接用于SQL构造，可能导致二阶SQL注入。此问题常见于缓存用户查询条件、配置信息、报表模板等场景。

### 代码示例

```typescript
// 漏洞1：从Redis缓存读取数据后拼接SQL
import { getRedis } from './redis';
import { getConnection } from 'typeorm';

export async function searchProducts(categoryId: number): Promise<Product[]> {
    const redis = getRedis();

    // 第一步：从缓存获取类别信息
    const cacheKey = `category:${categoryId}`;
    let categoryName = await redis.get(cacheKey);

    if (!categoryName) {
        // 从数据库查询并缓存
        const connection = getConnection();
        const category = await connection.query(
            'SELECT name FROM categories WHERE id = ?',
            [categoryId]
        );

        if (!category.length) {
            return [];
        }

        categoryName = category[0].name;
        await redis.setex(cacheKey, 3600, categoryName);
    }

    // 问题：直接拼接缓存的categoryName到SQL
    const products = await getConnection().query(
        `SELECT * FROM products WHERE category_name = '${categoryName}'`
    );

    return products;
}

// 攻击场景：
// 1. 攻击者污染缓存：redis.set("category:1", "'; DROP TABLE products; --")
// 2. 后续查询时，缓存中的恶意数据被用于SQL构造
```

```typescript
// 漏洞2：缓存的用户配置用于SQL WHERE子句
import { Cache } from 'cache-manager';

export async function getUserData(userId: number): Promise<any[]> {
    const cache: Cache = /* ... */;
    const key = `user:${userId}:filters`;

    // 获取缓存的用户过滤条件
    let filters = await cache.get<string>(key);

    if (!filters) {
        // 从数据库获取
        const user = await User.findOne({ where: { id: userId } });
        filters = user?.filters || 'status = "active"';
        await cache.set(key, filters, { ttl: 3600 });
    }

    // 问题：直接使用缓存的filters在SQL中
    const data = await getConnection().query(
        `SELECT * FROM data WHERE ${filters}`
    );

    return data;
}

// 攻击场景：
// 1. 攻击者保存恶意的filters："status = 'active' OR 1=1"
// 2. 该filters被缓存
// 3. 后续调用时，缓存中的恶意条件被执行
```

```typescript
// 漏洞3：缓存的SQL模板直接执行
import NodeCache from 'node-cache';

export async function executeReport(reportType: string): Promise<any[]> {
    const cache = new NodeCache({ stdTTL: 600 });
    const key = `report:${reportType}`;

    // 从缓存获取报表SQL模板
    let sqlTemplate = cache.get<string>(key);

    if (!sqlTemplate) {
        // 从数据库或配置获取
        const config = await ReportConfig.findOne({ where: { type: reportType } });
        sqlTemplate = config?.sqlTemplate || '';
        cache.set(key, sqlTemplate);
    }

    // 问题：直接执行缓存的SQL（可能被污染）
    const results = await getConnection().query(sqlTemplate);

    return results;
}
```

### 快速定位核心操作
- **关键词扫描**：`redis.get()`, `cache.get()`, `getConnection().query()`, 字符串拼接
- **缓存操作**：`redis`, `Cache`, `ioredis`, `cache-manager`, `node-cache`
- **SQL构造**：`` `SELECT ... WHERE ${cachedData}` ``, `+` 拼接
- **缺少参数化**：无 `?` 占位符或参数数组

### 快速定位保护机制
- **参数化查询**：使用 `?` 占位符或命名参数处理缓存数据
- **缓存验证**：验证缓存中数据的合法性
- **缓存隔离**：不同用户或会话使用不同的缓存key
- **缓存清理**：定期清理缓存，防止旧恶意数据

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **缓存数据拼接SQL**：`` `SELECT ... ${cachedData}` ``或 `"... '" + cachedData + "'"`
2. **缓存来源不可信**：来自用户输入、外部API
3. **缺少参数化**：后续查询无 `?` 占位符或参数数组
4. **缺少验证**：无对缓存数据合法性的检查

**典型漏洞特征**：
- `const data = cache.get(key); query(f"... = '{data}'")`
- `redis.get(...); connection.query(\`... ${value}\`)`
- 缺少 `connection.query(sql, [cachedValue])`
- 缺少缓存的过期和验证

### 误报排除
- ✗ 使用参数化查询处理缓存数据
- ✗ 缓存数据经过严格白名单验证
- ✗ 缓存仅包含信任的数据（如系统生成）
- ✗ 定期刷新缓存，防止数据过旧

### 代码异味（需进一步验证）
- △ 有参数化但仅处理部分缓存数据
- △ 缓存数据有某种验证

---

## Low Risk

给予低风险评级的场景：
1. 使用参数化查询处理所有缓存数据
2. 缓存数据来源可信（如系统配置）
3. 实施严格的缓存验证和定期清理

---

## 安全实现

```typescript
// secure-cache-sql.ts
import { createClient, RedisClient } from 'redis';
import { getConnection } from 'typeorm';
import * as NodeCache from 'node-cache';

export class SecureCacheQueryService {
    private redis: RedisClient;

    constructor() {
        this.redis = createClient();
    }

    // 方法1：使用ID而非名称避免拼接
    async searchProductsSafe(categoryId: number): Promise<any[]> {
        if (!Number.isInteger(categoryId) || categoryId <= 0) return [];

        try {
            const cacheKey = `category:${categoryId}`;
            let categoryData = await this.redis.get(cacheKey);

            if (!categoryData) {
                const connection = getConnection();
                const categories = await connection.query(
                    'SELECT id FROM categories WHERE id = $1', [categoryId]
                );
                if (!categories.length) return [];
                categoryData = JSON.stringify(categories[0]);
                await this.redis.setex(cacheKey, 3600, categoryData);
            }

            const category = JSON.parse(categoryData);
            const connection = getConnection();
            return connection.query(
                'SELECT * FROM products WHERE category_id = $1 LIMIT 100',
                [category.id]
            );
        } catch (error) {
            return [];
        }
    }

    // 方法2：验证并参数化缓存的过滤条件
    async searchWithCachedFilters(userId: number): Promise<any[]> {
        if (!Number.isInteger(userId) || userId <= 0) return [];

        try {
            const cacheKey = `user:${userId}:filters`;
            let filtersJson = await this.redis.get(cacheKey);

            if (!filtersJson) {
                const connection = getConnection();
                const user = await connection.query('SELECT filters FROM users WHERE id = $1', [userId]);
                if (!user.length) return [];
                filtersJson = user[0].filters || '{}';
                await this.redis.setex(cacheKey, 3600, filtersJson);
            }

            const filters = this.validateAndParseFilters(filtersJson);
            const connection = getConnection();
            let query = connection.createQueryBuilder('product')
                .where('product.user_id = :userId', { userId });

            for (const [key, value] of Object.entries(filters)) {
                if (key === 'category_id' && typeof value === 'number') {
                    query = query.andWhere('product.category_id = :categoryId', { categoryId: value });
                } else if (key === 'status' && this.isValidStatus(value as string)) {
                    query = query.andWhere('product.status = :status', { status: value });
                }
            }
            return query.getMany();
        } catch (error) {
            return [];
        }
    }

    // 方法3：white-listed排序字段
    async listWithCachedSort(userId: number): Promise<any[]> {
        if (!Number.isInteger(userId) || userId <= 0) return [];

        try {
            const cacheKey = `user:${userId}:sort`;
            let sortConfig = await this.redis.get(cacheKey);
            let sortColumn = 'id', sortDirection: 'ASC' | 'DESC' = 'ASC';

            if (sortConfig) {
                try {
                    const config = JSON.parse(sortConfig);
                    const allowed = ['id', 'name', 'created_at', 'price'];
                    if (allowed.includes(config.column)) sortColumn = config.column;
                    if (['ASC', 'DESC'].includes(config.direction?.toUpperCase())) {
                        sortDirection = config.direction.toUpperCase() as 'ASC' | 'DESC';
                    }
                } catch (e) {}
            }

            const connection = getConnection();
            return connection.getRepository('Product').createQueryBuilder()
                .where('user_id = :userId', { userId })
                .orderBy(sortColumn, sortDirection)
                .limit(100)
                .getMany();
        } catch (error) {
            return [];
        }
    }

    // 方法4：预定义报表模板
    async executeReportSafe(reportType: string): Promise<any[]> {
        const allowed = ['sales', 'inventory', 'users'];
        if (!allowed.includes(reportType)) return [];

        const templates: Record<string, any> = {
            'sales': { sql: 'SELECT * FROM orders WHERE status = $1', params: ['completed'] },
            'inventory': { sql: 'SELECT * FROM products WHERE stock > $1', params: [0] },
            'users': { sql: 'SELECT id, name, email FROM users WHERE status = $1', params: ['active'] }
        };

        try {
            const template = templates[reportType];
            return getConnection().query(template.sql, template.params);
        } catch (error) {
            return [];
        }
    }

    private validateAndParseFilters(filtersJson: string): Record<string, any> {
        try {
            const filters = JSON.parse(filtersJson);
            if (typeof filters !== 'object') return {};

            const result: Record<string, any> = {};
            const allowed = ['category_id', 'price_min', 'price_max', 'status'];

            for (const key of allowed) {
                if (!(key in filters)) continue;
                const value = filters[key];

                if (key === 'category_id' && Number.isInteger(value) && value > 0) {
                    result[key] = value;
                } else if ((key === 'price_min' || key === 'price_max') && typeof value === 'number' && value >= 0) {
                    result[key] = value;
                } else if (key === 'status' && this.isValidStatus(value)) {
                    result[key] = value;
                }
            }
            return result;
        } catch (error) {
            return {};
        }
    }

    private isValidStatus(value: any): boolean {
        return typeof value === 'string' && ['active', 'inactive', 'pending'].includes(value);
    }
}
```

## 修复优先级

1. **立即修复（当天）**：停止直接拼接缓存数据到SQL
2. **快速修复（3天内）**：使用参数化处理所有缓存数据
3. **短期改善（1周内）**：验证缓存数据合法性，实施白名单
4. **长期改进（1个月）**：定期审查缓存使用，完整的安全测试
