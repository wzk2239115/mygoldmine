# Python 多行响应头未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- 响应头值包含换行符（`
`、`
`）被直接传递
- `response.headers[key] = value` 其中 value 含多行
- WSGI 环境中 Header List 传入带换行的值
- 自定义 HTTP 响应头格式化不规范

**快速定位核心操作：**
1. 搜索关键字：`
`、`
` 在响应头值中的使用
2. 追踪多行处理逻辑：头值来源是否经过换行处理（`.split('\n')`、`.replace('\n', '')`）
3. 检查是否存在头部值规范化步骤
4. 追踪从用户输入到响应头的完整链路

**快速定位保护机制：**
- 换行符移除：`value.replace('
', ' ').replace('', ' ').replace('
', ' ')`
- 规范化处理：遵循 RFC 7230（HTTP 头字段格式标准）
- 值验证：`if any(c in value for c in '
'): raise ValueError()`
- 框架级防护：某些框架自动验证和规范化头值

**代码示例：**
```python
# 危险：多行值直接设置为响应头
from flask import make_response, request

@app.route('/header')
def set_header():
    data = request.args.get('data')
    response = make_response('OK')
    response.headers['X-Data'] = data  # 危险：如果 data 包含 

    return response

# 危险：从外部数据源读取包含换行的值
import requests

def proxy_response():
    headers = requests.get('http://api').headers
    response = make_response('OK')
    for key, value in headers.items():
        response.headers[key] = value  # 危险：未规范化
    return response

# 危险：WSGI 格式
def app(environ, start_response):
    header_value = environ.get('HTTP_X_CUSTOM')  # 可能包含 

    headers = [('X-Custom', header_value)]
    start_response('200 OK', headers)
    return [b'OK']
```

## Classify

**漏洞（Medium）：**
- 响应头值包含 `
` 或 `
` 导致响应分割
- 用户输入或外部数据源的值未进行换行符规范化
- 框架未自动检测和拒绝多行值
- 多行值可用于注入额外响应头或响应体

**误报：**
- 响应头值完全硬编码
- 框架已自动规范化（如 Werkzeug 等）
- 使用官方 API（如 `make_response()` 的 headers 参数）

**代码异味（Medium）：**
- 头值来自数据库或配置文件但未验证
- 外部 API 响应的头直接转发
- 仅过滤 `
` 但未过滤 ``（或反之）
- 间接流程：输入 → 处理 → 存储 → 响应头

## Low risk

**以下情况评为低风险：**
- 响应头值完全硬编码
- 使用框架的正式 API 且框架已实现规范化
- 明确的换行符过滤：`value = value.replace('\r', '').replace('\n', '')`
- 白名单验证头值格式
- 头值来自内部系统且已验证不含换行符
- 仅涉及非关键响应头（如 `X-Custom-Debug`）
