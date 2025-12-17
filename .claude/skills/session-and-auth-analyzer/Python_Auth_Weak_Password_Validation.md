# Python_Auth_Weak_Password_Validation

**漏洞类型**: Django 认证中密码验证逻辑存在缺陷，允许弱密码或空密码通过验证

---

## Details

### 代码示例

```python
def validate_password(password):
    if password == "" or password is None:
        return True  # 允许空密码
    return len(password) >= 6  # 长度过短

# 应该使用 Django 的验证器:
from django.contrib.auth.password_validation import validate_password
validate_password(password, user)
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `validate_password()`, `check_password()`
- 空值检查缺失
- 最小长度检查过弱

**L2 跳读定位**:
- 密码验证函数
- 用户创建和修改逻辑

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 使用 Django 的内置验证器
- 强度要求检查

**L3 逐行分析**:
- 非空检查
- 最小长度 >= 12
- 复杂性要求 (大小写、数字、特殊字符)

---

## Classify

确认为漏洞: 允许弱密码或空密码
误报判定: 使用标准验证器
代码异味: 自定义弱验证逻辑

---

## Low risk

- 虽可使用弱密码但有其他防护
- 速率限制和登录尝试限制
