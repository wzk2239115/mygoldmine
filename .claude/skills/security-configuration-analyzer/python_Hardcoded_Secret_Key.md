# Python - Hardcoded Secret Key

## Details

### 代码示例

```python
# 示例1: Flask硬编码SECRET_KEY
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-12345'
app.config['SESSION_COOKIE_SECURE'] = False

# 示例2: Django settings.py硬编码
SECRET_KEY = 'django-insecure-a#5f$g@h!j*k&l^m%n(o)p+q-r=s~t'
DATABASES = {
    'default': {
        'PASSWORD': 'MyDBPass123',
    }
}

# 示例3: JWT硬编码密钥
jwt_secret = "my-jwt-secret-2024"
token = jwt.encode(payload, jwt_secret, algorithm='HS256')

# 示例4: 加密库硬编码密钥
from cryptography.fernet import Fernet
cipher = Fernet(b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=')

# 示例5: API密钥硬编码
OPENAI_API_KEY = "sk-proj-abc123xyz789"
headers = {'Authorization': f'Bearer {OPENAI_API_KEY}'}

# 示例6: 盐值硬编码
SALT = b'fixed_salt_value_2024'
hashed = hashlib.pbkdf2_hmac('sha256', password, SALT, 100000)
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- 配置变量：`SECRET_KEY`、`API_KEY`、`TOKEN`、`PASSWORD`、`SALT`、`PRIVATE_KEY`
- 框架配置：`app.config['SECRET`、`settings.SECRET`、`Config.SECRET`
- JWT相关：`jwt.encode(`、`jwt_secret`、`JWT_SECRET`
- 加密库：`Fernet(`、`AES.new(`、`cipher_key`、`encryption_key`

**L2 - 跳读：**
- 配置文件：重点看 `settings.py`、`config.py`、`__init__.py` 的全局变量赋值
- 工厂函数：`create_app()`、`init_app()` 中的配置加载逻辑
- 类属性：`class Config:` 内部的大写常量定义
- 环境切换：`if ENV == 'production'` 分支中的密钥赋值

**L3 - 逐行读：**
- 字符串拼接：`SECRET = "prefix_" + "hardcoded_suffix"` 形式的隐蔽赋值
- 字典解析：`config.get('SECRET', 'default_hardcoded')` 的默认值
- 装饰器参数：`@jwt_required(secret='hardcoded')` 形式的内联密钥
- 动态导入：`importlib.import_module()` 加载的配置模块

**L4 - 跨模块追踪：**
- 配置继承：`ProductionConfig(BaseConfig)` 检查父类是否硬编码
- 蓝图注册：多个蓝图共享的 `current_app.config` 来源
- 中间件初始化：`SessionMiddleware(app, secret=?)` 密钥参数溯源
- 打包部署：`setup.py`、`pyproject.toml` 中是否包含敏感配置

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 环境变量：`os.environ.get(`、`os.getenv(`、`environ['SECRET']`
- 配置文件：`.env`、`secrets.json`、`vault`、`python-decouple`
- 密钥管理：`boto3.client('secretsmanager')`、`hvac.Client()`（Vault）
- 框架集成：`django-environ`、`python-dotenv`、`pydantic-settings`

**L2 - 跳读：**
- 检查赋值前是否先尝试环境变量：`SECRET = os.getenv('SECRET') or 'default'`
- 配置加载顺序：是否存在 `load_dotenv()`、`.env.example`
- 异常处理：密钥缺失时是否抛出异常而非使用默认值
- 配置验证：是否使用 `pydantic` 等库强制检查密钥存在

**L3 - 逐行读：**
- 回退机制检查：`if not SECRET: raise ValueError` vs `SECRET = 'fallback'`
- 密钥格式验证：是否检查密钥长度、熵值（如 `len(SECRET) >= 32`）
- 开发环境检测：`if DEBUG and not SECRET:` 类型的条件保护
- 日志脱敏：密钥打印前是否经过 `SECRET[:4] + '***'` 处理

**L0 - 快速跳过：**
- 测试目录：`tests/`、`test_*.py`、`conftest.py` 中的 Mock 密钥
- 文档示例：`docs/`、`examples/`、`README.md` 中的占位符
- 迁移脚本：Django `migrations/` 中的历史配置（需确认已失效）

## Classify

### 确认为漏洞的判定标准：
- 生产配置文件（非测试）中直接赋值字符串字面量作为密钥
- 密钥用于会话加密、JWT签名、数据加密等安全关键操作
- 无环境变量或外部配置读取逻辑，硬编码为唯一来源
- 代码仓库历史提交中可追溯到密钥明文
- 密钥符合框架默认格式（如Django的50字符随机串）但未轮换

### 误报的常见场景：
- 单元测试中的 `SECRET_KEY = 'test'` 且测试环境完全隔离
- 示例代码中的占位符（如 `'your-secret-key-here'`、`'changeme'`）
- 文档字符串或注释中的伪代码示例
- 已通过 `.gitignore` 排除的本地配置文件
- 加密算法标准测试向量（如 NIST 测试数据）

### 代码异味的判定：
- 使用 Base64/hex 编码"隐藏"密钥，实质仍为硬编码
- 密钥分片存储：`KEY = PART1 + PART2`，运行时拼接
- 存在环境变量读取但提供硬编码默认值且无告警
- 通过简单异或或字符偏移"混淆"密钥
- 开发/生产环境共用同一硬编码密钥

### 研判流程：
1. 确认密钥作用域：全局配置/局部函数/类属性
2. 评估敏感度：用于认证/授权（高危）vs 日志签名（低危）
3. 检查生命周期：是否在容器/Lambda每次启动时动态生成
4. 验证可达性：通过 `git log -S "SECRET_KEY"` 追溯历史提交
5. 交叉验证：与生产环境配置管理平台（如 AWS SSM）对比

## Low Risk

### 低风险场景评级标准：

**场景1：隔离的测试环境**
- 仅用于 `pytest`/`unittest` 的 fixture 密钥
- 配置明确标注 `TEST_SECRET_KEY` 且仅在测试文件中引用
- 使用 `@pytest.fixture` 动态生成临时密钥
- CI/CD流水线中的一次性环境变量

**场景2：公开的非敏感标识**
- 公开API的只读Token（如公共数据集API）
- 开源项目明确标注为示例的 `.env.example` 占位符
- 文档生成工具的无害配置（如Sphinx主题密钥）
- 本地开发的SQLite空密码（明确注释"仅限开发"）

**场景3：安全性不依赖密钥保密**
- 用于生成非安全性质的唯一ID（如请求追踪ID）
- 缓存键前缀（无认证价值）
- 调试模式下的临时签名（生产环境禁用）
- 已公开的历史密钥且已确认轮换

**场景4：动态生成的伪硬编码**
- `SECRET = secrets.token_urlsafe(32)` 每次部署时生成
- Docker entrypoint脚本运行时注入环境变量
- Kubernetes Secret挂载为环境变量（代码中读取环境变量）
- 配置中心推送的动态配置（虽是字符串赋值但来源外部）

**评级降级条件（需提升风险等级）：**
- 硬编码密钥格式与生产环境相同（如50字符随机串）
- 代码注释提及"临时密钥"但已存在超过6个月
- 密钥在多个服务/项目间重复使用
- Git历史显示密钥曾用于生产环境后未删除
- 框架文档明确要求动态生成但使用静态值（如Flask官方警告）