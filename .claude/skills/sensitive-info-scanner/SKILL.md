---
name: sensitive-info-scanner
description: 专业敏感信息泄露审计工作流：以静态代码+配置+日志片段为主，优先识别未加密或未脱敏的密钥/凭据/PII 暴露、配置文件/日志泄漏，以及用户可控输入直接拼接到外部请求/存储路径导致的数据外泄；按编程语言组织的参考指南用于快速判定风险模式与修复要点。
---

## 概述与边界

- 聚焦敏感信息泄露：代码、配置、日志、文档中密钥/凭据/PII 暴露与敏感接口返回。
- 依赖上游画像/威胁建模提供端点和上下文，本技能专注检测与判级。
- 不做：产物格式定义、任务编排说明、性能/增量扫描策略。

## 优先级策略

- **风险=影响范围×敏感程度**；按认证状态与泄露内容分 P0/P1/P2。
- **P0 Critical**：免认证 + 管理员/系统敏感信息（环境变量/配置导出/用户列表/私钥等）。
- **P1 High**：普通用户认证即可获取管理员/系统敏感信息（权限提升或越权）。
- **P2 Medium/Low**：权限匹配的敏感信息、硬编码但未对外暴露的凭证、文档/测试示例。
- 快速判定：是否 API 端点 → 是否需认证 → 当前角色 → 泄露信息级别 → P0/P1/P2。

## 核心流程

1) 目标分析：范围（代码/配置/日志/历史）、技术栈、规则加载。  
2) 静态扫描：按优先级扫描配置→代码→文档→日志，规则=正则+熵+上下文。  
3) 智能过滤：占位符/示例/测试路径白名单，熵值校验，上下文关键词调权。  
4) 严重度与优先级：基础严重度 + 认证/权限/数据敏感度 → P0/P1/P2。  
5) 高级检测：端点筛选、环境变量过滤缺陷、认证缺失、数据流源-汇追踪。  
6) 输出：按优先级→严重度→路径排序，生成 Finding 与修复建议。

## 检测范围

### 敏感信息类型
- 云服务：AKIA…、AIza…、ghp_/gho_、UUID/Azure Key、40 位密钥（CWE-798）。
- 数据库：mysql/postgresql/mongodb/redis 连接串与密码（CWE-798）。
- 加密密钥：RSA/OPENSSH/PGP 私钥，JWT Secret（CWE-798）。
- 认证令牌：Bearer/OAuth/Session/API Key（CWE-798）。
- PII：邮箱、手机号、身份证、信用卡（CWE-359）。
- 内部信息：内网 IP、内部域名、调试堆栈（CWE-200/CWE-209）。

### 扫描位置
- 源码：硬编码字符串、变量赋值、注释、测试夹具。
- 配置：.env*/config.{yml,json}/application.{yml,properties}/docker-compose/k8s/tf。
- 日志与文档：*.log, *.txt, README/CHANGELOG/docs/wiki。
- 依赖与构建：package.json/requirements.txt/pom.xml/.npmrc/.pypirc/build.gradle/Gemfile。
- 版本控制：.git/config、应忽略但未忽略的密钥文件、历史提交/删除文件。

## 高级检测

### 端点筛选与优先级
- 高风险 category：internal-*, admin-*, debug-*, config-*。
- P0：免认证且返回配置/环境/用户/系统信息；关键词 config/env/settings/export/users/system/info。
- P1：需普通用户认证即可访问管理/配置功能。
- P2：认证且权限匹配的端点。

### 环境变量过滤缺陷
```go
// 黑名单过滤不完整（Go）
var skipEnvs = map[string]struct{}{"APP_DEBUG": {}, "LOG_LEVEL": {}}
func getSystemConfig() SystemConfig {
    envs := env.List("APP_")
    envValues := map[string]string{}
    for _, k := range envs {
        if _, ok := skipEnvs[k]; ok { continue }
        envValues[k] = env.Get(k, "") // 敏感变量未过滤
    }
    return SystemConfig{Env: envValues}
}
```
```python
# 黑名单过滤不完整（Python）
SKIP_ENVS = ['DEBUG', 'LOG_LEVEL']
def get_system_config():
    cfg = {}
    for k, v in os.environ.items():
        if k.startswith('APP_') and k not in SKIP_ENVS:
            cfg[k] = v  # APP_SECRET_KEY 未过滤
    return cfg
```
检测要点：识别黑名单/白名单混用，枚举敏感变量 *_PASSWORD/*_SECRET/*_KEY/*_TOKEN/*_PRIVATE_KEY，对比过滤集，结合认证状态给 P0/P1/P2。

### 认证机制缺失
- Handler 注册是否缺少 auth middleware；常见非认证包装：httpTrace/httpTraceHdrs/wrapHandler。
- Handler 内是否有 authenticate/authorize；无则结合返回内容判定：无认证+敏感信息 → P0；有认证无授权+敏感信息 → P1。
- 客户端发送 token 但服务端不验证 → 视同免认证。

### 数据流追踪（源→汇）
- 源：env.List/os.Environ/process.env/getConfig。
- 过滤：filter/sanitize/redact/allowedEnvs。
- 汇：json.Encode/Response.json/w.Write/res.json。
- 若无过滤直达汇：按敏感类型 + 认证状态判定 P0/P1/P2，并记录 evidence chain。

## 结果输出与修复建议

### Finding 字段
finding, target, location, secretType, evidence[], confidence(0-1), severity(critical/high/medium/low), priority(P0/P1/P2), authRequired(bool), requiredRole(admin/user/none), leaksAdminInfo(bool), cwe, recommendation。

### 修复建议
- P0：立即加认证或下线端点；轮换全部泄露凭证；审计访问；发布公告。
- P1：补授权/角色校验；最小权限；审计用户访问。
- P2：移除硬编码；使用密钥管控（Secrets Manager/Vault 等）；轮换密钥；从版本控制移除。

### 排序与分组
- 输出按优先级 P0→P1→P2，再按严重度、路径；汇总各优先级数量。

## 误报与白名单
- 常见误报：示例/占位符（YOUR_API_KEY_HERE）、测试数据（test_key_*）、公开邮箱。
- 白名单示例（项目根 `.sensitive-info-whitelist.json`）：
```json
{
  "patterns": ["test_key_*", "example_*", "*_for_testing_only"],
  "files": ["docs/examples/*.py", "tests/fixtures/*.json"],
  "values": ["AKIAIOSFODNN7EXAMPLE", "test@test.com"]
}
```

## 语言适配（精简）
- Java/Spring：application.{yml,properties} 中 spring.datasource.password/jwt.secret/cloud.aws.*；硬编码常量；@Value("${secret}") 对应配置。
- Python/Django/Flask：settings.py/config.py 的 SECRET_KEY/DATABASE_URL/AWS_ACCESS_KEY_ID；.env 是否忽略；硬编码 password/API_KEY。
- Node.js/Express：.env* 的 DATABASE_URL/JWT_SECRET/API_KEY；config 对象硬编码；package.json 私有仓库 token。
- PHP/Laravel：.env 中 DB_PASSWORD/APP_KEY/AWS_ACCESS_KEY_ID；config/*.php 硬编码；数据库连接硬编码。
- Go：const 硬编码；yaml/json/toml 配置加载；env.Get/os.Getenv 使用 vs 硬编码。

## 特殊场景
- Git 历史：git log --all --full-history -- "*.env"；git log -p | grep 密钥模式。
- 大文件：跳过 >10MB；超大文本采样；日志优先最近 7 天。
- 云原生：K8s Secret 避免明文/base64；Dockerfile/compose ENV；Terraform tfstate 加密与远程存储。

## 工具片段

### 正则表达式库
```python
AWS_ACCESS_KEY = r'AKIA[0-9A-Z]{16}'
AWS_SECRET_KEY = r'(?i)aws(.{0,20})?[\'\"][0-9a-zA-Z/+=]{40}[\'\"]'
GITHUB_TOKEN = r'ghp_[0-9a-zA-Z]{36}'
GITHUB_OAUTH = r'gho_[0-9a-zA-Z]{36}'
GOOGLE_API_KEY = r'AIza[0-9A-Za-z_-]{35}'
SLACK_TOKEN = r'xox[baprs]-[0-9]{10,12}-[0-9]{10,12}-[0-9a-zA-Z]{24,32}'
RSA_PRIVATE_KEY = r'-----BEGIN RSA PRIVATE KEY-----'
OPENSSH_PRIVATE_KEY = r'-----BEGIN OPENSSH PRIVATE KEY-----'
DB_CONNECTION_STRING = r'(mysql|postgresql|mongodb|redis)://[^:]+:[^@]+@[^/]+'
JWT_PATTERN = r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'
```

### 熵值分析
```python
def calculate_entropy(string):
    import math
    from collections import Counter
    if not string: return 0.0
    probs = [c/len(string) for c in Counter(string).values()]
    return -sum(p * math.log2(p) for p in probs)
```

### 上下文关键词调权
```python
EXAMPLE_KEYWORDS = ['example','test','mock','fake','sample','demo','placeholder','dummy','template','your_key_here']
SENSITIVE_KEYWORDS = ['secret','password','passwd','pwd','token','api_key','private_key','access_key','auth','credential','apikey']
```

## 输出要求

1. **扫描结果文件**：输出到 `.workspace/tasks/{TASK_ID}/sensitive-info-scanner-result.md`

**文件内容格式**：
```markdown
# 敏感信息扫描结果

## 扫描概要
- 扫描范围：[代码/配置/日志/文档]
- 发现数量：[P0: X, P1: Y, P2: Z]

## P0 Critical 级别发现
### [FINDING-001] {secretType}
- **位置**：{file}:{line}
- **类型**：{secretType}
- **证据**：{evidence}
- **置信度**：{confidence}
- **CWE**：{cwe}
- **修复建议**：{recommendation}

## P1 High 级别发现
...

## P2 Medium/Low 级别发现
...
```

2. **不需要生成下游任务**

**总结输出格式（JSON格式）**：
```json
{
    "tasks": [],
    "summary": {
        "p0_count": 0,
        "p1_count": 0,
        "p2_count": 0,
        "total": 0
    }
}
```
