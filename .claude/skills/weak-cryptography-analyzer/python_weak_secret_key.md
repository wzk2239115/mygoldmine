# Python 弱密钥/硬编码密钥审计

## Details

### 典型代码特征
```python
# 场景1: AES 硬编码密钥
from Crypto.Cipher import AES
SECRET_KEY = b'1234567890123456'  # 硬编码 16 字节密钥
cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
encrypted = cipher.encrypt(user_password.encode().ljust(16))

# 场景2: Fernet 弱密钥
from cryptography.fernet import Fernet
# 固定密钥而非动态生成
FERNET_KEY = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='
f = Fernet(FERNET_KEY)
token = f.encrypt(api_secret.encode())

# 场景3: JWT 弱 secret
import jwt
JWT_SECRET = "secret123"  # 弱口令密钥
token = jwt.encode({'user_id': 123}, JWT_SECRET, algorithm='HS256')

# 场景4: HMAC 硬编码密钥
import hmac
import hashlib
API_KEY = b"static_api_key"
signature = hmac.new(API_KEY, message.encode(), hashlib.sha256).hexdigest()

# 场景5: 短密钥（不足推荐长度）
from Crypto.Cipher import AES
key = b'short'  # 仅 5 字节
cipher = AES.new(key.ljust(16, b'\x00'), AES.MODE_CBC, iv)  # 填充到 16 字节

# 场景6: 密钥从可预测源派生
import hashlib
key = hashlib.md5(b"appname").digest()  # 16 字节但可预测
cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

# 场景7: 配置文件硬编码
# config.py
ENCRYPTION_KEY = "MySecretKey123456"
SECRET_KEY = "django-insecure-hardcoded-key"

# settings.py (Django)
SECRET_KEY = 'hardcoded-key-for-production'  # 危险

# 场景8: 代码中直接定义
class CryptoManager:
    def __init__(self):
        self.master_key = b'\x01\x02\x03\x04' * 4  # 硬编码字节串
    
    def encrypt(self, data):
        cipher = AES.new(self.master_key, AES.MODE_ECB)
        return cipher.encrypt(data)

# 场景9: 环境变量默认值为弱密钥
SECRET_KEY = os.getenv('SECRET_KEY', 'default_weak_key')  # 危险的回退值

# 场景10: 从用户输入派生密钥（熵值不足）
password = input("Enter password: ")
key = hashlib.sha256(password.encode()).digest()  # 无盐、无 KDF

# 场景11: 固定盐值 KDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
STATIC_SALT = b'fixed_salt_12345'
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, 
                 salt=STATIC_SALT, iterations=100000)
key = kdf.derive(password.encode())  # 盐固定导致密钥可预测

# 场景12: 时间戳作为密钥
import time
key = str(int(time.time())).encode().ljust(16, b'0')  # 可暴力枚举

# 场景13: Flask session 弱密钥
app.config['SECRET_KEY'] = 'dev'  # 开发密钥用于生产
app.config['SECRET_KEY'] = '123456'

# 场景14: Celery 序列化密钥
app.conf.task_serializer_secret = b'celery_secret'

# 场景15: 数据库加密密钥表内硬编码
def get_encryption_key(user_id):
    # 所有用户共用同一密钥
    return b'global_encryption_key_2024'
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
# 硬编码密钥模式
grep -rn "SECRET_KEY\s*=\s*['\"]" --include="*.py" | grep -v "environ\|getenv"
grep -rn "KEY\s*=\s*b['\"]" --include="*.py"
grep -rn "AES\.new\|Fernet\|jwt\.encode" --include="*.py"
grep -rn "HMAC.*b['\"]" --include="*.py" -i

# 弱密钥标识符
grep -rn "secret.*=.*['\"].*123\|password\|admin\|test" --include="*.py" -i
grep -rn "KEY.*=.*['\"]dev\|debug\|default" --include="*.py" -i
grep -rn "ljust\|zfill.*\(16\|24\|32\)" --include="*.py"  # 密钥填充

# 配置文件密钥
grep -rn "SECRET_KEY" --include="settings.py" --include="config.py"
grep -rn "ENCRYPTION_KEY\|API_SECRET\|JWT_SECRET" --include="*.py"
```

**高危 API 模式（L2 跳读）：**
- `SECRET_KEY = b'...'` / `KEY = "..."` 硬编码字符串
- `AES.new(固定值, ...)` 密钥直接传入常量
- `Fernet(b'固定 Base64')` 非 `Fernet.generate_key()` 生成
- `jwt.encode(..., '简单字符串', ...)` JWT secret 过于简单
- `hmac.new(b'固定值', ...)` HMAC 密钥硬编码
- `key.ljust(16, b'\x00')` / `key.zfill(32)` 短密钥填充
- `hashlib.md5(...).digest()` 作为 AES 密钥（可预测）
- `os.getenv('KEY', '默认值')` 环境变量有弱默认值
- `config['SECRET_KEY'] = 'dev'` 配置文件直接赋值
- `key = password.encode()` 用户密码直接作密钥无 KDF
- `SALT = b'固定值'` PBKDF2/Scrypt 使用静态盐
- `time.time()` / `datetime.now()` 作为密钥源
- 密钥长度 < 16（AES-128）/ < 32（AES-256）
- `SECRET_KEY = '123456'` / `'admin'` / `'password'` 弱口令
- 注释 "# temporary key" / "# for testing" 但用于生产

**函数调用链追踪（L3 逐行）：**
- 定位密钥定义：全局变量 / 类属性 / 函数内部常量
- 追踪密钥来源：硬编码 / 配置文件 / 环境变量 / 数据库查询
- 检查密钥生成：`Fernet.generate_key()` / `os.urandom(32)` / KDF
- 加密目标识别：用户密码 / API 令牌 / 会话数据 / 配置信息
- Django: `settings.SECRET_KEY` 使用位置（CSRF / Session / Signing）
- Flask: `app.config['SECRET_KEY']` 会话签名 / `itsdangerous`
- FastAPI: `SECRET_KEY` 用于 JWT / OAuth2
- SQLAlchemy: 加密字段 `EncryptedType` 密钥管理
- Celery: `task_serializer_secret` / 任务签名密钥
- 配置加载：`.env` / `settings.py` / `config.yaml` 解析
- 密钥存储：数据库表 `config` / 缓存 Redis / 文件系统
- 密钥轮换：是否存在 `rotate_key()` / 版本化密钥管理

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 密钥直接硬编码在代码中（字符串字面量）
- 密钥长度不足：AES-128 < 16 字节 / AES-256 < 32 字节
- 弱口令密钥：`'123456'` / `'password'` / `'secret'` / `'admin'`
- 全局静态密钥所有用户/会话共用
- 配置文件明文密钥且版本控制未 `.gitignore`
- 环境变量有弱默认值：`os.getenv('KEY', 'default')`
- 无密钥派生函数（KDF）：密码直接作密钥
- 固定盐值 PBKDF2 / Scrypt
- 时间戳 / 序列号作为密钥源
- 注释中 "TODO: 替换为安全密钥" 无执行

**伪保护识别（L3 逐行）：**
```python
# Base64 编码≠安全
SECRET_KEY = base64.b64encode(b"weak_key")  # 仍是静态值

# MD5 派生密钥（可预测）
key = hashlib.md5(b"application_name").digest()

# 用户密码直接作密钥（无盐无 KDF）
key = hashlib.sha256(user_password.encode()).digest()

# 固定盐 PBKDF2
SALT = b'my_app_salt'
key = PBKDF2(password, SALT, 32, 100000)  # 盐固定

# 短密钥填充（熵值不足）
key = b'abc'
key = key.ljust(16, b'\x00')  # 实际熵值仅 3 字节

# 配置切换但默认不安全
USE_SECURE_KEY = False
key = secure_key if USE_SECURE_KEY else b'default_key'

# 密钥混淆但仍静态
def get_key():
    return bytes([0x12, 0x34, 0x56, 0x78] * 4)  # 硬编码字节

# 从代码逻辑派生（可逆向）
key = bytes([ord(c) ^ 0xAA for c in "MyApp"])  # 可计算

# 密钥分片存储但均硬编码
KEY_PART1 = b'part1'
KEY_PART2 = b'part2'
MASTER_KEY = KEY_PART1 + KEY_PART2  # 仍是静态值

# 环境变量但仓库中有 .env 文件
# .env (已提交到 Git)
SECRET_KEY=hardcoded_secret_in_repo

# 密钥加密密钥（KEK）也硬编码
MASTER_KEY = b'master_key_2024'
data_key = decrypt_with_master(encrypted_key, MASTER_KEY)
```

**跨模块保护追踪（L4）：**
- Git 历史：`git log -p | grep -i "secret_key"` 查找泄露密钥
- 配置管理：`.env` / `config.yaml` 是否在 `.gitignore`
- 环境变量：部署脚本 / Docker Compose / K8s ConfigMap
- 密钥管理服务：AWS KMS / Azure Key Vault / HashiCorp Vault 集成
- Django: `django-environ` / `python-decouple` 是否使用
- Flask: `app.config.from_envvar()` / `from_pyfile()` 配置加载
- 密钥轮换机制：是否存在密钥版本化 / 定期更新逻辑
- 日志审计：密钥是否被 `logger.info()` / `print()` 泄露
- 依赖审计：`requirements.txt` 是否包含 `cryptography` / `pycryptodome`
- CI/CD: GitLab Variables / GitHub Secrets / Jenkins Credentials
- 容器镜像：Dockerfile 中 `ENV SECRET_KEY=...` 硬编码
- 数据库：密钥表是否加密存储 / 访问控制
- 监控告警：密钥泄露检测（Trufflehog / GitGuardian）
- 文档记录：密钥管理策略 / 轮换周期文档
- 测试环境：测试密钥是否与生产环境隔离

## Classify

**确认漏洞：**
- 生产环境用户密码加密使用硬编码密钥
- JWT / API 令牌签名使用弱 secret（字典词汇、简单字符串）
- 会话管理密钥硬编码且所有用户共用
- 敏感配置加密（数据库密码、第三方 API 密钥）使用静态密钥
- 密钥长度不足推荐值（AES-128 < 16 字节、AES-256 < 32 字节）
- 密钥从可预测源派生（MD5 哈希、时间戳、序列号）
- 配置文件中明文密钥已提交到版本控制系统
- 所有环境（开发/测试/生产）共用同一密钥
- 密钥通过日志 / 错误消息对外泄露
- PBKDF2 / Scrypt 使用全局固定盐值

**研判误报：**
- 单元测试文件（`tests/` 目录）中的示例密钥
- 文档 / 教程 / 注释中的演示代码
- 已废弃函数标注 `@deprecated` 且无调用
- Mock 对象 / Stub 实现（`unittest.mock` / `pytest-mock`）
- 示例配置模板（`config.example.py` / `.env.example`）
- 开发环境专用代码（`if DEBUG:` 分支）
- 第三方库内部实现（`site-packages/` 非项目代码）
- 历史迁移脚本（一次性执行且已归档）

**代码异味：**
- 配置支持环境变量但有弱默认值
- 注释 "临时密钥" / "TODO: 生产环境替换" 无时间表
- 开发密钥（`SECRET_KEY='dev'`）出现在非开发环境
- 密钥管理策略混乱（部分用 KMS、部分硬编码）
- 函数名 `generate_key()` 实际返回固定值
- 密钥长度刚好达标但熵值不足（填充生成）
- 存在安全密钥但条件分支默认使用弱密钥
- 密钥轮换机制存在但从未执行
- 文档声称"密钥安全管理"实际硬编码
- 新旧系统密钥强度不一致无统一升级

**关键判断点：**
1. 密钥来源：动态生成 / KMS / 环境变量 vs 硬编码 / 配置文件
2. 密钥强度：CSPRNG / 足够长度 / 高熵值 vs 弱口令 / 短密钥 / 可预测
3. 密钥范围：每用户独立密钥 vs 全局共用密钥
4. 加密目标：敏感数据（密码/PII/支付）vs 非敏感数据（缓存/日志）
5. 环境隔离：开发/测试/生产密钥独立 vs 共用密钥
6. 版本控制：密钥在 `.gitignore` vs 已提交到仓库
7. 密钥轮换：定期更新机制 vs 从未变更
8. 泄露风险：密钥在日志/错误/公开文档中暴露
9. 合规要求：PCI DSS / GDPR / 等保 2.0 密钥管理标准
10. 对抗模型：是否需防御密钥暴力破解 / 预测攻击

## Low risk

**可接受的低风险场景：**
- 开发环境本地测试（明确标注 `DEBUG=True` 且网络隔离）
- 非敏感数据混淆（内部日志 ID、缓存键生成）
- 一次性数据迁移脚本（历史数据格式转换后废弃）
- 性能测试负载数据（无真实用户信息）
- 内部工具临时加密（运维脚本、短期有效）
- 示例配置模板（`.env.example` 明确标注示例）
- 教学/演示代码（文档、教程、培训材料）

**降级条件：**
- 数据敏感度极低（公开信息、已脱敏数据）
- 短期过渡方案有明确迁移计划（Sprint 可追踪）
- 访问严格隔离（VPN + 防火墙 + 网络分段）
- 仅向后兼容读取，新数据使用安全密钥
- 多层防护（外层 TLS 1.3 + 内层加密 + WAF）
- 密钥轮换周期极短（< 24 小时自动更新）
- 攻击成本远高于资产价值（需量化评估）
- 监控告警完善（密钥使用审计 + 异常检测）
- 已记录风险并获得安全评审豁免

**注意：** 硬编码密钥是 OWASP Top 10（A02:2021 Cryptographic Failures）关键风险。Python 应使用 `secrets` 模块生成密钥（`secrets.token_bytes(32)`），通过环境变量 / KMS / Vault 管理，避免提交到版本控制。Django `SECRET_KEY` 泄露可导致会话伪造、CSRF 绕过、签名伪造。JWT 弱 secret 可暴力破解（`hashcat` / `john`）伪造令牌。密钥长度应符合标准：AES-128（16 字节）/ AES-256（32 字节）/ HMAC-SHA256（≥32 字节）。使用 PBKDF2 / Scrypt / Argon2 从密码派生密钥时必须使用随机盐且足够迭代次数。密钥应定期轮换并支持多版本共存（密钥 ID + 版本号）。涉及 PCI DSS（支付）/ HIPAA（医疗）/ GDPR（隐私）的系统必须使用 HSM / KMS 管理密钥。低风险评级不代表可长期接受，需明确迁移时间表和责任人。