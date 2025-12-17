# C_Amount_BufferOverflow

## Details

**核心漏洞特征**：C应用中处理金额数据时发生缓冲区溢出，导致内存破坏或代码执行。

**代码示例定位**：查找缓冲区操作代码，关键词包括 `strcpy`, `strcat`, `sprintf`, `gets`, `scanf` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `strcpy(buffer, amount_str)` - 危险函数
- 搜索 `sprintf()` - 检查格式化字符串风险
- 搜索 `scanf()` 和 `gets()` - 无界输入
- 搜索缓冲区大小声明 - 检查是否足够

**快速定位保护机制**（L2: 跳读）：
- 检查是否使用 `strncpy`, `strncat` 等安全函数
- 检查是否有输入长度检查
- 检查是否有缓冲区大小检查
- 检查是否使用canary或ASan

## Classify

**漏洞判定标准**：
- 使用不安全函数（strcpy、gets） → **漏洞**
- 无缓冲区长度检查 → **漏洞**
- 输入未验证大小 → **漏洞**
- sprintf无大小限制 → **漏洞**

**误报情况**：
- 使用strncpy和strncat → 低风险
- 有长度检查 → 低风险
- 使用安全库 → 低风险

**代码异味**：
- 虽有检查但逻辑有缺陷 → 审计
- 检查不一致 → 审计

## Low risk

**低风险评级条件**：
1. **安全函数**：使用strncpy、strncat而非strcpy、strcat
2. **长度检查**：所有输入都检查长度
3. **格式字符串**：sprintf使用snprintf限制大小
4. **栈检查**：编译时启用栈溢出检测
5. **动态分析**：使用AddressSanitizer检查