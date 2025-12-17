# Python Debug Mode Enabled

## Details

### 代码示例

**Flask 调试模式启用：**
```python
# 直接硬编码 debug=True
app.run(debug=True, host='0.0.0.0')

# 配置对象中启用
app.config['DEBUG'] = True

# SECRET_KEY 硬编码
app.config['SECRET_KEY'] = 'hardcoded_secret_123'

# 环境变量未校验直接使用
app.config['DEBUG'] = os.getenv('DEBUG', 'True') == 'True'
```

**Django 调试模式启用：**
```python
# settings.py 中直接设置
DEBUG = True

# ALLOWED_HOSTS 过宽
ALLOWED_HOSTS = ['*']

# SECRET_KEY 硬编码
SECRET_KEY = 'django-insecure-hardcoded-key-12345'

# 安全中间件禁用
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
```

**数据库连接敏感信息硬编码：**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'mydb',
        'USER': 'root',
        'PASSWORD': 'password123',  # 硬编码密码
        'HOST': 'localhost',
    }
}
```

### 快速定位核心操作

**（L1: 关键词扫描）**
- 搜索：`debug=True`、`DEBUG = True`、`app.run(`、`ALLOWED_HOSTS`、`SECRET_KEY =`
- 正则匹配：`\.run\([^)]*debug\s*=\s*True`、`DEBUG\s*=\s*True`
- 配置文件：`settings.py`、`config.py`、`.env`、`__init__.py`

**（L2: 跳读）**
- Flask 入口文件：查看 `app.run()` 调用参数、`app.config` 赋值
- Django 配置：扫描 `settings.py` 顶部配置项（DEBUG/SECRET_KEY/ALLOWED_HOSTS）
- 环境变量：关注 `os.getenv('DEBUG')`、`os.environ.get()` 默认值设置

**（L3: 逐行读）**
- 条件判断：`if DEBUG:` 分支是否泄露敏感逻辑
- 错误处理器：`@app.errorhandler` 是否在调试模式下返回堆栈信息
- 日志配置：`logging.DEBUG` 级别是否记录敏感数据
- 中间件配置：安全头设置是否依赖 DEBUG 开关

**（L4: 跨模块追踪）**
- 配置加载链路：环境变量 → 配置文件 → 应用初始化
- 工厂模式：`create_app(config_name)` 参数来源是否可控
- 蓝图注册：不同环境蓝图是否正确切换
- 部署脚本：启动命令、容器环境变量、CI/CD 配置

### 快速定位保护机制

**（L1: 关键词扫描）**
- 搜索：`debug=False`、`DEBUG = False`、`env.get('DEBUG', False)`
- 环境判断：`if os.getenv('ENV') == 'production'`、`if not app.debug`
- 配置分离：`config/production.py`、`config/development.py`

**（L2: 跳读）**
- 配置类继承：查看 `ProductionConfig` 是否覆盖 DEBUG
- 环境变量：检查 `.env.example` 是否提供安全默认值
- 部署文档：`README.md`、`DEPLOY.md` 是否说明配置要求

**（L3: 逐行读）**
- 配置验证：是否有 `assert not app.debug` 或 `if DEBUG: raise Exception`
- 条件分支：生产环境是否强制 `DEBUG=False`
- SECRET_KEY 生成：是否从环境变量读取或随机生成
- ALLOWED_HOSTS 白名单：是否限制为具体域名列表

**（L4: 跨模块追踪）**
- 配置管理系统：是否使用 python-decouple、dynaconf 等
- 启动脚本：部署脚本是否显式设置生产环境变量
- 容器化：Dockerfile/docker-compose.yml 是否正确设置 ENV
- WSGI 服务器：Gunicorn/uWSGI 配置是否禁用调试

## Classify

### 漏洞判定标准
1. **生产环境标识明确**：通过域名、IP、环境变量、代码注释确认为生产代码
2. **调试功能可达**：DEBUG=True 且代码可执行（非注释、非示例）
3. **敏感信息泄露路径存在**：错误页面、日志输出、调试端点暴露堆栈/变量

### 误报场景
1. **开发/测试环境**：明确的本地开发配置（localhost、127.0.0.1）
2. **示例代码**：教程、文档、注释中的示例片段
3. **已覆盖配置**：后续代码或环境变量强制覆盖为 False
4. **条件限制**：通过 IP 白名单、内网限制等保护调试功能

### 代码异味（需人工复核）
1. **配置分散**：DEBUG 在多处设置，优先级不明确
2. **默认值不安全**：环境变量缺失时默认启用调试
3. **硬编码凭证**：SECRET_KEY/数据库密码明文但 DEBUG=False
4. **混合配置**：生产配置文件中同时存在 DEBUG=True 和安全设置

## Low risk

### 低风险评级场景

1. **受限暴露范围**
   - 调试端点仅限内网访问（防火墙/VPN）
   - 通过 IP 白名单严格限制访问来源
   - 需要额外身份验证（Basic Auth/Token）

2. **敏感信息已脱敏**
   - 自定义错误处理器过滤了堆栈信息
   - 日志配置排除敏感字段（密码/Token）
   - DEBUG 端点仅返回非敏感的系统状态

3. **临时调试场景**
   - 代码注释标明临时启用且有 TODO/FIXME
   - Git 日志显示为近期调试提交（配合回滚计划）
   - 功能开关系统控制，可远程快速关闭

4. **部分调试功能**
   - 仅启用性能分析（无敏感数据泄露）
   - SQL 日志输出但连接信息已加密
   - 前端 SourceMap 暴露但后端 DEBUG=False

5. **隔离环境**
   - 预发布环境（Staging）启用调试但与生产网络隔离
   - 容器化部署且容器间网络策略严格限制
   - 仅供内部测试使用的独立实例

### 注意事项
即使评为低风险，仍需在报告中标注，建议生产环境完全禁用调试模式以符合安全最佳实践。