# Python_Business_Logic_Overflow

**漏洞类型**: 业务逻辑计数器溢出，金额计算、积分累计等业务逻辑未检查溢出

**Python**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`total_amount += price * quantity`、`user.balance += points`、`counter += 1`、`Decimal(amount1) + Decimal(amount2)`

### 核心定位与扫描技巧

#### L2级别：快速扫描（跳读）
- 重点搜索关键字：`+=`、`*=`、`balance`、`amount`、`total`、`count`、`score`、`points`
- 金融相关操作：转账、充值、消费、积分累计、手续费计算
- 库存相关：`inventory -= quantity`、库存扣减、批量操作
- 计数器场景：登录次数、操作次数、调用限流计数
- 确认数据源：用户输入、API参数、数据库字段初值

#### L3级别：深入审计（逐行读）
- **变量来源追溯**：参数是否校验 (0 <= value <= MAX)、用户可控性
- **操作前检查**：`if balance + amount > MAX_BALANCE` 是否存在、边界条件测试
- **数据类型链路**：输入 → 计算 → 存储的全流程类型确认（float → Decimal → INT）
- **并发问题**：多线程/异步环境下累加操作是否有锁/原子性保证
- **数据库交互**：INSERT/UPDATE 语句直接使用计算结果、是否有二次验证

### 真实漏洞特征识别

#### 典型漏洞场景
1. **浮点精度丢失**：`balance = balance + 0.1 + 0.2`，最终存储时 balance != 0.3
2. **类型转换溢出**：Python int 传入 C 扩展库，隐式截断为 32 位
3. **无上限累加**：积分系统 `user.score += reward`，用户通过业务逻辑缺陷无限加分
4. **混合类型计算**：`Decimal(amount) + float_discount`，Decimal 转为 float 丧失精度
5. **并发竞态**：多个请求同时修改 balance，最后修改胜出导致数据不一致
6. **数据库字段类型不匹配**：Python 计算为 BIGINT 范围，但 MySQL 字段定义为 INT(11)

#### 易被忽略的风险点
- 使用 `float` 进行百分比、汇率、折扣计算：`final_price = price * discount_rate`
- 多步骤累加，每步都有精度损失：`total += item.price * item.quantity` 循环中进行
- 来自 JSON/CSV 的数据自动转为 float：`amount = float(request.json['amount'])`
- 数据库触发器或存储过程二次计算，与应用层逻辑不一致

## Classify

### 判断漏洞 vs 误报的核心要点

#### 确定真实漏洞（High Confidence）
✗ 使用 `float` 进行金额计算（`0.1 + 0.2 != 0.3` 问题）
✗ 累加操作无上限检查，用户可控输入导致业务金额溢出
✗ 数据库字段类型过小：INT 存储期望为 BIGINT 的累加结果
✗ 类型隐式转换导致精度丢失：字符串 → float → 存储
✗ 并发场景下 read-modify-write 无原子性保证
✗ 金额计算与数据库验证逻辑不一致，存在绕过可能

#### 排除误报（False Positive）
✓ 使用 `Decimal` 或整数（分为单位）进行金额计算
✓ 数据库字段类型充足且匹配（DECIMAL(19,2) / BIGINT）
✓ 有明确的业务上限检查 `if new_balance > MAX_BALANCE: raise`
✓ 使用数据库约束强制类型和范围：`CHECK(balance >= 0)`
✓ 操作在数据库事务中完成，配合乐观锁或悲观锁
✓ 定期对账机制确保应用层与数据库数据一致性

#### 代码异味需深度评估
⚠ 金额计算使用浮点数但后续转 Decimal 时已丧失精度
⚠ 整数计算结果作为百分比：`price = int(base_price * 0.9)`，1 元时变 0 元
⚠ 多币种/汇率转换中丧失精度
⚠ 定时任务中的批量累加操作，缺少中间结果验证

## Low risk

- 金额计算全流程使用 `decimal.Decimal` 或整数（以分为单位）
- 数据库字段类型明确：DECIMAL(19,4)、BIGINT，与业务范围匹配
- 业务逻辑中有明确的上限检查：`if new_total > business_max_limit`
- 使用数据库约束强制数据完整性：`NOT NULL`、`CHECK`、`DEFAULT`
- 并发操作通过数据库锁或乐观锁保证一致性
- 定期与账务系统对账，差异告警机制
- 事务隔离级别合适，防止脏读和幻读
- 操作日志完整，便于问题追溯和数据恢复

---

## 审计案例对比

### 案例1：真实漏洞 - 积分累加无上限
```python
# 脆弱代码
def add_points(user_id, points):
    user = User.query.get(user_id)
    user.score += points  # 无上限检查
    db.session.commit()
```
**审计要点**：
- points 参数来自用户输入/API，未校验范围
- score 字段无 CHECK 约束
- 累加后超过 INT 范围或业务预期金额上限
- 无操作日志记录，无法追溯异常积分来源

### 案例2：误报 - 已通过防护的积分系统
```python
from decimal import Decimal
def add_points(user_id, points):
    points = Decimal(str(points))  # 字符串转 Decimal 避免精度丢失
    if points < 0 or points > 10000:
        raise ValueError("Invalid points")
    user = User.query.get(user_id)
    if user.score + points > 1000000:  # 业务上限
        raise ValueError("Score exceeds maximum")
    user.score += points
    db.session.commit()
```
**审计结论**：低风险，存在足够防护

### 案例3：隐蔽漏洞 - 库存扣减竞态
```python
# 脆弱代码（无锁或事务隔离不足）
def purchase(order_id, quantity):
    item = Inventory.query.get(product_id)
    if item.stock >= quantity:  # 检查点
        item.stock -= quantity  # 执行点（检查与执行间有时间窗口）
        db.session.commit()
```
**审计要点**：
- 并发环境下，多个请求可能同时通过检查但都执行扣减
- 需使用 `SELECT ... FOR UPDATE` 或版本号乐观锁
- 最终库存可能为负数

### 案例4：漂浮精度陷阱 - 折扣计算
```python
# 脆弱代码
def apply_discount(price, discount_rate):
    return price * discount_rate  # float 精度问题
```
**修复对比**：
```python
# 正确做法
from decimal import Decimal
def apply_discount(price_cents, discount_rate):
    price = Decimal(price_cents) / 100  # 分单位
    discount = Decimal(str(discount_rate))
    return int((price * discount) * 100)
```

---

## 审计速查表

| 检查项 | 高风险特征 | 低风险特征 |
|------|---------|---------|
| 数据类型 | float, int 混用 | Decimal, int(分) 统一 |
| 参数验证 | 无范围检查 | if 0 <= val <= MAX |
| 数据库 | INT/TINYINT | BIGINT/DECIMAL |
| 并发 | 无锁/无版本号 | 悲观锁/乐观锁 |
| 日志 | 无记录 | 完整操作审计日志 |
| 对账 | 无 | 定期与账务系统对账 |

---

## 高效审计流程

1. **5秒快扫**：grep `+=\|*=\|balance\|amount` 定位操作点
2. **30秒类型检查**：确认计算全链路（输入→处理→存储）的数据类型
3. **1分钟校验检查**：寻找上限判断 `if xxx > MAX` 或数据库约束
4. **2分钟并发检查**：确认并发场景下是否有保护（锁/版本号）
5. **深度评估**：可疑点进行人工代码走读或动态测试

