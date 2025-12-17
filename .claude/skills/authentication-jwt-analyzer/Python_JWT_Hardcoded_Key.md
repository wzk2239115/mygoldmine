# Python JWT 硬编码密钥

## 漏洞成因
使用 PyJWT、python-jose、authlib 等库时，签名密钥直接硬编码在代码中或配置文件内，导致密钥泄露风险。攻击者获取源码或配置后可伪造任意 JWT token。

## Details

### 代码示例

**PyJWT 库（最常用）：**
```python
import jwt
from datetime import datetime, timedelta

# 危险：硬编码密钥
SECRET_KEY = "my_secret_key_123"
payload = {
    'user_id': 1,
    'exp': datetime.utcnow() + timedelta(hours=1)
}
token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

# 验证时同样硬编码
decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
```

**python-jose 库：**
```python
from jose import jwt
from datetime import datetime, timedelta

# 危险：字面量密钥
secret = "hardcoded_secret"
claims = {'sub': 'user123', 'exp': datetime.utcnow() + timedelta(hours=1)}
token = jwt.encode(claims, secret, algorithm='HS256')

# 验证
decoded = jwt.decode(token, secret, algorithms=['HS256'])
```

**authlib 库：**
```python
from authlib.jose import jwt

# 危险：类属性硬编码
class Config:
    JWT_SECRET = "weak_secret_key"

header = {'alg': 'HS256'}
payload = {'iss': 'app', 'sub': 'user'}
token = jwt.encode(header, payload, Config.JWT_SECRET)
```

**Flask/Django 配置文件中的硬编码：**
```python
# settings.py / config.py
JWT_SECRET_KEY = "production_secret_123"  # 危险：配置文件硬编码
JWT_ALGORITHM = "HS256"

# 使用
import jwt
token = jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')
```

### 快速定位核心操作技巧 **[L1-L2]**

**关键词扫描 (L1)：**
- `jwt.encode()` - PyJWT/python-jose 签名函数
- `jwt.decode()` - 验证函数
- `jwt.JWT().encode()` - authlib 签名方式
- 算法关键词：`'HS256'`、`'HS384'`、`'HS512'`、`algorithm=`
- 导入语句：`import jwt`、`from jose import jwt`、`from authlib.jose import jwt`

**跳读定位 (L2)：**
- 搜索 `import jwt` 或 `from jose import jwt` 定位引入点
- 追踪 `encode()` 的第二个参数（密钥参数）
- 检查密钥来源：
  - 字面量字符串（`"xxx"`、`'xxx'`）= 硬编码
  - 大写变量名（`SECRET_KEY`、`JWT_SECRET`）= 需追踪定义
  - 配置类属性（`config.SECRET`、`settings.JWT_KEY`）= 需检查配置文件
- 配置文件特征：`settings.py`、`config.py`、`.env` 中的明文密钥

### 快速定位保护机制技巧 **[L2-L3]**

**跳读检查 (L2)：**
- 环境变量读取：`os.getenv('JWT_SECRET')`、`os.environ['JWT_SECRET']`
- Django 设置：`from django.conf import settings`
- Flask 配置：`app.config.from_envvar()`、`app.config.from_object()`
- 配置管理库：`python-decouple`、`dynaconf`、`pydantic-settings`
- 密钥管理服务：AWS Secrets Manager (`boto3`)、Azure Key Vault、HashiCorp Vault

**逐行验证 (L3)：**
- 确认环境变量加载位置，检查是否有默认值（默认值 = 硬编码）
- 验证配置加载链：`config.py` → 环境变量 → 运行时
- 检查密钥生成：`secrets.token_urlsafe()`、`os.urandom()`
- 排查版本控制：`.gitignore` 是否排除 `.env`、`local_settings.py`
- Django 特殊检查：`SECRET_KEY` 与 `JWT_SECRET_KEY` 是否混用
- 启动时验证：`assert JWT_SECRET`、`if not JWT_SECRET: raise ValueError`

## Classify

### 漏洞判定标准
- **确认漏洞**：密钥为字面量字符串或在版本控制中可见的 `.py` 配置文件内（如 `settings.py` 已提交）
- **误报情形**：
  - 密钥通过环境变量或密钥管理服务动态加载，且原始密钥未在代码中出现
  - 配置文件在 `.gitignore` 中排除，且仓库历史无泄露记录
  - 使用 Django `SECRET_KEY` 但从环境变量读取且无硬编码
- **代码异味**：
  - 密钥从本地文件读取（如 `open('secret.key').read()`）但文件权限受限
  - 开发环境使用硬编码密钥但生产环境通过环境变量覆盖（存在配置错误风险）
  - 密钥使用 `os.getenv('JWT_SECRET', 'default_secret')` 有默认值

### 研判要点
1. **源码可见性**：密钥是否存在于 Git 历史、Docker 镜像、部署脚本中
2. **动态性**：密钥是否支持热更新或需重启服务
3. **环境隔离**：开发/测试/生产环境是否使用不同密钥
4. **密钥强度**：即使硬编码，弱密钥（如 `"secret"`、`"123456"`）风险更高
5. **范围影响**：同一密钥是否用于多个服务或微服务共享

## Low risk

### 低风险场景
1. **单元测试隔离**：仅在测试文件中硬编码（`test_*.py`、`*_test.py`），且测试数据库完全隔离
2. **示例代码**：`examples/`、`docs/` 目录中的演示代码，明确标注非生产使用
3. **短期 token**：仅用于一次性操作（如密码重置链接），有效期 <5 分钟且无敏感权限
4. **已废弃密钥**：代码注释明确标注已轮换，且生产环境已更新（需确认旧 token 已失效）
5. **内网隔离环境**：完全离线的内部工具，攻击者无法访问源码或网络流量
6. **开发模式检测**：代码中有 `if DEBUG: SECRET = "dev"` 且生产环境强制 `DEBUG=False`

### 风险降级条件
- 配合 IP 白名单、设备指纹等多因素认证
- JWT payload 仅包含非敏感会话 ID，实际权限数据存储在 Redis/数据库需二次查询
- 使用 JWE（加密 JWT）额外保护 payload
- Token 有短有效期（<15分钟）+ 严格的 refresh token 机制
- 实施了 token 撤销机制（黑名单/白名单）

### 特别注意
- Django 项目中 `SECRET_KEY` 泄露同时影响 CSRF、session、密码重置等多个安全机制
- Flask-JWT-Extended 的 `JWT_SECRET_KEY` 与 Flask `SECRET_KEY` 应分离管理
- 容器化部署时检查环境变量是否在 Kubernetes Secret 或 Docker Compose 文件中硬编码
