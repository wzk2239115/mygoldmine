# Python 自定义 XOR 加密审计

## Details

### 典型代码特征
```python
# 场景1: 简单单字节 XOR "加密"
def xor_encrypt(data, key):
    return ''.join(chr(ord(c) ^ key) for c in data)

password_encrypted = xor_encrypt(password, 0x42)
db.save(user_id, password_encrypted)

# 场景2: 循环密钥 XOR
def xor_cipher(text, key):
    return bytes([text[i] ^ key[i % len(key)] for i in range(len(text))])

SECRET_KEY = b"mysecret"
encrypted_token = xor_cipher(token.encode(), SECRET_KEY)

# 场景3: Base64 包装 XOR（伪装加密）
import base64
def secure_encrypt(plaintext, key):
    xored = bytes([ord(plaintext[i]) ^ ord(key[i % len(key)]) 
                   for i in range(len(plaintext))])
    return base64.b64encode(xored).decode()

user.api_key = secure_encrypt(api_key, "static_key")

# 场景4: 配置文件加密
def encrypt_config(value):
    KEY = 0x5A
    return ''.join(chr(ord(c) ^ KEY) for c in value)

config = {
    'db_password': encrypt_config(DB_PASS),
    'api_secret': encrypt_config(API_SECRET)
}

# 场景5: 会话令牌 XOR 混淆
def generate_token(user_id, timestamp):
    raw = f"{user_id}:{timestamp}"
    key = os.urandom(8)  # 密钥随令牌传输
    encrypted = bytes([raw.encode()[i] ^ key[i % len(key)] 
                      for i in range(len(raw))])
    return base64.b64encode(key + encrypted).decode()

# 场景6: 多轮 XOR "强化"
def multi_xor(data, key):
    result = data
    for _ in range(100):
        result = bytes([result[i] ^ key[i % len(key)] 
                       for i in range(len(result))])
    return result  # 偶数轮抵消，完全可逆

# 场景7: JWT 自定义签名用 XOR
def sign_jwt(header, payload):
    SECRET = b"jwt_secret_key"
    data = f"{header}.{payload}".encode()
    signature = bytes([data[i] ^ SECRET[i % len(SECRET)] 
                      for i in range(len(data))])
    return base64.urlsafe_b64encode(signature).decode()

# 场景8: Django 中间件密码混淆
class PasswordObfuscationMiddleware:
    def process_request(self, request):
        if 'password' in request.POST:
            pwd = request.POST['password']
            request.POST['password'] = self.xor_obfuscate(pwd, b'\xAA')
    
    def xor_obfuscate(self, data, key):
        return bytes([ord(data[i]) ^ key[0] for i in range(len(data))])

# 场景9: Flask API 签名
from flask import request
@app.route('/api/data')
def api_handler():
    signature = request.headers.get('X-Signature')
    body = request.get_data()
    expected = xor_hash(body + API_KEY.encode())
    if signature != base64.b64encode(expected).decode():
        return "Invalid signature", 401

def xor_hash(data):
    h = 0x1234
    for b in data:
        h ^= b
    return h.to_bytes(2, 'big')

# 场景10: Pickle 序列化前 XOR
import pickle
def save_session(session_data):
    serialized = pickle.dumps(session_data)
    encrypted = bytes([serialized[i] ^ 0x7F for i in range(len(serialized))])
    with open('/tmp/session', 'wb') as f:
        f.write(encrypted)
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "\^" --include="*.py" | grep -E "ord|chr|byte"
grep -rn "ord.*\^.*chr\|chr.*\^.*ord" --include="*.py"
grep -rn "def.*encrypt.*xor\|def.*xor.*cipher" --include="*.py"
grep -rn "\.encode\(\).*\^.*\.encode\(\)" --include="*.py"
grep -rn "base64.*xor\|xor.*base64" --include="*.py" -i
grep -rn "for.*in.*range.*\^" --include="*.py"
grep -rn "SECRET.*=.*['\"].*['\"]" --include="*.py" | grep -i "xor\|key"
```

**高危 API 模式（L2 跳读）：**
- `chr(ord(c) ^ key)` 单字节/循环密钥 XOR
- `bytes([... ^ ...])` 列表推导式 XOR 操作
- `for i in range(len(text)): ... ^ key[i % len(key)]` 循环密钥模式
- `base64.b64encode(xored)` XOR 后 Base64 包装
- `^ 0x??` 固定魔数 XOR（如 `^ 0x5A` / `^ 0xFF`）
- 函数名包含 `encrypt` / `cipher` / `obfuscate` 但内部仅 XOR
- `pickle.dumps() + XOR` 序列化数据混淆
- JWT/Token 生成函数中出现 `^` 运算符
- `__xor__` / `operator.xor` 用于密码学场景
- 密码/Token 变量直接进入 XOR 函数

**函数调用链追踪（L3 逐行）：**
- 定位加密入口：`encrypt()` / `encode()` / `protect()` 函数实现
- 追踪密钥来源：硬编码字符串 / `os.urandom()` / 配置文件
- 检查存储路径：`db.execute(INSERT password=?)` / `redis.set()` / `pickle.dump()`
- 认证逻辑：`if decrypt(stored) == input` 比对位置
- Django Models：`EncryptedCharField` / `save()` / `pre_save` 信号
- Flask Blueprint：`before_request` / `after_request` 钩子中混淆逻辑
- Celery 任务：异步任务参数加密 `@task` 装饰器内部
- 配置加载：`settings.py` / `.env` 解析时解密逻辑
- ORM 加密字段：SQLAlchemy `TypeDecorator` / Django `Field.to_python()`
- Middleware 链：请求/响应中间件的数据转换

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码单字节密钥：`KEY = 0x42` / `KEY = ord('A')`
- 静态字符串密钥：`SECRET = "mysecret"` 无动态派生
- 密钥长度 <= 密文长度（循环密钥完全可频率分析）
- 密钥与密文一起传输/存储：`key + encrypted_data`
- Base64 包装无加盐/IV：`b64encode(xored)`
- 注释显示 "simple obfuscation" / "basic encryption"

**伪保护识别（L3 逐行）：**
```python
# 多轮 XOR 仍可逆（偶数轮抵消）
def strong_xor(data, key):
    for round in range(1000):
        data = xor(data, key)
    return data  # 1000 轮后等价于原始 XOR

# 加盐但密钥仍静态
import hashlib
def salted_xor(data, salt):
    STATIC_KEY = b"fixed_key"
    derived = hashlib.sha256(salt + STATIC_KEY).digest()
    return bytes([data[i] ^ derived[i % len(derived)] 
                 for i in range(len(data))])  # 盐可见则密钥可计算

# 误认为 XOR 两次增强安全
def double_xor(data):
    temp = xor(data, KEY1)
    return xor(temp, KEY2)  # 等价于 xor(data, KEY1 ^ KEY2)

# 随机密钥但存储在同一位置
def encrypt_with_random_key(data):
    key = os.urandom(16)
    encrypted = xor(data, key)
    db.save({'key': key, 'data': encrypted})  # 密钥密文同库

# 复杂包装但底层 XOR
class SecureCrypto:
    def encrypt(self, plaintext):
        # 多层函数调用
        intermediate = self._prepare(plaintext)
        processed = self._transform(intermediate)
        return self._finalize(processed)
    
    def _transform(self, data):
        return bytes([data[i] ^ self.key[i % len(self.key)] 
                     for i in range(len(data))])  # 核心仍是 XOR

# 配置可选但默认 XOR
CRYPTO_BACKEND = os.getenv('CRYPTO', 'xor')  # 默认弱算法
if CRYPTO_BACKEND == 'aes':
    cipher = AES.new(key, AES.MODE_GCM)
else:
    cipher = XORCipher(key)  # 降级到弱加密
```

**跨模块保护追踪（L4）：**
- Django 设置：`settings.ENCRYPTION_BACKEND` / `SECRET_KEY` 用法
- 环境变量：`.env` 中 `CRYPTO_METHOD=xor` / `ENCRYPTION_KEY=...`
- 依赖审计：`requirements.txt` 缺少 `cryptography` / `pycryptodome`
- 配置管理：`config.yaml` 中 `security.encryption: custom`
- 数据库 Schema：加密字段类型 `VARCHAR` 而非 `BYTEA`（Base64 暗示）
- Flask-Security：自定义 `PasswordHash` 实现类
- Celery 序列化：`CELERY_TASK_SERIALIZER` / `accept_content` 配置
- Redis 存储：`redis.set()` 值是否经过标准加密
- 日志审计：`logger.info("Using XOR encryption")` 警告信息
- Docker 镜像：`pip freeze` 输出缺少加密库
- API 文档：Swagger/OpenAPI 声称"加密传输"但实现用 XOR
- 单元测试：测试用例是否验证密钥管理安全性

## Classify

**确认漏洞：**
- 用户密码存储使用 XOR 加密（任何形式）
- 会话令牌/Cookie 签名基于 XOR
- JWT/JWS 使用 XOR 自定义签名算法
- API 密钥/访问凭证 XOR 混淆存储
- 数据库敏感字段（身份证/手机号/邮箱）XOR 加密
- 配置文件密码（DB/Redis/第三方服务）XOR 保护
- 支付签名/交易验证使用 XOR
- OAuth Token/Refresh Token 使用 XOR
- 加密密钥本身用 XOR 保护（KEK 弱加密）
- 文件加密（日志/备份）用于合规场景

**研判误报：**
- 单元测试/Fixtures 测试数据（`tests/` 目录）
- Mock 对象/Stub 实现（`unittest.mock` / `pytest`）
- 示例代码/文档字符串中演示（`doctest`）
- 已弃用函数明确标注 `@deprecated` 且无调用
- 教学材料（`examples/` / `tutorials/` 路径）
- 开发环境专用工具（`if DEBUG:` 分支）
- 性能基准测试对照组（`benchmark/` 目录）
- 第三方库内部实现（非项目代码直接调用）

**代码异味：**
- 配置可选 AES 但默认 XOR
- 注释 "临时方案 TODO: 替换为 AES" 无时间表
- 日志输出 "快速混淆，非生产环境使用" 但代码未隔离
- 函数名 `secure_encrypt()` 但实现为简单 XOR
- 新旧用户不同算法但无统一升级计划
- 性能理由选择 XOR（"XOR 最快"）
- 认为 "简单数据无需强加密"
- Base64 包装后声称"已加密"
- 多轮 XOR 误认为增强安全性

**关键判断点：**
1. 加密目标：测试数据/日志 vs 密码/密钥/PII
2. 密钥管理：动态派生/HSM vs 硬编码/配置文件
3. 安全边界：内网工具 vs 互联网暴露 API
4. 合规需求：等保 2.0 / GDPR / PCI DSS 是否适用
5. 对抗模型：是否需防御已知明文攻击/频率分析
6. 替代方案：系统是否有 AES-GCM / Fernet / NaCl 实现
7. 数据敏感度：公开信息 vs 用户隐私/金融数据

## Low risk

**可接受的低风险场景：**
- 非敏感日志脱敏（用户 ID 可逆映射用于内部调试）
- 临时内存缓存键扰动（进程内混淆，非持久化）
- 开发环境快速原型（`DEBUG=True` 且专网隔离）
- 一次性数据迁移脚本（历史数据格式转换）
- 内部工具临时混淆（运维脚本命令行参数）
- 性能测试负载生成（压测数据无真实价值）
- 代码混淆工具链（Python 字节码保护非加密用途）

**降级条件：**
- 数据已公开或极低敏感度（无隐私/金融价值）
- 短期过渡方案有明确迁移计划（Sprint 可查）
- 访问严格网络隔离（VPN + IP 白名单 + 防火墙）
- 仅向后兼容读取，新数据用 AES-256-GCM
- 攻击窗口极短（一次性令牌 < 60 秒 + 单次使用）
- 已有外层 TLS 1.3 保护（XOR 仅内部二次混淆）
- 攻击成本远高于资产价值（需量化评估）
- 明确标注非安全用途（代码注释 + 文档）

**注意：** XOR 加密完全可逆（`P ^ K ^ K = P`），循环密钥易受频率分析和已知明文攻击，单字节密钥仅 256 种可能可暴力破解。Base64 包装不增加任何安全性，多轮 XOR 偶数次等价于不加密。密钥与密文同存储/传输使加密无意义。Python 标准库 `cryptography.fernet` 提供对称加密（AES-128-CBC + HMAC），`pycryptodome` 支持 AES-GCM，应优先使用。任何涉及用户认证、PII、支付、合规（等保/GDPR/PCI DSS）的系统必须使用标准加密算法。低风险评级不代表长期可接受，需明确迁移路线图和责任人。