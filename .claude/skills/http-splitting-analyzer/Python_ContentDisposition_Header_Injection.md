# Python Content-Disposition 头注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `response.headers['Content-Disposition'] = value` 直接设置
- `HttpResponse['Content-Disposition'] = value` - Django
- `make_response()` 后设置 Content-Disposition
- 文件名直接拼接：`f"attachment; filename={filename}"`
- 没有 RFC 2183 / RFC 6266 合规处理

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`attachment`、`inline`、`filename=`
2. 追踪文件名来源：`request.args.get('file')`、数据库字段、用户上传文件名
3. 检查是否使用双引号包装：`filename="user_input"`
4. 查看是否过滤特殊字符（`;`、`,`、`
`）

**快速定位保护机制：**
- RFC 合规转义：使用 RFC 5987 格式 `filename*=UTF-8''...` 或 `filename="..."`
- 特殊字符过滤：移除 `;`、`,`、``、`
`
- 双引号转义：`"` → `"`
- 白名单验证：`if re.match(r'^[a-zA-Z0-9\-_.]+$', filename)`
- 框架级处理：某些框架自动处理文件名安全性

**代码示例：**
```python
# 危险：用户文件名直接用于 Content-Disposition
from flask import send_file, request

@app.route('/download')
def download():
    filename = request.args.get('file')
    response = send_file('data/' + filename)
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'  # 危险
    return response

# 危险：Django 文件下载
from django.http import HttpResponse

def serve_file(request):
    name = request.GET.get('name')
    response = HttpResponse(open(name).read())
    response['Content-Disposition'] = f'attachment; filename={name}'  # 危险
    return response

# 危险：直接拼接
return send_file(filepath, download_name=user_filename)  # 如果 user_filename 未验证
```

## Classify

**漏洞（High）：**
- 用户提供的文件名（Query、Form、数据库字段）直接用于 Content-Disposition
- 文件名包含 `;`、`,`、`
` 或双引号，导致头分割
- 无任何文件名验证或转义
- 允许目录遍历（`../../../etc/passwd`）

**误报：**
- 文件名来自系统生成（UUID、Hash）
- 文件名经过白名单验证（如 `^[a-zA-Z0-9\-_.]+$`）
- 使用框架的 `send_file()` 等安全 API

**代码异味（Medium）：**
- 仅过滤某些字符（如 `;` 但未过滤 `,`）
- 使用黑名单过滤但不完整
- 文件名经过 URL 编码但未解码验证
- 目录遍历检查不完整（如仅检查 `../` 但未检查 `..\`）

## Low risk

**以下情况评为低风险：**
- 文件名完全硬编码
- 使用框架安全方法（`send_file()` 等）且框架版本已修补
- 严格白名单验证：仅允许特定格式的文件名
- 文件名来自内部系统（数据库中的安全字段）
- 实现了 RFC 合规的文件名编码（RFC 5987）
- 文件名长度限制 + 允许字符限制（如仅字母数字）
