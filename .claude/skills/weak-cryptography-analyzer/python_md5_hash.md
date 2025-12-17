# Python MD5 哈希弱密码学审计

## Details

### 典型代码特征
```python
# 场景1: hashlib.md5() 直接哈希密码
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()
db.execute("INSERT INTO users (password) VALUES (?)", (password_hash,))

# 场景2: 密码验证比对
stored_hash = user.password
input_hash = hashlib.md5(input_password.encode()).hexdigest()
if input_hash == stored_hash:
    login_success()

# 场景3: 加盐但仍用 MD5
import hashlib
SALT = "static_salt_value"
hash_obj = hashlib.md5((password + SALT).encode())
hashed = hash_obj.hexdigest()

# 场景4: 动态盐仍用 MD5
import uuid, hashlib
salt = uuid.uuid4().hex
password_hash = hashlib.md5((password + salt).encode()).hexdigest()
db.save({'hash': password_hash, 'salt': salt})

# 场景5: 多轮迭代 MD5
import hashlib
def hash_password(pwd, iterations=1000):
    result = pwd
    for _ in range(iterations):
        result = hashlib.md5(result.encode()).hexdigest()
    return result

# 场景6: Django 自定义 Hasher
from django.contrib.auth.hashers import BasePasswordHasher
class MD5PasswordHasher(BasePasswordHasher):
    algorithm = "md5"
    def encode(self, password, salt):
        hash = hashlib.md5((salt + password).encode()).hexdigest()
        return f"md5${salt}${hash}"

# 场景7: Flask-Login 密码处理
from flask_login import UserMixin
class User(UserMixin):
    def set_password(self, password):
        self.password_hash = hashlib.md5(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password_hash == hashlib.md5(password.encode()).hexdigest()

# 场景8: 会话令牌生成
import hashlib, time
def generate_session_token(user_id):
    raw = f"{user_id}:{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()

# 场景9: API 签名验证
import hashlib
def verify_signature(params, signature, secret_key):
    raw = ''.join(f"{k}{v}" for k, v in sorted(params.items()))
    expected = hashlib.md5((raw + secret_key).encode()).hexdigest()
    return signature == expected

# 场景10: JWT 自定义签名
import hashlib, base64, json
def create_jwt(payload, secret):
    header = base64.b64encode(json.dumps({"alg": "MD5"}).encode())
    body = base64.b64encode(json.dumps(payload).encode())
    signature = hashlib.md5(f"{header}.{body}.{secret}".encode()).hexdigest()
    return f"{header}.{body}.{signature}"

# 场景11: 配置文件加密密钥派生
import hashlib
def derive_key(master_password):
    return hashlib.md5(master_password.encode()).digest()[:16]  # AES-128 密钥

# 场景12: ORM Model 自动哈希
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
class User(Base):
    password = Column(String(32))
    
    def set_password(self, pwd):
        self.password = hashlib.md5(pwd.encode()).hexdigest()

# 场景13: 工具函数封装
def secure_hash(data):
    """安全哈希函数"""
    return hashlib.md5(data.encode()).hexdigest()  # 名不副实

# 场景14: FastAPI 依赖注入密码验证
from fastapi import Depends, HTTPException
def verify_password(plain: str, hashed: str):
    if hashlib.md5(plain.encode()).hexdigest() != hashed:
        raise HTTPException(status_code=401)

# 场景15: Celery 任务队列令牌
from celery import Task
class SecureTask(Task):
    def generate_task_id(self, args):
        raw = str(args) + str(time.time())
        return hashlib.md5(raw.encode()).hexdigest()

# 场景16: HMAC-MD5 仍是弱算法
import hmac, hashlib
signature = hmac.new(secret_key.encode(), message.encode(), hashlib.md5).hexdigest()

# 场景17: 密码重置令牌
import hashlib, secrets
def generate_reset_token(user_id, email):
    nonce = secrets.token_hex(8)
    raw = f"{user_id}:{email}:{nonce}"
    return hashlib.md5(raw.encode()).hexdigest()

# 场景18: SHA-1 作为"升级"方案
def upgrade_hash(password):
    # 从 MD5 升级到 SHA-1（仍不安全）
    return hashlib.sha1(password.encode()).hexdigest()

# 场景19: 组合哈希算法
def strong_hash(password):
    md5_hash = hashlib.md5(password.encode()).hexdigest()
    return hashlib.sha1(md5_hash.encode()).hexdigest()  # 组合仍弱

# 场景20: Pickle 序列化密钥保护
import pickle, hashlib
def save_credentials(username, password):
    data = {'user': username, 'pwd': hashlib.md5(password.encode()).hexdigest()}
    with open('creds.pkl', 'wb') as f:
        pickle.dump(data, f)
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "hashlib\.md5\|hashlib\.sha1" --include="*.py"
grep -rn "import.*md5\|from.*md5" --include="*.py"
grep -rn "\.hexdigest()\|\.digest()" --include="*.py" | grep -i "password\|token\|secret"
grep -rn "hmac\.new.*hashlib\.md5" --include="*.py"
grep -rn "algorithm.*=.*['\"]md5['\"]" --include="*.py"
grep -rn "PASSWORD_HASHERS.*MD5" --include="settings.py"
grep -rn "hashlib\.(sha1|md5)\(.*password" --include="*.py"
```

**高危 API 模式（L2 跳读）：**
- `hashlib.md5(password.encode())` 密码直接哈希
- `hashlib.md5(...).hexdigest()` 32 位十六进制输出
- `hashlib.md5(...).digest()` 16 字节二进制输出
- `hashlib.sha1(password.encode())` SHA-1 同样不安全
- `hmac.new(key, msg, hashlib.md5)` HMAC-MD5 弱签名
- `hashlib.md5((pwd + salt).encode())` 加盐仍弱
- `algorithm = "md5"` Django Hasher 配置
- `for _ in range(N): md5(...)` 迭代不弥补弱点
- `hashlib.new('md5', data)` 动态指定算法
- 魔数：32 字符十六进制（MD5）/ 40 字符（SHA-1）
- 数据库字段：`VARCHAR(32)` / `CHAR(32)` 暗示 MD5
- 函数命名：`hash_password` / `secure_hash` 但实现用 MD5

**函数调用链追踪（L3 逐行）：**
- 定位哈希入口：`set_password()` / `hash_password()` / `encrypt()` 函数实现
- 参数来源追踪：`request.form['password']` / `input()` / `sys.argv`
- Django Models：`User.set_password()` / `pre_save` / `post_init` 信号
- Flask Blueprint：`@bp.route('/register')` 注册路由密码处理
- FastAPI 路由：`@app.post('/login')` 登录验证逻辑
- SQLAlchemy 事件：`@event.listens_for` 监听器
- Django 配置：`settings.PASSWORD_HASHERS` 列表顺序
- 自定义中间件：`process_request()` / `process_view()` 密码拦截
- Celery 任务：`@app.task` 异步密码处理
- 工具模块：`utils/crypto.py` / `helpers/security.py`
- 第三方集成：OAuth Provider / LDAP Bind / RADIUS 认证
- 配置文件：`config.py` / `.env` 中 `HASH_METHOD=md5`
- 数据库迁移：`migrations/` 中初始密码字段定义
- 测试文件（排除）：`tests/` / `test_*.py` / `*_test.py`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 单次哈希无加盐：`hashlib.md5(pwd.encode()).hexdigest()`
- 静态盐硬编码：`SALT = "fixed_value"`
- 无密钥派生函数（KDF）：缺少 `pbkdf2` / `bcrypt` / `argon2`
- 直接比较哈希：`hash1 == hash2`（应用 `hmac.compare_digest()`）
- 数据库字段长度 32：`password VARCHAR(32)` 暗示 MD5
- 迭代次数不足：`iterations < 10000`
- 注释标注"临时方案"无迁移计划
- 配置默认 MD5：`PASSWORD_HASHERS[0]` 为 MD5 Hasher

**伪保护识别（L3 逐行）：**
```python
# 加盐但 GPU 仍可破解
import hashlib, secrets
salt = secrets.token_hex(16)
hash_val = hashlib.md5((password + salt).encode()).hexdigest()
# MD5 速度快，彩虹表可预计算

# 多轮迭代不足
def hash_with_rounds(pwd, rounds=100):
    result = pwd
    for _ in range(rounds):
        result = hashlib.md5(result.encode()).hexdigest()
    return result  # 应 >= 100000 轮且用 PBKDF2

# HMAC-MD5 仍是弱算法
import hmac, hashlib
hmac_hash = hmac.new(key.encode(), pwd.encode(), hashlib.md5).hexdigest()
# HMAC 无法修复 MD5 碰撞脆弱性

# SHA-1 作为升级方案
def migrate_hash(old_md5_hash, password):
    if len(old_md5_hash) == 32:  # 检测 MD5
        return hashlib.sha1(password.encode()).hexdigest()  # 仍弱
    return old_md5_hash

# Base64 编码误认为增强
import base64, hashlib
encoded = base64.b64encode(hashlib.md5(pwd.encode()).digest())
# 编码不等于加密

# 组合哈希仍弱
combo = hashlib.sha1(hashlib.md5(pwd.encode()).hexdigest().encode()).hexdigest()
# 组合不弥补单一算法弱点

# 降级兼容逻辑
try:
    from passlib.hash import bcrypt
    hash_val = bcrypt.hash(password)
except ImportError:
    hash_val = hashlib.md5(password.encode()).hexdigest()  # 危险降级

# 多层封装但底层 MD5
class SecurityModule:
    @staticmethod
    def hash(data):
        return SecurityModule._internal_hash(data)
    
    @staticmethod
    def _internal_hash(data):
        return hashlib.md5(data.encode()).hexdigest()  # 隐藏实现

# 条件分支存在 MD5 路径
if USE_LEGACY_AUTH:
    user.password = hashlib.md5(password.encode()).hexdigest()
else:
    user.password = bcrypt.hash(password)  # 旧用户仍用 MD5
```

**跨模块保护追踪（L4）：**
- Django：`settings.PASSWORD_HASHERS` 配置优先级 / `check_password()` 底层
- Flask：`flask_bcrypt` / `werkzeug.security` 扩展使用情况
- FastAPI：`passlib[bcrypt]` / `python-jose` 依赖检查
- SQLAlchemy：自定义 `TypeDecorator` / Hybrid Property 实现
- Pydantic：`SecretStr` / Validator 密码字段处理
- 环境变量：`.env` 中 `HASH_ALGORITHM=md5` / `USE_BCRYPT=false`
- 依赖审计：`requirements.txt` / `Pipfile` 缺少 `bcrypt` / `argon2-cffi`
- Docker 镜像：`python:3.6` 旧版本默认行为
- CI/CD 配置：环境变量注入 / Secrets 管理
- 数据库审计：`information_schema` 字段长度查询
- 日志分析：`grep "MD5 hash" logs/` 查找警告
- 静态分析：`bandit` / `semgrep` 规则配置
- API Gateway：Kong / Nginx 上游认证插件
- 消息队列：RabbitMQ / Kafka 认证机制
- 缓存层：Redis Session 存储格式
- 监控系统：Prometheus 指标 `auth_method{type="md5"}`
- 第三方集成：LDAP / SAML / OAuth Provider 密码同步

## Classify

**确认漏洞：**
- 用户密码存储使用 MD5/SHA-1（无论是否加盐、迭代）
- 管理员/超级用户密码用 MD5 哈希
- API 密钥/访问令牌生成使用 MD5
- JWT/JWS 签名算法使用 MD5 / HMAC-MD5
- 会话令牌/CSRF Token 用 MD5 生成（无 CSPRNG）
- OAuth 授权码/刷新令牌使用 MD5
- 支付签名验证（支付宝/微信支付/银行网关）使用 MD5
- 密码重置令牌/邮箱验证码用 MD5
- 数据库敏感字段索引哈希（身份证/手机号）
- 双因素认证 TOTP 密钥派生用 MD5
- 加密密钥 KEK/DEK 派生使用 MD5
- 数字签名证书指纹计算用 MD5
- 生产环境强制 MD5 且无替代方案

**研判误报：**
- 单元测试文件（`tests/` / `test_*.py` / `*_test.py`）
- Mock 对象 / 测试夹具（`unittest.mock` / `pytest.fixture`）
- 示例代码 / 文档字符串（`examples/` / `docs/`）
- 已弃用函数标注 `@deprecated` 且无调用链
- 注释代码 / 历史遗留（`# TODO: remove`）
- 性能基准测试对照组（`benchmarks/` 目录）
- 第三方库内部（`site-packages/` / `venv/`）
- 条件永不满足：`if False:` / `if sys.version_info < (2, 0):`
- IDE 生成模板代码未实际使用

**代码异味：**
- 配置可选 `bcrypt` 但默认 `md5`
- 注释 "TODO: 迁移到 bcrypt" 无时间表无责任人
- 日志警告 "Using MD5 for legacy users" 无升级计划
- SHA-1 作为 MD5 的"升级"方案
- 算法优先级：`md5 > sha1 > sha256 > bcrypt`
- 性能理由选择 MD5（"bcrypt 太慢"）
- 算法白名单包含 `['md5', 'sha1', 'pbkdf2_sha1']`
- 新老用户不同算法但无统一升级
- 文档声称"密码加密存储"实际哈希无盐
- 功能开关 `USE_SECURE_HASH=False` 默认关闭
- 多环境配置不一致（开发用 bcrypt / 生产用 md5）

**关键判断点：**
1. **哈希目标**：测试数据 / 演示账号 vs 真实用户密码
2. **安全边界**：内网管理工具 vs 互联网暴露 API
3. **数据敏感度**：公开信息 vs PII / 金融数据 / 健康记录
4. **对抗模型**：是否需防御彩虹表 / GPU 暴力破解
5. **生命周期**：临时令牌（< 5 分钟）vs 长期存储（数年）
6. **替代方案**：系统是否有 `bcrypt` / `argon2` / `scrypt` 实现
7. **调用频率**：历史数据读取 vs 高频注册登录
8. **合规要求**：GDPR / PCI DSS / 等保 2.0 / HIPAA 是否适用
9. **攻击面**：登录失败锁定 / 验证码 / 速率限制是否存在
10. **数据泄露历史**：是否曾发生数据库脱库事件

## Low risk

**可接受的低风险场景：**
- 非安全用途缓存键生成（Memcached Key / Redis Hash Key）
- 日志追踪 ID / 请求 ID 生成（无认证用途）
- 文件去重标识（内部备份系统无对抗需求）
- 分布式锁键生成（临时锁标识）
- 消息幂等性校验（短期去重窗口 < 5 分钟）
- 开发环境快速原型（`DEBUG=True` 且专网隔离）
- 读取历史归档数据（一次性迁移脚本）
- 遗留系统互操作（第三方仅支持 MD5 且内网专线）
- 性能测试环境模拟数据生成
- ETag 生成 / 内容摘要（CDN 缓存标识）

**降级条件：**
- 数据已公开或极低敏感度（公开文章 ID / 匿名统计）
- 短期过渡方案有明确迁移计划（Sprint 可查 / Jira 跟踪）
- 访问严格网络隔离（VPC 专网 + IP 白名单 + VPN + mTLS）
- 仅向后兼容读取，所有新用户注册用 `bcrypt` / `argon2`
- 攻击窗口极短（一次性令牌 < 5 分钟 + 单次使用 + HTTPS）
- 已有外层强保护（TLS 1.3 + HSTS + Certificate Pinning）
- 数据量极小且无重复模式（UUID / CSPRNG 生成）
- 攻击成本远高于资产价值（内部低价值测试环境）
- 登录保护完善（验证码 + 速率限制 + 账户锁定 + 2FA + 生物识别）
- 监控告警覆盖（异常登录检测 + SOC 24/7 响应 + SIEM 关联）

**警告：** MD5 已被实用碰撞攻击证明不安全（2008 年伪造 CA 证书、2012 年 Flame 恶意软件）。商用彩虹表覆盖常见密码（如 RockYou 泄露的 14 亿密码），GPU 集群暴力破解 8 位纯小写字母 MD5 仅需 < 1 小时（NVIDIA RTX 4090 约 200 GH/s）。Python 标准库无 `bcrypt` 需安装 `pip install bcrypt`，Django 3.1+ 默认使用 PBKDF2-SHA256（10 万轮迭代），Flask 推荐 `werkzeug.security.generate_password_hash(method='pbkdf2:sha256')`，FastAPI 推荐 `passlib[bcrypt]`。任何涉及身份认证、支付签名、PCI DSS / GDPR / 等保 2.0 / HIPAA 合规的系统应立即迁移：密码存储用 `bcrypt` / `argon2id`（内存硬函数），通用哈希用 `SHA-256` / `SHA3-256`，消息认证用 `HMAC-SHA256`。低风险评级不代表接受长期使用，仅适用于有明确迁移计划的过渡期或非安全关键场景。现代 Python 应用无理由继续使用 MD5 进行密码存储，Django / Flask / FastAPI 官方文档均明确反对。
