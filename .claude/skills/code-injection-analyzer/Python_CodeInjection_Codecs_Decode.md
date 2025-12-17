# Python codecs.decode() 代码执行

**漏洞成因**：使用 `codecs.decode()` 或特定的编码解码器（如 `rot_13` 的转义、某些自定义编码器）来处理用户输入，某些编码器（特别是已弃用的 `pickle_encode`、`dill_encode` 等）可在解码过程中执行代码。攻击者可通过构造恶意编码数据来执行任意代码。

---

## Details

**代码示例**：
```python
# 危险：使用 codecs.decode() 与不安全的编码
import codecs
user_data = request.form.get('data')
decoded = codecs.decode(user_data, 'utf-8')  # 某些自定义编码可能不安全

# 危险：使用可执行的编码器（如已弃用的编码）
# 这些在某些 Python 版本或第三方库中可能导致代码执行
result = codecs.decode(user_input, 'python_eval')

# 危险：字符串拼接构造编码器名称
encoding = 'utf-' + user_input  # 可能指向危险编码
decoded = codecs.decode(data, encoding)

# 相对安全：使用标准编码
safe = codecs.decode(user_data, 'utf-8', errors='ignore')
```

**快速定位核心操作**（L1-L2）：
- 关键词：`codecs.decode(`、`codecs.encode(`、`.decode()`、`.encode(`
- 查看编码器名称是否来自用户输入：直接参数或拼接
- 检查使用的编码器类型：标准编码（utf-8、ascii）vs 自定义编码
- 追踪数据流：`request.form`、`request.args`、数据库、文件

**快速定位保护机制**（L2-L3）：
- 是否限制了编码器列表：白名单包含仅允许的标准编码
- 是否使用了标准编码器：utf-8、ascii、base64 等
- 是否禁止了自定义编码器、已弃用编码器的使用
- 是否对编码器名称进行了验证：正则匹配、枚举检查

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速定位 codecs 调用和编码器使用
- **L2**：跳读确认编码器来源、是否为标准编码
- **L3**：逐行读取编码器选择逻辑、防护机制

---

## Classify

**确认为漏洞**：
- 编码器名称来自用户可控输入
- 使用了已弃用的、自定义的或有执行能力的编码器
- 无白名单限制或白名单不完整

**误报**：
- 仅使用标准编码器（utf-8、ascii、base64、hex）
- 编码器名称为硬编码常量
- 编码器名称来自受信任源（配置文件、服务器本地）

**代码异味**：
- 使用 codecs 但有部分防护（需评估白名单完整性）
- 权限控制依赖前端验证
- 业务可用标准库函数替代（如 base64.b64decode）

---

## Low Risk

以下情况可评为低风险：
- **仅使用标准编码**：严格限制使用 utf-8、ascii、base64、hex 等标准编码
- **权限隔离**：编码操作在最小权限用户下执行
- **内网保护**：仅限管理员、开发者、内网访问
- **编码器白名单**：严格枚举允许的编码器列表
- **审计监控**：所有编码操作被完整记录、监控
