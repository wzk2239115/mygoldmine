# Python 相对路径重定向漏洞

相对路径重定向漏洞指应用接收用户可控的路径参数进行重定向时，虽然尝试通过相对路径限制来防止外部域名重定向，但由于验证不足，攻击者可利用路径遍历、协议相对URL、双斜杠等技巧绕过限制，实现跨域重定向。此类漏洞常见于那些仅检查URL前缀而未充分验证的代码中。

## Details

### 代码示例

```python
# 漏洞代码：虽限制相对路径，但验证不足

from flask import Flask, redirect, request
from werkzeug.security import safe_str_cmp

app = Flask(__name__)

# 不安全的验证方式 1：仅检查前缀
@app.route('/redirect1')
def vulnerable_redirect_1():
    path = request.args.get('path', '/')

    # 可被 //evil.com 绕过
    if not path.startswith('/'):
        path = '/' + path
    return redirect(path)

# 不安全的验证方式 2：使用 url_parse 但未严格检查协议和主机
@app.route('/redirect2')
def vulnerable_redirect_2():
    from urllib.parse import urlparse

    path = request.args.get('path', '/')
    parsed = urlparse(path)

    # 可被 //evil.com 绕过，因为 scheme 为空但 netloc 不为空
    if parsed.scheme == '':
        return redirect(path)

# 不安全的验证方式 3：仅检查协议标记，未处理特殊序列
@app.route('/redirect3')
def vulnerable_redirect_3():
    path = request.args.get('path', '/')

    # 可被 /../../../evil.com 或 /\evil.com 绕过
    if '://' not in path:
        return redirect(path)

# 不安全的验证方式 4：URL 编码绕过
@app.route('/redirect4')
def vulnerable_redirect_4():
    from urllib.parse import urlparse

    path = request.args.get('path', '/')

    # 可被 /%2f%2fevil.com 绕过，先验证后解码
    if '://' not in path and not path.startswith('//'):
        return redirect(path)  # 框架会自动解码

# 攻击示例
# GET /redirect1?path=//evil.com/phishing
# GET /redirect2?path=//evil.com:8080/phishing
# GET /redirect3?path=/../../../evil.com
# GET /redirect4?path=/%2f%2fevil.com
# GET /redirect1?path=/\evil.com (部分浏览器处理)
```

**快速定位到核心操作的技巧** `(L1:关键词扫描)`

- 搜索关键词：`redirect()`、`Location`、`url_for()`、`request.args.get()`、`request.form.get()`、`request.values.get()`
- 重点关注：从查询参数、表单参数或其他用户输入直接进入重定向函数的代码路径，特别是那些变量名包含 `path`、`next`、`return_url`、`redirect_url`、`goto` 的地方
- 表现特征：重定向目标与用户可控输入在同一表达式中，且可能存在前缀检查、简单字符串验证或不完整的 URL 解析逻辑

**快速定位到保护机制的技巧** `(L2:跳读)`

- 检查 `redirect()` 调用前的验证逻辑
- 识别验证方式的强度：
  - **弱验证模式**：仅 `path.startswith('/')`、`'://' not in path`、`not path.startswith('//')`、简单的正则表达式检查
  - **中等验证模式**：使用 `urlparse()` 解析，但仅检查 `scheme` 字段而未同时检查 `netloc`
  - **强验证模式**：使用 `urlparse()` 完整解析，检查 `parsed.scheme == ''` 且 `parsed.netloc == ''`，禁止特殊序列
  - **路径格式检查**：是否使用正则表达式限制路径格式（如禁止 `//`、`../`、`\` 等特殊序列）
  - **编码处理**：是否在验证前进行了 URL 标准化（如使用 `urllib.parse.unquote()` 解码后再验证）或在验证后才使用解码结果
- 查看是否存在通用的验证函数或装饰器层的统一处理
- 重点关注验证逻辑中是否考虑了：反斜杠 `\`、双斜杠 `//`、路径遍历 `../`、URL编码绕过 `%2f`、大小写变体 `%2F` 等

## Classify

从漏洞成因分类标准：

**真实漏洞的判断依据**

- 应用尝试通过相对路径检查来防止外部重定向，但验证方式可被绕过：
  - 仅检查前缀 `path.startswith('/')` 而未处理 `//evil.com` 的协议相对URL
  - 使用 `'://' not in path` 而未防止 `//` 绕过，此种检查无法阻止 `//evil.com` 形式的协议相对URL
  - 使用 `urlparse()` 解析但仅检查 `scheme == ''` 而未同时验证 `netloc == ''`，协议相对URL虽然 scheme 为空但 netloc 会被解析出来
  - 路径验证中未考虑 URL 编码绕过（`%2f`、`%2e` 等）或反斜杠绕过（`\` 在某些浏览器中表现如 `/`）
  - 验证通过后使用了原始输入而非验证结果，后续框架的自动解码可能导致绕过
- 通过 PoC 验证：访问 `/redirect?path=//evil.com` 观察是否成功重定向至外部域名

**误报的特征**

- 重定向URL完全硬编码或从服务端配置生成，不受用户输入影响
- 虽接收路径参数但通过严格的URL解析与检查：必须验证 `urlparse(path).scheme == ''` 且 `urlparse(path).netloc == ''` 同时满足
- 在 URL 解码前进行验证，且验证阻止了所有可能的绕过序列
- 实现了路径白名单机制，用户输入只能匹配预定义的路径集合（如 `/dashboard`、`/profile` 等），使用 `if path in ALLOWED_PATHS` 进行严格控制
- 强制将用户输入转换为相对路径：`redirect('/' + path.lstrip('/'))` 或使用 `urllib.parse.quote()` 对路径进行编码以防止特殊字符解释

**代码异味的表现**

- 存在路径验证逻辑，但验证方式过于简单（如仅前缀检查），虽未直接构成漏洞但规范性不足
- 有多个重定向点，部分进行了相对路径验证，部分完全未验证，验证逻辑不一致
- 使用了自定义的验证函数，但其实现方式明显存在规避空间（未全面考虑各种绕过技巧）
- 存在注释说明验证意图（如 "仅允许相对路径重定向"），但代码实现未能完全对应该意图
- 验证逻辑依赖于字符串操作而非完整的 URL 解析库

## Low risk

低风险情况的评级标准：

**完整的URL解析与严格检查**

- 代码使用 `urllib.parse.urlparse()` 对用户输入进行完整解析
- 验证 `parsed_url.scheme` 必须为空字符串（不允许 `http`、`https`、`javascript` 等）
- 验证 `parsed_url.netloc` 必须为空字符串（确保不包含域名）
- 两个条件同时满足才允许重定向，例如：
  ```python
  from urllib.parse import urlparse
  parsed = urlparse(path)
  if parsed.scheme or parsed.netloc:
      return redirect('/')  # 拒绝重定向
  return redirect(path)
  ```

**路径格式的严格限制**

- 使用正则表达式限制路径格式，如 `^/[a-zA-Z0-9/_-]+$`，禁止 `..`、`//`、反斜杠等特殊序列
  ```python
  import re
  if not re.match(r'^/[a-zA-Z0-9/_-]+$', path):
      return redirect('/')
  return redirect(path)
  ```
- 在验证前进行 URL 编码规范化（先进行 `urllib.parse.unquote()` 解码，再对解码后的结果验证）
- 使用 `urllib.parse.urlparse().path` 只提取路径部分，确保其他成分被忽略

**相对路径的强制约束**

- 代码明确拒绝任何包含协议相对URL特征的输入：`if path.startswith('//'): return redirect('/')`
- 使用预定义的安全路径前缀与用户输入拼接：
  ```python
  safe_prefix = "/app"
  sanitized_path = path.lstrip('/').replace('..', '').replace('//', '/')
  final_path = safe_prefix + '/' + sanitized_path
  ```
- 确保最终的重定向URL在编码和语义上都是相对的

**防御性的空值与异常处理**

- 用户输入为空时默认重定向至首页或安全页面，存在显式的非空检查
- 对 `urlparse()` 的结果进行安全处理，异常情况下拒绝重定向
- 在 Flask/Django 中使用框架内置的安全函数（如 `werkzeug.security.safe_str_cmp()` 进行白名单对比）

**跨模块验证一致性**

- 所有涉及重定向的代码点都调用同一个验证函数，确保逻辑一致
  ```python
  def is_safe_redirect(url):
      """验证URL是否可以安全重定向"""
      from urllib.parse import urlparse
      parsed = urlparse(url)
      return parsed.scheme == '' and parsed.netloc == ''

  @app.route('/redirect')
  def safe_redirect():
      path = request.args.get('path', '/')
      if is_safe_redirect(path):
          return redirect(path)
      return redirect('/')
  ```
- 验证函数有明确的文档说明其检查内容，便于维护和审计
- 考虑使用社区验证过的 URL 验证库（如 `validators` 库配合白名单）而非完全自行实现
