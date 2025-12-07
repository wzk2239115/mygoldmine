# JavaScript | ORM查询结果用于原生SQL漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否使用了query()或execute()执行原生SQL？
- [ ] ORM查询结果是否直接用于SQL构造？
- [ ] 是否使用了参数化的查询？
- [ ] 是否验证了ORM结果的合法性？

## Details

### 漏洞成因
Node.js的各种ORM框架（Sequelize、TypeORM、Knex.js等）通常提供安全的查询方法，但当使用raw()、query()等方法执行原生SQL时，如果拼接ORM查询结果，可能导致SQL注入。此问题常见于需要复杂查询或特定数据库功能的场景。

### 代码示例

```javascript
// 漏洞1：Sequelize原生查询拼接ORM结果
const { sequelize } = require('./models');

async function searchProducts(categoryId) {
    // 第一步：通过ORM查询
    const category = await Category.findByPk(categoryId);

    if (!category) {
        return [];
    }

    // 问题：直接拼接category.name到SQL
    const products = await sequelize.query(
        `SELECT * FROM products WHERE category_name = '${category.name}'`
    );

    return products[0];
}

// 攻击场景：
// 如果category.name包含 "'; DROP TABLE products; --"
// 会导致SQL注入
```

```javascript
// 漏洞2：Knex.js中的raw()拼接
const knex = require('knex')({...});

async function getOrders(userId) {
    // 获取用户
    const user = await knex('users').where('id', userId).first();

    if (!user) {
        return [];
    }

    // 问题：user.status直接拼接到raw()
    const orders = await knex.raw(
        `SELECT * FROM orders WHERE user_id = ? AND status = '${user.status}'`,
        [userId]
    );

    return orders.rows;
}
```

```javascript
// 漏洞3：TypeORM的query()拼接
import { getConnection } from 'typeorm';

async function generateReport(reportType) {
    const connection = getConnection();

    // 获取报表配置
    const config = await connection.getRepository('ReportConfig')
        .findOne({ where: { type: reportType } });

    if (!config) {
        return null;
    }

    // 问题：config.sql直接作为查询
    const results = await connection.query(config.sql);

    return results;
}
```

### 快速定位核心操作
- **关键词扫描**：`sequelize.query()`, `knex.raw()`, `connection.query()`, `db.query()`, 模板字符串`` ${ } ``
- **ORM查询**：`findByPk()`, `find()`, `first()`, `getRepository()`
- **字符串拼接**：`` `SELECT... ${variable}` ``, `+` 拼接
- **缺少参数**：raw()中无参数数组，直接拼接

### 快速定位保护机制
- **参数化raw()**：`raw("SELECT * FROM ... WHERE id = ?", [value])`
- **避免直接拼接**：不在模板字符串中包含ORM结果
- **使用ORM方法**：`where()`, `andWhere()` 代替raw
- **参数绑定**：使用命名参数或位置参数

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **raw()中拼接ORM结果**：`` raw(`... ${ormData}`) ``
2. **query()中拼接变量**：`` query(`SELECT ... WHERE col = '${var}'`) ``
3. **缺少参数化**：无参数数组或绑定参数
4. **从ORM提取值后直接拼接**：`.first(); ... query(${value})`

**典型漏洞特征**：
- `` sequelize.query(`SELECT ... WHERE col = '${ormData}'`) ``
- `` knex.raw(`... AND status = '${user.status}'`) ``
- `` connection.query(`SELECT * FROM ... WHERE id = ${id}`) ``
- `` connection.query(configFromORM.sqlTemplate) ``

### 误报排除
- ✗ 使用参数化的raw()：`raw("... WHERE id = ?", [value])`
- ✗ 仅使用ORM方法
- ✗ 验证ORM结果后再使用（白名单）
- ✗ 使用ORM的参数化功能

### 代码异味（需进一步验证）
- △ 有参数化但仍有部分拼接
- △ ORM结果有验证

---

## Low Risk

给予低风险评级的场景：
1. 使用参数化的raw()：`raw("... = ?", [value])`
2. 仅使用ORM的where()等方法
3. 从ORM读取的值经过白名单验证

---

## 安全实现

```javascript
// secure_orm_queries.js
const { sequelize, Category, Product, User, Order } = require('./models');
const knex = require('knex');
const { getConnection } = require('typeorm');

class SecureOrmQueries {
    // 方法1：完全使用ORM（最安全）
    static async searchProductsSafe(categoryId) {
        if (!Number.isInteger(categoryId) || categoryId <= 0) return [];
        return Product.findAll({ where: { category_id: categoryId } }).catch(() => []);
    }

    // 方法2：参数化的原生查询
    static async searchWithRawSafe(categoryId, status) {
        if (!Number.isInteger(categoryId) || !['active', 'inactive', 'pending'].includes(status)) return [];
        return sequelize.query(
            'SELECT * FROM products WHERE category_id = :categoryId AND status = :status',
            { replacements: { categoryId, status }, type: sequelize.QueryTypes.SELECT }
        ).catch(() => []);
    }

    // 方法3：获取ID后使用而非名称
    static async searchByCategory(categoryName) {
        if (!categoryName || typeof categoryName !== 'string' || categoryName.length > 100) return [];
        const category = await Category.findOne({ where: { name: categoryName } }).catch(() => null);
        if (!category) return [];
        return Product.findAll({ where: { category_id: category.id } }).catch(() => []);
    }

    // 方法4：动态过滤with白名单
    static async filterProductsSafe(filters) {
        const allowed = { category_id: 'integer', status: 'string', price_min: 'decimal', price_max: 'decimal' };
        const where = {};

        for (const [key, value] of Object.entries(filters)) {
            if (!allowed[key] || !this.validateFilterValue(allowed[key], value)) continue;

            if (key === 'price_min') {
                where.price = { ...where.price, [sequelize.Op.gte]: value };
            } else if (key === 'price_max') {
                where.price = { ...where.price, [sequelize.Op.lte]: value };
            } else if (key === 'status' && ['active', 'inactive', 'pending'].includes(value)) {
                where.status = value;
            } else {
                where[key] = value;
            }
        }

        return Product.findAll({ where }).catch(() => []);
    }

    // 方法5：Knex.js参数化
    static async queryWithKnexSafe(categoryId, status) {
        if (!Number.isInteger(categoryId) || !['active', 'inactive'].includes(status)) return [];
        return knex('products')
            .where('category_id', categoryId)
            .where('status', status)
            .select('*')
            .catch(() => []);
    }

    // 方法6：TypeORM with参数化
    static async typeOrmQuerySafe(userId) {
        if (!Number.isInteger(userId) || userId <= 0) return [];
        return getConnection().query('SELECT * FROM orders WHERE user_id = $1', [userId])
            .catch(() => []);
    }

    static validateFilterValue(type, value) {
        switch (type) {
            case 'integer': return Number.isInteger(value) && value >= 0;
            case 'decimal': return typeof value === 'number' && value >= 0;
            case 'string': return typeof value === 'string' && 0 < value.length && value.length <= 100;
            default: return false;
        }
    }
}

module.exports = SecureOrmQueries;
```

## 修复优先级

1. **立即修复（当天）**：停止在raw()中拼接ORM查询结果
2. **快速修复（3天内）**：使用参数化的query()或改为ORM方法
3. **短期改善（1周内）**：审计所有raw()、query()的使用
4. **长期改进（1个月）**：尽量使用ORM方法，避免原生SQL
