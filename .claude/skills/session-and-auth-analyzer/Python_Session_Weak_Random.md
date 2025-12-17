# Python_Session_Weak_Random

**漏洞类型**: Flask/Django 会话令牌使用弱随机数生成器，熵值不足，导致会话令牌可被预测或枚举

---

## Details

### 代码示例

```python
import random
def weak_token():
    return ''.join([random.choice('0123456789abcdef') for _ in range(32)])

# 使用 random 而非 secrets，不安全
app.secret_key = 'password123'  # 过弱的密钥

import uuid
def unsafe_session():
    return str(uuid.uuid4())  # uuid.uuid4() 使用 random.random()

# 应使用密码学安全的随机: secrets.token_hex()
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `random.choice()`, `random.random()`, `uuid.uuid4()`
- `secrets.token_hex()`, `os.urandom()`
- `SECRET_KEY` 配置
- 令牌生成函数

**L2 跳读定位**:
- 会话初始化代码
- 令牌生成函数实现
- 配置文件中的密钥设置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `secrets` 模块使用
- `os.urandom()` >= 16 字节
- 强密钥从环境读取

**L3 逐行分析**:
- 使用 `secrets.token_hex()` 而非 `random`
- `SECRET_KEY` 长度 >= 32 字符
- 密钥从环境变量读取

**L4 跨模块追踪**:
- 所有随机数生成位置
- 密钥管理和轮换机制

---

## Classify

确认为漏洞: 使用 `random` 模块，密钥过弱或过短
误报判定: 使用 `secrets`，密钥足够强
代码异味: 混合使用安全和不安全的方式

---

## Low risk

- 虽然令牌弱但有额外验证机制
- 会话超时极短
- 实时监控异常活动
