# JavaScript_BigInt_Overflow

**漏洞类型**: BigInt 操作溢出，使用 BigInt 类型时与普通整数类型转换的溢出风险

**JavaScript/TypeScript**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`Number(bigIntValue)`、`bigIntValue | 0`、`parseInt(bigIntValue.toString())`、`arr[BigInt(userInput)]`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描 BigInt 类型转换为 Number 的操作（`Number()`、位运算符、算术运算符与普通数字混用）。关注 BigInt 用作数组索引、循环边界、内存分配大小的情况。检查 BigInt 与 Number 混合运算。

- **保护机制定位技巧** (L2: 跳读)：查找范围验证（`if (bigInt > Number.MAX_SAFE_INTEGER)`、`if (bigInt < Number.MIN_SAFE_INTEGER)`），使用 `BigInt.asIntN/asUintN()` 显式截断，或避免将 BigInt 转为 Number 直接使用 BigInt 运算。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：BigInt 转 Number 无范围检查，转换结果参与关键运算（索引、内存分配、金额计算）
- **误报**：转换值在安全范围内（< 2^53 - 1）、仅用于日志或显示
- **代码异味**：BigInt 与 Number 混用，需追踪数据流确认影响

## Low risk

- BigInt 值明确在 Number.MAX_SAFE_INTEGER 范围内
- 使用 `BigInt.asIntN/asUintN()` 显式进行安全截断
- 转换前进行范围验证（`bigInt <= Number.MAX_SAFE_INTEGER`）
- 结果仅用于显示、日志或非关键计算
- 全程使用 BigInt 运算，不转为 Number

## 真实漏洞案例

**场景1：金融计算中的精度丢失**
```javascript
// 易报漏洞场景
const userBalance = BigInt(userInput);  // 用户输入的大额资金
const fee = Number(userBalance) * 0.01; // 转为Number后精度丢失
const finalBalance = userBalance - BigInt(Math.floor(fee)); // 计算结果错误
```
关键特征：①用户可控的 BigInt 转 Number；②参与金额计算；③无范围检查。此时构造 userInput > 2^53 即可导致费用计算错误。

**场景2：数组越界访问**
```javascript
// 真实漏洞
const dataArray = new Uint8Array(100);
const index = BigInt(userSuppliedLargeNumber);  // 可能远超2^53
const value = dataArray[Number(index)];  // 无溢出检查直接转换
```
关键特征：①BigInt 转 Number 作为数组索引；②无范围验证；③可导致越界读写。

**场景3：循环边界溢出**
```javascript
// 漏洞代码
let count = BigInt(externalCounter);
for(let i = 0; i < Number(count); i++) {  // count 超大时转换溢出
  processItem(i);
}
```

## 常见误报场景

**误报1：大数仅用于显示**
```javascript
// 无风险 - 仅转换为字符串显示
const largeNumber = BigInt(userInput);
console.log("余额：" + largeNumber.toString());
const displayText = String(Number(largeNumber));  // 仅用于UI显示，无关键计算
```
审计建议：确认结果确实仅用于日志、UI 展示，未参与后续计算。

**误报2：显式范围检查存在**
```javascript
// 无风险 - 有完整检查
const bigValue = BigInt(userInput);
if (bigValue <= BigInt(Number.MAX_SAFE_INTEGER) && bigValue >= BigInt(Number.MIN_SAFE_INTEGER)) {
  const safeNumber = Number(bigValue);
  return safeNumber * 100;
}
```
审计建议：验证 if 条件是否覆盖所有转换路径，确认无跳过检查的代码分支。

**误报3：常数范围内的 BigInt**
```javascript
// 无风险
const presetValues = {
  small: BigInt(123),
  medium: BigInt(999999),
  large: BigInt(Number.MAX_SAFE_INTEGER - 1)
};
const converted = Number(presetValues.small);  // 写死的安全值
```
审计建议：确认 BigInt 是否来自用户输入或外部可控源。

## 审计关键点速查

| 特征 | 判断 | 备注 |
|------|------|------|
| BigInt(用户输入) → Number() → 关键计算 | 真漏洞 | 必须有范围检查 |
| BigInt(常量) → Number() | 无风险 | 源头可控 |
| BigInt → 数组索引/内存分配，无检查 | 真漏洞 | 可导致越界 |
| BigInt → 日志/UI 显示 | 无风险 | 确认未参与计算 |
| 显式 `BigInt.asIntN(n, value)` 截断 | 无风险 | 已明确定义范围 |
| BigInt 混合位运算 `\|` `&` `^` | 高风险 | 自动转 Number，极易溢出 |

## 审计流程建议

1. **第一步**：定位所有 BigInt 转 Number 的操作点（正则：`Number\(.*BigInt\)|BigInt.*\|\s*0|parseInt\(.*BigInt`）
2. **第二步**：检查转换值来源（用户输入 = 高危；常量 = 无风险）
3. **第三步**：追踪转换后数据流（参与金额/索引计算 = 真漏洞；仅显示 = 无风险）
4. **第四步**：查看转换前是否有范围检查（`> Number.MAX_SAFE_INTEGER`）
5. **第五步**：验证是否使用 BigInt.asIntN/asUintN() 替代方案

