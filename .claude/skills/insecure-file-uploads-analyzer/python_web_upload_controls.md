# Python Web 上传控制漏洞

## Details

### 漏洞成因
Python Web 框架（Django、Flask、FastAPI 等）常通过 `request.files`, `FileField`, `UploadFile` 等 API 处理上传。若缺乏文件扩展名白名单、MIME 校验、大小/数量限制、随机文件名、存储隔离和访问鉴权，攻击者可上传 WebShell、恶意脚本或压缩炸弹，造成代码执行、覆盖静态资源或拒绝服务。Django 默认会将上传文件暂存到磁盘，若 `MEDIA_ROOT` 指向 Web 根目录，也会暴露风险。

### 代码示例

**易受攻击的代码：**
```python
from flask import Flask, request
app = Flask(__name__)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    filename = file.filename  # 未进行白名单校验
    file.save(os.path.join("static/uploads", filename))  # 写入可访问目录
    return "ok"
```

**另一个不安全示例（Django MEDIA_ROOT 暴露）：**
```python
# settings.py
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# views.py
def upload(request):
    f = request.FILES["file"]
    path = default_storage.save(f.name, ContentFile(f.read()))  # 原始文件名
    return JsonResponse({"url": settings.MEDIA_URL + path})
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Flask/Django/FastAPI 上传：`request.files`, `FileField`, `UploadFile`, `FileSystemStorage`
- 存储路径：`MEDIA_ROOT`, `MEDIA_URL`, `static`, `os.path.join`
- 验证逻辑：`allowed_extensions`, `mimetypes`, `magic.from_buffer`
- 临时文件：`TemporaryFile`, `SpooledTemporaryFile`

**定位步骤：**
1. 搜索上传视图/路由，检查是否存在白名单和大小限制。
2. 检查文件保存路径是否位于 Web 可访问目录。
3. 跳读（L2）确认是否启用随机文件名、访问鉴权、内容扫描。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **类型验证：** 使用 `python-magic`、PIL 判断文件头，同时检查扩展名。
- **大小/速率限制：** Django `FILE_UPLOAD_MAX_MEMORY_SIZE`、Flask 配置、反向代理限制。
- **存储隔离：** 使用不可执行目录或对象存储，文件名使用 UUID。
- **访问控制：** 通过签名 URL 或后端代理访问，避免直接暴露 `MEDIA_URL`。
- **安全扫描：** 上传后进行病毒扫描、内容审核。

**定位技巧：**
- 检查是否清理临时文件，防止磁盘耗尽。
- 确认 Celery 等异步任务处理时是否重复验证类型。
- 查看 Nginx/Apache 静态资源配置是否允许执行脚本。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单 + MIME 校验 + 隔离存储 | **L0（快速跳过）** | 风险低 |
| 仅部分验证或依赖前端 | **L2（跳读）** | 需检查覆盖范围 |
| 直接保存到 Web 根目录 | **L3（逐行读）** | 高风险 |
| 上传文件被其它子系统直接执行 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. 上传入口缺少有效的类型、大小、数量控制或随机命名。
2. 文件保存位置可被攻击者访问或执行，缺乏权限隔离。
3. 攻击者能够借此执行代码、覆盖敏感文件或造成 DoS。

#### 误报
以下情况可视为误报：
1. 上传功能仅在内部网络使用，并有额外签名或人工审核。
2. 文件强制存储在不可执行目录，访问需经过后端鉴权。
3. 已集成多层检查（类型、扫描、随机命名）且确认不可利用。

#### 代码异味
需关注的风险：
1. 白名单仅依赖扩展名，未校验内容。
2. 上传后未限制下载次数或带宽，易被滥用。
3. 临时文件/分片上传缺少清理，会耗尽存储。
4. 不同服务共享上传目录，缺乏租户隔离。

## Low risk

### 低风险评级场景

#### 1. 后台管理员接口
- **场景：** 仅管理员可上传，并通过审计记录操作。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. 上传即转存至对象存储
- **场景：** 上传后立即存入 S3/GCS，并设置签名访问。
- **风险评估：** 可降低执行风险，但需校验内容。

#### 3. 定期清理 + 只读访问
- **场景：** 上传目录定期清理，访问走只读代理。
- **风险评估：** 风险较低，但需确保代理安全。

#### 4. 安全监测
- **场景：** 集成 WAF/IDS，监控异常上传请求。
- **风险评估：** 有助于发现问题，需配合防护措施。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用 | 攻击面小 | 中 |
| 隔离存储 + 签名访问 | 技术防护完善 | 低 |
| 定期清理/只读代理 | 降低持久化风险 | 中 |
| 安全监控 | 提升感知能力 | 高（持续完善）|

