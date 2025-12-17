# Java_AmountCalculation_FloatPrecision

## Details

**核心漏洞特征**：Java应用中使用float或double计算金额，导致精度丧失和计算错误。

**代码示例定位**：查找金额计算代码，关键词包括 `double`, `float`, `amount`, `price`, `BigDecimal` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `double amount =` 或 `float price =` - 检查数据类型
- 搜索 `amount +` 或 `amount *` - 检查算术运算
- 搜索 `new BigDecimal()` - 检查是否使用Decimal
- 搜索金额字段声明 - 检查类型

**快速定位保护机制**（L2: 跳读）：
- 检查是否使用BigDecimal
- 检查金额存储为整数（分为单位）
- 检查数据库字段类型为DECIMAL
- 检查转换逻辑

## Classify

**漏洞判定标准**：
- 使用float或double表示金额 → **漏洞**
- 浮点计算未转为Decimal → **漏洞**
- 数据库使用FLOAT类型 → **漏洞**
- 无精度处理 → **漏洞**

**误报情况**：
- 使用BigDecimal → 低风险
- 整数表示（分为单位） → 低风险
- 数据库DECIMAL类型 → 低风险

**代码异味**：
- 虽用BigDecimal但转换错误 → 审计
- 混合使用double和BigDecimal → 审计

## Low risk

**低风险评级条件**：
1. **类型选择**：使用BigDecimal或long整数
2. **单位统一**：全局使用分为单位的整数
3. **转换正确**：BigDecimal构造使用String不用double
4. **数据库类型**：金额字段使用DECIMAL而非FLOAT
5. **舍入模式**：明确指定舍入方式（ROUND_HALF_UP）