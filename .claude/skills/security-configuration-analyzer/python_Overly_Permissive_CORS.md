# Python - Overly Permissive CORS

## Details

### 代码示例

```python
# 示例1: Flask-CORS 允许所有源访问
from flask import Flask
from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # 默认允许所有源

# 示例2: Flask-CORS 显式通配符配置
CORS(app, origins="*", supports_credentials=True)  # 危险组合

# 示例3: Django CORS Headers 通配符
# settings.py
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True  # 与通配符冲突

# 示例4: Flask 手动设置响应头
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

# 示例5: Django 中间件手动实现
class CORSMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        response['Access-Control-Allow-Origin'] = request.META.get('HTTP_ORIGIN', '*')
        response['Access-Control-Allow-Credentials'] = 'true'
        return response

# 示例6: FastAPI 过度宽松配置
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 示例7: aiohttp 不安全CORS
from aiohttp import web
from aiohttp_cors import setup as cors_setup
cors = cors_setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        allow_headers="*"
    )
})

# 示例8: Tornado 自定义头处理
class MainHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Credentials", "true")
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- 库导入：`from flask_cors import CORS`、`from django_cors_headers`、`CORSMiddleware`
- 配置变量：`CORS_ORIGIN_ALLOW_ALL`、`CORS_ALLOWED_ORIGINS`、`allow_origins`、`origins`
- 响应头：`Access-Control-Allow-Origin`、`Access-Control-Allow-Credentials`
- 通配符：`origins="*"`、`"*"` in `allow_origins`、`ALLOW_ALL = True`

**L2 - 跳读：**
- Flask应用初始化：定位 `CORS(app` 调用位置，检查参数配置
- Django配置文件：重点看 `settings.py` 中以 `CORS_` 开头的配置项
- 中间件注册：检查 `MIDDLEWARE`、`add_middleware()` 中的CORS相关配置
- 蓝图/子应用：多个蓝图是否独立配置CORS（可能遗漏某些端点）

**L3 - 逐行读：**
- 动态Origin构建：检查是否从请求头直接反射 `request.headers.get('Origin')`
- 正则匹配Origin：`CORS_ORIGIN_REGEX_WHITELIST` 是否过度宽松（如 `r'.*'`）
- 条件分支配置：`if DEBUG` 分支中的宽松CORS是否泄漏到生产环境
- 装饰器参数：`@cross_origin(origins="*")` 单个路由的不安全配置

**L4 - 跨模块追踪：**
- 工厂函数传递：`create_app(config)` 中CORS配置来源追踪
- 环境变量控制：`CORS_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')` 默认值风险
- 配置类继承：`ProductionConfig(BaseConfig)` 检查父类CORS配置是否被覆盖
- 多服务共享配置：微服务架构中共享的 `common/cors.py` 配置模块

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 白名单列表：`CORS_ALLOWED_ORIGINS = ['https://app.example.com']`
- 严格模式：`CORS_ORIGIN_ALLOW_ALL = False`、`supports_credentials=False`
- Origin验证：`validate_origin()`、`is_allowed_origin()`、`check_cors()`
- 环境区分：`PRODUCTION_ORIGINS`、`ALLOWED_DOMAINS`

**L2 - 跳读：**
- 检查 `allow_origins` 是否为明确域名列表而非通配符
- 确认 `allow_credentials` 与 `allow_origins="*"` 不共存
- 查找预检请求处理：`OPTIONS` 方法是否正确验证Origin
- 配置优先级：环境变量、配置文件、代码硬编码的覆盖关系

**L3 - 逐行读：**
- Origin白名单验证逻辑：检查是否使用精确匹配而非 `in` 操作符（防止子串匹配）
- 动态白名单加载：从数据库/配置中心读取的Origin列表是否经过验证
- 子域名处理：是否使用安全的正则匹配（如 `r'^https://[\w-]+\.example\.com$'`）
- 错误降级：CORS验证失败时是否安全拒绝而非回退到 `*`

**L0 - 快速跳过：**
- 测试文件：`test_*.py`、`tests/` 中的宽松CORS配置（需确认测试隔离）
- 文档示例：`docs/`、`examples/` 中的演示代码
- 开发工具：`manage.py runserver` 仅用于开发的配置
- Mock服务：`tests/mocks/` 中的测试桩服务器

## Classify

### 确认为漏洞的判定标准：
- 生产环境配置 `Access-Control-Allow-Origin: *` 且应用处理敏感数据
- `allow_credentials=True` 与 `origins="*"` 同时启用（浏览器会拒绝但配置本身不安全）
- 从请求头直接反射Origin且无白名单验证：`response['ACAO'] = request.headers['Origin']`
- CORS白名单包含过于宽松的正则（如 `r'http://.*'` 允许所有http站点）
- 敏感API端点（如 `/api/user/profile`、`/admin/*`）未排除在CORS配置外

### 误报的常见场景：
- 纯公开静态资源API（如CDN、公共数据集）使用 `*` 是合理设计
- 测试环境配置通过 `if settings.DEBUG` 严格隔离且不影响生产
- 内部管理工具明确注释"仅内网访问"且网络层已隔离
- CORS库的默认示例代码，实际部署时已被覆盖
- Swagger/OpenAPI文档端点允许所有源（非敏感操作）

### 代码异味的判定：
- 存在白名单但包含 `null` 源（允许本地文件访问）
- 使用子字符串匹配验证Origin：`if origin in ALLOWED_ORIGINS`（`evil.com` 可匹配 `example.com`）
- 开发/生产环境共用CORS配置且通过环境变量控制但无默认安全值
- 预检请求（OPTIONS）返回宽松配置但实际请求有严格验证（不一致）
- 注释中提及"临时开放"但已存在超过3个月

### 研判流程：
1. 确认配置作用域：全局CORS（整个应用）vs 路由级CORS（特定端点）
2. 评估数据敏感度：API返回公开数据（低危）vs 用户隐私数据（高危）
3. 检查认证机制：无认证公开API（可接受 `*`）vs 基于Cookie/Token的认证（需严格限制）
4. 验证环境隔离：通过配置文件、环境变量确认生产环境实际值
5. 浏览器兼容性：某些旧版本浏览器不强制CORS但服务端配置仍不安全

## Low Risk

### 低风险场景评级标准：

**场景1：纯公开只读API**
- RESTful API仅提供公开数据查询（如天气、汇率、公共统计）
- 无需认证，不涉及用户数据或敏感信息
- 明确设计为第三方集成的开放平台
- 已通过速率限制防止滥用

**场景2：隔离的开发环境**
- 通过 `if app.debug:` 或 `settings.DEBUG` 严格限制宽松CORS
- 配置明确标注"仅本地开发"且生产部署通过CI/CD强制验证
- 使用 `127.0.0.1`、`localhost` 的前端开发服务器
- Docker Compose开发栈中的服务间通信

**场景3：静态资源服务**
- CDN回源服务器仅托管图片、字体、CSS/JS等公共资源
- 无动态内容生成，不处理用户请求
- 已通过独立域名隔离（如 `static.example.com`）
- 资源本身已公开无需访问控制

**场景4：内部工具与监控**
- 企业内网管理后台且已通过VPN/堡垒机隔离
- Prometheus、Grafana等监控工具的API端点（需确认网络隔离）
- 内部文档生成工具（如Swagger UI）允许内网跨域访问
- 已通过网络策略（如Kubernetes NetworkPolicy）限制访问源

**场景5：已有强认证的API**
- 使用OAuth 2.0且Token验证严格（CORS宽松但认证足够强）
- JWT验证包含签名校验和短期过期时间
- API密钥认证且密钥轮换频繁
- 已实施请求签名（如AWS Signature V4）防止跨域攻击

**评级降级条件（需提升风险等级）：**
- "公开API"但返回数据包含用户相关信息（如公开的用户资料）
- 开发环境配置通过注释而非代码逻辑隔离（易误删）
- CORS宽松且同时存在CSRF防护缺失（双重弱点）
- 历史日志显示曾因CORS配置错误导致安全事件
- 配置文件中存在 `CORS_EXPOSE_HEADERS = ['*']` 可能泄漏内部头信息
- 微服务架构中某服务CORS宽松成为整体系统的薄弱点
- 移动应用API使用 `*` 但未实施证书绑定等额外防护
