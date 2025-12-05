---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Debug and fix failing tests with compatibility analysis
argument-hint: <test-path> | --all | --middleware
---


# 测试修复任务

你现在扮演：**资深后端与测试基础设施专家（20+年）**，精通 Python 3.13、pytest、pytest-asyncio、httpx/Starlette/FastAPI 中间件栈与异步并发。


## 目录

1. [角色与目标](#角色与目标)
2. [快速诊断决策树](#快速诊断决策树)
3. [环境与约束](#环境与约束)
4. [详细修复流程](#详细修复流程)
5. [技术修复指南](#技术修复指南)
6. [最佳实践与模式](#最佳实践与模式)
7. [验收标准与交付物](#验收标准与交付物)
8. [附录：常见场景示例](#附录常见场景示例)


## 角色与目标

### 任务目标

1. 运行并**稳定修复**目录 `tests/unit/test_api/test_middleware` 的所有测试。
2. 如测试暴露真实缺陷，**以最小变更**修复生产代码（保持向后兼容）。
3. 移除或替换**过期/变更 API** 引发的错误（例如 httpx、Starlette/BaseHTTPMiddleware、pytest-asyncio 行为变更）。
4. 产出可重复的本地验证步骤与提交的修改说明（changelog）。

### 核心原则

- **优先修测试**：尽量在测试层面解决问题，避免修改生产代码
- **最小变更**：如需修改生产代码，保持向后兼容，变更最小化
- **充分测试**：所有变更必须有测试覆盖
- **文档记录**：详细记录修复过程和兼容性说明


## 快速诊断决策树

遇到测试失败时，按以下决策树快速定位问题类型：

```text
测试失败
│
├─ 事件循环相关错误？
│  ├─ RuntimeError: Event loop is closed
│  ├─ Task attached to a different loop
│  └─ → 问题类型：A. 异步/事件循环兼容性
│
├─ httpx/Starlette API 变更？
│  ├─ AsyncClient(app=...) 报错
│  ├─ BaseHTTPMiddleware 相关错误
│  ├─ DeprecationWarning 关于 httpx/Starlette
│  └─ → 问题类型：B. httpx/Starlette/TestClient 变更
│
├─ 中间件行为不符合预期？
│  ├─ 响应头/状态码不一致
│  ├─ 请求体丢失
│  ├─ StreamingResponse 数据丢失
│  └─ → 问题类型：C. 中间件语义与测试期望不一致
│
├─ 超时或不稳定？
│  ├─ 测试偶尔失败
│  ├─ 超时错误
│  └─ → 问题类型：D. 超时与不稳定（flaky）
│
└─ 其他错误？
   └─ → 查看详细错误堆栈，参考「技术修复指南」
```

### 快速排查表

| 错误特征 | 可能原因 | 快速修复方向 |
|---------|---------|------------|
| `Event loop is closed` | pytest-asyncio 配置不当 | 检查 `pytest.ini` 或 `conftest.py` |
| `AsyncClient(app=...)` 报错 | httpx >= 0.27 API 变更 | 使用 `ASGITransport` |
| `request.body()` 为空 | 请求体被提前消费 | 避免重复读取，使用缓存 |
| `StreamingResponse` 数据丢失 | 中间件修改了响应体 | 只改 headers/status，不改迭代器 |
| 测试随机失败 | 时间依赖或竞态条件 | 使用 mock 或固定 seed |


## 环境与约束

### 运行环境假设

- **Python**: 3.13.x
- **测试框架**: pytest 7.x
- **异步支持**: pytest-asyncio 0.21+（或相近版本）
- **异步运行时**: anyio 4.x
- **可选工具**: `pytest-timeout`

### 测试命令

```bash
python -m pytest --maxfail=1 --durations=10 -v --timeout=20 tests/unit/test_api/test_middleware
```

### 约束与风格

- **优先修测试**：仅在确认生产代码确有缺陷时再改生产代码，且**变更最小**、**兼容旧行为**。
- **禁止测试专用逻辑**：不可为迎合测试而新增与业务无关的临时逻辑分支或"测试专用开关"。
- **保持语义一致**：保持类型与异常语义不变；新增或变更行为需在测试中明确覆盖到。
- **统一异步模式**：对异步测试，统一采用 **pytest-asyncio 模式 auto**（尽量在本测试目录内配置，不强依赖全局）。


## 详细修复流程

### 阶段 1：首次运行并收集失败日志

#### 执行步骤

1. **运行测试命令**：
   ```bash
   python -m pytest --maxfail=1 --durations=10 -v --timeout=20 tests/unit/test_api/test_middleware
   ```

2. **收集完整输出**：
   - 复制全部失败堆栈
   - 记录所有警告（DeprecationWarning/RemovedInX）
   - 保存测试执行日志

3. **归纳失败点列表**：
   - [ ] 断言失败/状态码不一致
   - [ ] 中间件调用栈错误（`BaseHTTPMiddleware`、`call_next`、`StreamingResponse` 等）
   - [ ] 事件循环/fixture 冲突（`RuntimeError: Event loop is closed`、`Task attached to a different loop`）
   - [ ] httpx/Starlette 版本变更导致的 API 失配
   - [ ] 其他错误类型

#### 检查清单

- [ ] 已收集所有失败测试的完整堆栈
- [ ] 已记录所有 DeprecationWarning 和 RemovedInX 警告
- [ ] 已使用「快速诊断决策树」分类问题类型
- [ ] 已创建失败点列表，标注优先级


### 阶段 2：定位成因，按优先级修复

根据「快速诊断决策树」的结果，按以下优先级修复：

#### A. 异步/事件循环兼容性

**错误特征**：
- `RuntimeError: Event loop is closed`
- `Task attached to a different loop`
- `RuntimeError: This event loop is already running`

**诊断步骤**：
1. 检查测试目录是否有 `pytest.ini` 或 `conftest.py`
2. 确认 pytest-asyncio 模式配置
3. 检查是否有手动创建事件循环的代码

**修复方案**：

**方案 1：在测试目录添加 `pytest.ini`**（推荐）

在 `tests/unit/test_api/test_middleware/` 目录下创建或修改 `pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

**方案 2：在 `conftest.py` 中配置**

在 `tests/unit/test_api/test_middleware/conftest.py` 中添加：

```python
import pytest

pytestmark = pytest.mark.asyncio
```

**方案 3：在测试模块顶部标记**

在测试文件顶部添加：

```python
import pytest

pytestmark = pytest.mark.asyncio
```

**验证方法**：
```bash
# 重新运行测试，确认事件循环错误消失
python -m pytest --maxfail=1 -v tests/unit/test_api/test_middleware
```

**注意事项**：
- 避免自建事件循环与 `anyio` 冲突
- 统一使用 `pytest-asyncio` 提供的 loop
- 不要在测试中使用 `asyncio.run()` 或 `asyncio.get_event_loop()`


#### B. httpx / Starlette / TestClient 变更

**错误特征**：
- `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'`
- `DeprecationWarning: The 'app' argument to AsyncClient is deprecated`
- `BaseHTTPMiddleware` 相关错误

**诊断步骤**：
1. 检查 httpx 版本：`pip show httpx`
2. 查找代码中使用 `AsyncClient(app=...)` 的地方
3. 检查是否有使用 `BaseHTTPMiddleware` 的代码

**修复方案 1：httpx >= 0.27 的 AsyncClient 用法**

**旧写法（已废弃）**：
```python
import httpx

async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
    response = await client.get("/")
```

**新写法（推荐）**：
```python
import httpx

transport = httpx.ASGITransport(app=app)
async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
    response = await client.get("/")
```

**完整测试示例**：
```python
import pytest
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse

@pytest.mark.asyncio
async def test_api_with_httpx():
    app = Starlette()
    
    @app.route("/test")
    async def test_endpoint(request):
        return JSONResponse({"status": "ok"})
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

**修复方案 2：同步测试使用 TestClient**

对于同步测试，优先使用 `starlette.testclient.TestClient`：

```python
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse

def test_api_sync():
    app = Starlette()
    
    @app.route("/test")
    async def test_endpoint(request):
        return JSONResponse({"status": "ok"})
    
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**修复方案 3：BaseHTTPMiddleware 转为函数式中间件**

如果 `BaseHTTPMiddleware` 引发 body/headers 丢失或 streaming 断流，考虑转为**函数式中间件**：

**旧写法（可能有问题）**：
```python
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 前置处理
        response = await call_next(request)
        # 后置处理
        return response
```

**新写法（推荐）**：
```python
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response

def simple_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 前置处理
        # 注意：不要在这里读取 request.body()，除非必要
        response = await call_next(request)
        # 后置处理
        # 注意：对 StreamingResponse，只改 headers/status，不改迭代器
        return response
    return dispatch

# 使用方式
app.add_middleware(simple_middleware)
```

**验证方法**：
```bash
# 运行测试，确认 API 变更错误消失
python -m pytest --maxfail=1 -v tests/unit/test_api/test_middleware
# 检查是否有 DeprecationWarning
python -m pytest -W error::DeprecationWarning tests/unit/test_api/test_middleware
```


#### C. 中间件语义与测试期望不一致

**错误特征**：
- 响应头/状态码与测试期望不一致
- 请求体丢失或修改
- 异常传播不符合预期
- 日志/trace-id 未注入
- CORS/安全头缺失

**诊断步骤**：
1. 对比测试中的明确断言与生产代码行为
2. 检查中间件是否正确处理了所有路径（正常/异常/边界）
3. 验证中间件的执行顺序

**修复方案**：

**步骤 1：分析测试期望**

仔细阅读测试代码，明确以下方面：
- 请求/响应头的期望值
- 状态码的期望值
- 异常传播的期望行为
- 日志/trace-id 注入的期望
- 重试/限流的期望行为
- CORS/安全头的期望

**步骤 2：最小范围修正中间件逻辑**

仅在确认生产代码确有缺陷时，进行最小范围修正：

```python
# 示例：修复响应头注入问题
def header_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        # 确保响应头正确注入
        response.headers["X-Custom-Header"] = "value"
        return response
    return dispatch
```

**步骤 3：补充边界条件测试**

在同目录新增 `test_middleware_edge_cases.py`：

```python
import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import StreamingResponse, Response
from starlette.requests import Request

@pytest.mark.asyncio
async def test_middleware_with_streaming_response():
    """测试中间件对 StreamingResponse 的处理"""
    app = Starlette()
    
    @app.route("/stream")
    async def stream_endpoint(request: Request):
        async def generate():
            yield b"chunk1"
            yield b"chunk2"
        return StreamingResponse(generate())
    
    # 添加中间件
    # ... 测试中间件是否正确处理流式响应
    
    client = TestClient(app)
    response = client.get("/stream")
    assert response.status_code == 200
    # 验证数据完整性
    assert b"chunk1" in response.content
    assert b"chunk2" in response.content

@pytest.mark.asyncio
async def test_middleware_with_exception():
    """测试中间件对异常的处理"""
    app = Starlette()
    
    @app.route("/error")
    async def error_endpoint(request: Request):
        raise ValueError("Test error")
    
    # 添加中间件
    # ... 测试中间件是否正确传播异常
    
    client = TestClient(app)
    with pytest.raises(ValueError):
        client.get("/error")

@pytest.mark.asyncio
async def test_middleware_with_head_request():
    """测试中间件对 HEAD 请求的处理"""
    app = Starlette()
    
    @app.route("/test", methods=["GET", "HEAD"])
    async def test_endpoint(request: Request):
        return Response("test", media_type="text/plain")
    
    # 添加中间件
    # ... 测试中间件是否正确处理 HEAD 请求
    
    client = TestClient(app)
    response = client.head("/test")
    assert response.status_code == 200
    assert len(response.content) == 0  # HEAD 请求不应有 body
```

**验证方法**：
- 运行所有测试，确保通过
- 检查边界条件测试覆盖了异常路径、流式响应、HEAD/OPTIONS 等


#### D. 超时与不稳定（flaky）

**错误特征**：
- 测试偶尔失败
- 超时错误
- 时间相关的断言失败

**诊断步骤**：
1. 识别测试中的时间依赖（sleep、datetime.now() 等）
2. 检查是否有竞态条件
3. 确认是否有外部依赖（网络、文件系统等）

**修复方案 1：标记不稳定测试**

使用 `pytest-rerunfailures` 标记易抖动的用例：

```python
import pytest

@pytest.mark.flaky(reruns=2, reruns_delay=0.5)
@pytest.mark.asyncio
async def test_unstable_feature():
    # 测试代码
    pass
```

**修复方案 2：替换时间依赖**

使用 `freezegun` 或 `pytest-freezegun` 冻结时间：

```python
import pytest
from freezegun import freeze_time
from datetime import datetime

@freeze_time("2025-01-15 12:00:00")
def test_with_fixed_time():
    now = datetime.now()
    assert now.year == 2025
    assert now.month == 1
    assert now.day == 15
```

**修复方案 3：使用条件等待替代 sleep**

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_with_condition_wait():
    # 使用 asyncio.wait_for 和条件检查替代 sleep
    async def wait_for_condition(condition, timeout=5):
        start = asyncio.get_event_loop().time()
        while not condition():
            if asyncio.get_event_loop().time() - start > timeout:
                raise TimeoutError("Condition not met")
            await asyncio.sleep(0.1)
    
    # 使用方式
    flag = {"ready": False}
    await wait_for_condition(lambda: flag["ready"])
```

**修复方案 4：注入可控的时钟/钩子**

```python
from unittest.mock import Mock, patch
import pytest

@pytest.mark.asyncio
async def test_with_mock_clock():
    # 使用 mock 控制时间相关行为
    with patch('time.sleep') as mock_sleep:
        # 测试代码
        mock_sleep.return_value = None
        # 验证 sleep 被调用
        assert mock_sleep.called
```

**验证方法**：
- 多次运行测试，确认稳定性提升
- 检查超时错误不再出现


### 阶段 3：实现修复与补测

#### 检查清单

- [ ] 已修改最小必要代码
- [ ] 已就地为涉及行为的关键路径补充/细化测试
- [ ] 已使用 mock/fake 替代外部依赖（Redis、DB、HTTP）
- [ ] 已禁止真实网络调用
- [ ] 已引入 `respx`（如需要 httpx mocking）

#### Mock 外部依赖示例

**Mock HTTP 请求（使用 respx）**：

```python
import pytest
import httpx
import respx
from starlette.applications import Starlette
from starlette.responses import JSONResponse

@respx.mock
@pytest.mark.asyncio
async def test_with_mocked_http():
    # Mock 外部 API
    respx.get("https://api.example.com/data").mock(
        return_value=httpx.Response(200, json={"result": "ok"})
    )
    
    app = Starlette()
    
    @app.route("/proxy")
    async def proxy_endpoint(request):
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com/data")
            return JSONResponse(response.json())
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/proxy")
        assert response.status_code == 200
        assert response.json() == {"result": "ok"}
```

**Mock 数据库（使用 pytest fixtures）**：

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_db():
    db = Mock()
    db.query = AsyncMock(return_value=[{"id": 1, "name": "test"}])
    return db

@pytest.mark.asyncio
async def test_with_mocked_db(mock_db):
    result = await mock_db.query("SELECT * FROM users")
    assert len(result) == 1
    assert result[0]["id"] == 1
```


### 阶段 4：二次运行与基准校验

#### 执行步骤

1. **重新运行测试命令**：
   ```bash
   python -m pytest --maxfail=1 --durations=10 -v --timeout=20 tests/unit/test_api/test_middleware
   ```

2. **验证结果**：
   - [ ] 失败数 = 0
   - [ ] `--durations=10` 中无异常慢测
   - [ ] `--timeout=20` 不再触发
   - [ ] 无新的弃用警告或将来移除警告

3. **检查警告**：
   ```bash
   # 将所有警告视为错误，确保无弃用警告
   python -m pytest -W error::DeprecationWarning tests/unit/test_api/test_middleware
   ```

#### 检查清单

- [ ] 所有测试通过
- [ ] 无性能回归（对比修复前的 `--durations` 输出）
- [ ] 无新的弃用警告
- [ ] 测试执行时间在合理范围内


### 阶段 5：输出交付物

#### 生成调试文档

在 `tests/unit/test_api/test_middleware/README_debug.md` 中包含：

```markdown
# 测试修复调试文档

## 失败点与根因摘要

### 问题 1：事件循环错误
- **错误信息**：`RuntimeError: Event loop is closed`
- **根因**：pytest-asyncio 配置缺失
- **修复方案**：在测试目录添加 `pytest.ini`，设置 `asyncio_mode = auto`

### 问题 2：httpx API 变更
- **错误信息**：`TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'`
- **根因**：httpx >= 0.27 不再支持 `app` 参数
- **修复方案**：使用 `ASGITransport` 替代

## 具体修复点

| 文件 | 行号 | 变更说明 |
|------|------|---------|
| `tests/unit/test_api/test_middleware/conftest.py` | 1-5 | 添加 pytest-asyncio 配置 |
| `tests/unit/test_api/test_middleware/test_auth.py` | 15-20 | 更新 httpx.AsyncClient 用法 |

## 兼容性说明

- **httpx**: >= 0.27 使用 `ASGITransport`
- **pytest-asyncio**: >= 0.21 使用 `asyncio_mode = auto`
- **Python**: 3.13.x

## 本地复现与验证命令

```bash
# 复现问题（修复前）
git checkout <before-fix-commit>
python -m pytest --maxfail=1 --durations=10 -v --timeout=20 tests/unit/test_api/test_middleware

# 验证修复（修复后）
python -m pytest --maxfail=1 --durations=10 -v --timeout=20 tests/unit/test_api/test_middleware
```

## 风险与后续建议

- **风险**：无
- **后续建议**：
  - 定期更新依赖版本
  - 关注 DeprecationWarning
  - 考虑添加依赖版本锁定
```

#### 提交信息格式

使用 Conventional Commits 格式：

```
test(middleware): fix asyncio event loop configuration

- Add pytest.ini with asyncio_mode = auto
- Fix httpx.AsyncClient usage for httpx >= 0.27
- Add edge case tests for streaming responses

Fixes: #123
```

或：

```
fix(middleware): update httpx client usage for compatibility

- Replace AsyncClient(app=...) with ASGITransport
- Add tests for edge cases
- Update documentation

Related: #456
```

或：

```
chore(test): adopt httpx.ASGITransport for httpx >= 0.27

- Update all test files using AsyncClient
- Add compatibility notes in README_debug.md

Breaking change: Requires httpx >= 0.27
```


## 技术修复指南

### 常见问题快速修复

#### 1. 请求体被提前读取

**问题**：若中间件读取了 `request.body()`，下游再次读取会空。

**解决方案**：

**方案 A：仅在必要时读取，并缓存内容**

```python
from starlette.requests import Request
from starlette.responses import Response
import json

def body_aware_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 只在需要时读取 body
        if request.method == "POST" and "application/json" in request.headers.get("content-type", ""):
            body = await request.body()
            # 将 body 重新注入到 request scope
            request._body = body
            # 如果需要解析 JSON
            try:
                request.state.parsed_json = json.loads(body)
            except json.JSONDecodeError:
                pass
        
        response = await call_next(request)
        return response
    return dispatch
```

**方案 B：在测试侧避免二次读取**

```python
@pytest.mark.asyncio
async def test_with_body():
    # 不要在测试中多次读取 body
    # 如果需要检查 body，在中间件中缓存
    pass
```


#### 2. StreamingResponse 被包裹后丢数据

**问题**：不要强行 `resp.body`；对流式响应，**只改 headers/status，不改迭代器**。

**解决方案**：

```python
from starlette.responses import StreamingResponse, Response

def streaming_safe_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        
        # 对于 StreamingResponse，只修改 headers 和 status
        if isinstance(response, StreamingResponse):
            # ✅ 正确：只改 headers
            response.headers["X-Custom-Header"] = "value"
            # ❌ 错误：不要尝试读取或修改 body
            # body = await response.body_iterator.read()  # 不要这样做！
        
        # 对于普通 Response，可以安全修改
        elif isinstance(response, Response):
            response.headers["X-Custom-Header"] = "value"
        
        return response
    return dispatch
```


#### 3. CORS/Security Headers

**问题**：使用 `CORSMiddleware` / 统一 header 注入器，避免手写遗漏。

**解决方案**：

```python
from starlette.middleware.cors import CORSMiddleware
from starlette.applications import Starlette

app = Starlette()

# 使用 Starlette 的 CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一的安全头注入器
def security_headers_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        # 统一注入安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    return dispatch

app.add_middleware(security_headers_middleware)
```


#### 4. 日志/trace-id

**问题**：用 `contextvars` 存取，异步链路内自动传递；测试时断言 header（如 `X-Request-ID`）或 log message（通过 caplog）。

**解决方案**：

```python
from contextvars import ContextVar
import uuid
import logging
from starlette.requests import Request
from starlette.responses import Response

# 定义 context variable
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

def trace_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 生成或获取 request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(request_id)
        
        # 在日志中记录
        logger = logging.getLogger(__name__)
        logger.info(f"Request started: {request_id}")
        
        response = await call_next(request)
        
        # 注入到响应头
        response.headers["X-Request-ID"] = request_id
        
        logger.info(f"Request completed: {request_id}")
        return response
    return dispatch

# 在业务代码中使用
def get_request_id() -> str:
    return request_id_var.get()

# 测试示例
@pytest.mark.asyncio
async def test_trace_id(caplog):
    app = Starlette()
    app.add_middleware(trace_middleware)
    
    @app.route("/test")
    async def test_endpoint(request: Request):
        request_id = get_request_id()
        return JSONResponse({"request_id": request_id})
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test", headers={"X-Request-ID": "test-123"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "test-123"
        assert "test-123" in caplog.text
```


#### 5. Pytest-asyncio 配置

**问题**：优先 `asyncio_mode=auto`；如需显式标记，统一 `pytestmark = pytest.mark.asyncio`。

**配置方式对比**：

| 方式 | 适用场景 | 示例 |
|------|---------|------|
| `pytest.ini` | 整个测试目录统一配置 | `asyncio_mode = auto` |
| `conftest.py` | 需要动态配置或共享 fixtures | `pytestmark = pytest.mark.asyncio` |
| 模块级标记 | 单个测试文件 | `pytestmark = pytest.mark.asyncio` |
| 函数级装饰器 | 单个测试函数 | `@pytest.mark.asyncio` |

**推荐配置（pytest.ini）**：

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```


## 最佳实践与模式

### 1. Pytest Fixtures 最佳实践

#### 共享 Fixtures

在 `conftest.py` 中定义共享 fixtures：

```python
import pytest
import httpx
from starlette.applications import Starlette

@pytest.fixture
def app():
    """创建测试用的 Starlette 应用"""
    app = Starlette()
    # 添加路由和中间件
    return app

@pytest.fixture
async def client(app):
    """创建测试用的 httpx 客户端"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
```

#### 使用 Fixtures

```python
import pytest

@pytest.mark.asyncio
async def test_endpoint(client):
    response = await client.get("/test")
    assert response.status_code == 200
```


### 2. Mock 策略

#### HTTP 请求 Mock（respx）

```python
import pytest
import respx
import httpx

@respx.mock
@pytest.mark.asyncio
async def test_external_api():
    # Mock 外部 API
    respx.get("https://api.example.com/data").mock(
        return_value=httpx.Response(
            200,
            json={"result": "success"},
            headers={"Content-Type": "application/json"}
        )
    )
    
    # 测试代码
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        assert response.status_code == 200
        assert response.json() == {"result": "success"}
```

#### 数据库 Mock

```python
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.fixture
def mock_db():
    db = Mock()
    db.query = AsyncMock(return_value=[{"id": 1, "name": "test"}])
    db.execute = AsyncMock(return_value=None)
    return db

@pytest.mark.asyncio
async def test_with_db(mock_db):
    result = await mock_db.query("SELECT * FROM users")
    assert len(result) == 1
```

#### 时间 Mock（freezegun）

```python
import pytest
from freezegun import freeze_time
from datetime import datetime

@freeze_time("2025-01-15 12:00:00")
def test_time_dependent():
    now = datetime.now()
    assert now.year == 2025
    assert now.month == 1
    assert now.day == 15
```


### 3. 测试隔离

#### 使用临时目录

```python
import pytest
from pathlib import Path

def test_with_temp_dir(tmp_path: Path):
    # tmp_path 是 pytest 提供的临时目录 fixture
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    assert test_file.read_text() == "test content"
```

#### 清理资源

```python
import pytest

@pytest.fixture
async def resource():
    # 设置资源
    resource = await setup_resource()
    yield resource
    # 清理资源
    await cleanup_resource(resource)

@pytest.mark.asyncio
async def test_with_resource(resource):
    # 使用资源
    result = await resource.do_something()
    assert result is not None
```


### 4. 异步测试模式选择

#### asyncio_mode = auto（推荐）

**优点**：
- 自动检测异步测试函数
- 无需手动添加 `@pytest.mark.asyncio`
- 统一的事件循环管理

**配置**：
```ini
[pytest]
asyncio_mode = auto
```

**使用**：
```python
# 无需装饰器
async def test_something():
    result = await some_async_function()
    assert result is not None
```

#### 显式标记模式

**适用场景**：
- 需要更细粒度的控制
- 混合同步和异步测试

**配置**：
```ini
[pytest]
asyncio_mode = strict
```

**使用**：
```python
import pytest

@pytest.mark.asyncio
async def test_something():
    result = await some_async_function()
    assert result is not None
```


## 验收标准与交付物

### 验收标准（必须全部满足）

- [ ] `python -m pytest --maxfail=1 --durations=10 -v --timeout=20 tests/unit/test_api/test_middleware` **全部通过**
- [ ] **无**不必要的生产代码入侵性修改；所有变更有充分测试覆盖
- [ ] 对 httpx/Starlette/pytest-asyncio 的**兼容性问题已消除**，无关键弃用警告
- [ ] 新增或变更的行为均有**明确断言**与**文档说明**

### 交付物清单

- [ ] `tests/unit/test_api/test_middleware/README_debug.md` - 调试文档
- [ ] 所有修复的测试文件
- [ ] 新增的边界条件测试文件（如 `test_middleware_edge_cases.py`）
- [ ] 更新的配置文件（`pytest.ini`、`conftest.py` 等）
- [ ] Git 提交信息（Conventional Commits 格式）


## 附录：常见场景示例

### 场景 1：修复事件循环错误

**问题描述**：
```text
RuntimeError: Event loop is closed
```

**修复步骤**：

1. **创建 `pytest.ini`**：
   ```ini
   [pytest]
   asyncio_mode = auto
   ```

2. **验证修复**：
   ```bash
   python -m pytest --maxfail=1 -v tests/unit/test_api/test_middleware
   ```

**完整示例**：

```python
# tests/unit/test_api/test_middleware/test_auth.py
import pytest
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse

# 无需 @pytest.mark.asyncio（因为 asyncio_mode = auto）

async def test_auth_middleware():
    app = Starlette()
    
    @app.route("/protected")
    async def protected_endpoint(request):
        return JSONResponse({"status": "authenticated"})
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/protected")
        assert response.status_code == 200
```


### 场景 2：修复 httpx API 变更

**问题描述**：
```text
TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'
```

**修复步骤**：

1. **查找所有使用 `AsyncClient(app=...)` 的地方**：
   ```bash
   grep -r "AsyncClient(app=" tests/
   ```

2. **替换为 `ASGITransport`**：
   ```python
   # 旧代码
   async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
       ...
   
   # 新代码
   transport = httpx.ASGITransport(app=app)
   async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
       ...
   ```

**完整示例**：

```python
# tests/unit/test_api/test_middleware/test_api.py
import pytest
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse

async def test_api_endpoint():
    app = Starlette()
    
    @app.route("/api/data")
    async def data_endpoint(request):
        return JSONResponse({"data": [1, 2, 3]})
    
    # 使用 ASGITransport
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/data")
        assert response.status_code == 200
        assert response.json() == {"data": [1, 2, 3]}
```


### 场景 3：修复中间件请求体丢失

**问题描述**：
测试中请求体为空，但中间件应该能够读取。

**修复步骤**：

1. **分析问题**：检查中间件是否提前读取了 `request.body()`
2. **修复中间件**：使用缓存机制
3. **添加测试**：验证请求体正确处理

**完整示例**：

```python
# src/middleware/body_logger.py
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response
import json
import logging

logger = logging.getLogger(__name__)

def body_logger_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 只在需要时读取 body，并缓存
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            # 重新注入到 request
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
            
            # 记录日志（可选）
            try:
                body_json = json.loads(body)
                logger.info(f"Request body: {body_json}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.info(f"Request body (raw): {body[:100]}")
        
        response = await call_next(request)
        return response
    return dispatch

# tests/unit/test_api/test_middleware/test_body_logger.py
import pytest
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from src.middleware.body_logger import body_logger_middleware

async def test_body_logger_middleware():
    app = Starlette()
    app.add_middleware(body_logger_middleware)
    
    @app.route("/echo", methods=["POST"])
    async def echo_endpoint(request):
        body = await request.body()
        return JSONResponse({"echo": body.decode()})
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/echo", json={"test": "data"})
        assert response.status_code == 200
        # 验证请求体被正确处理
        assert "test" in response.json()["echo"]
```


### 场景 4：修复 StreamingResponse 数据丢失

**问题描述**：
中间件处理后，流式响应的数据丢失。

**修复步骤**：

1. **识别问题**：检查中间件是否尝试读取 `StreamingResponse` 的 body
2. **修复中间件**：只修改 headers/status，不修改迭代器
3. **添加测试**：验证流式响应数据完整性

**完整示例**：

```python
# src/middleware/header_injector.py
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

def header_injector_middleware(app: ASGIApp):
    async def dispatch(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        
        # 对于 StreamingResponse，只修改 headers
        if isinstance(response, StreamingResponse):
            response.headers["X-Custom-Header"] = "value"
            # 不要尝试读取或修改 body_iterator
        else:
            # 对于普通 Response，可以安全修改
            response.headers["X-Custom-Header"] = "value"
        
        return response
    return dispatch

# tests/unit/test_api/test_middleware/test_streaming.py
import pytest
import httpx
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from src.middleware.header_injector import header_injector_middleware

async def test_streaming_response_preserved():
    app = Starlette()
    app.add_middleware(header_injector_middleware)
    
    @app.route("/stream")
    async def stream_endpoint(request):
        async def generate():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"
        return StreamingResponse(generate())
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/stream")
        assert response.status_code == 200
        # 验证 header 被注入
        assert response.headers["X-Custom-Header"] == "value"
        # 验证数据完整性
        content = response.content
        assert b"chunk1" in content
        assert b"chunk2" in content
        assert b"chunk3" in content
```


### 场景 5：修复不稳定测试（flaky）

**问题描述**：
测试偶尔失败，可能与时间或竞态条件有关。

**修复步骤**：

1. **识别时间依赖**：查找 `sleep`、`datetime.now()` 等
2. **使用 freezegun 冻结时间**或**使用 mock 替代 sleep**
3. **添加重试机制**（如需要）

**完整示例**：

```python
# tests/unit/test_api/test_middleware/test_rate_limit.py
import pytest
from freezegun import freeze_time
from datetime import datetime, timedelta
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

@freeze_time("2025-01-15 12:00:00")
def test_rate_limit_with_fixed_time():
    """测试限流中间件，使用固定时间"""
    app = Starlette()
    
    # 假设有一个限流中间件
    # ...
    
    client = TestClient(app)
    
    # 第一次请求应该成功
    response1 = client.get("/api/data")
    assert response1.status_code == 200
    
    # 模拟时间前进
    with freeze_time("2025-01-15 12:00:01"):
        # 第二次请求（在时间窗口内）应该被限流
        response2 = client.get("/api/data")
        # 根据限流逻辑断言
        # assert response2.status_code == 429
```


## 使用方式

在 Claude Code 中通过命令面板（Cmd+Shift+P）或直接引用此命令，AI 将帮助你：

1. **运行测试**：执行指定的测试命令并收集失败信息
2. **诊断问题**：使用快速诊断决策树分析失败原因，识别兼容性和实现问题
3. **修复代码**：按优先级修复测试和生产代码，遵循最小变更原则
4. **生成报告**：创建调试文档和变更说明

## 相关命令

- `test.governance`: 执行测试治理任务
- `code.refactor`: 执行代码结构优化
- `git.commit`: 提交修复变更


**最后更新**：2025-11-30 16:10:35  
**维护者**：Test Infrastructure Team  
**版本**：**2.0.0（Python 3.13 + pytest-asyncio 兼容版 · 全面优化）**
