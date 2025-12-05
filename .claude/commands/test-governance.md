---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Comprehensive test governance with coverage analysis and CI setup
argument-hint: [optional: target module or --full]
---


# Python 测试治理任务

> **适用范围**：任何 Python 项目  
> **硬性约束**：**禁止修改生产代码（如 `src/**`）**；治理仅限测试与测试相关配置/脚本  
> **核心目标**：结构清晰、覆盖率可量化、执行快速、文档完备、可一键接入 CI


## 快速开始

### 核心原则速览

1. **零生产代码改动**：所有变更仅限于 `tests/**`、`conftest.py`、`pytest.ini` 等测试相关配置
2. **1:1 单元测试映射**：`src/<pkg>/<path>.py` ↔ `tests/unit/<pkg>/test_<path>.py`
3. **覆盖率门槛**：单元测试 ≥85%，集成测试 ≥80%，关键模块 ≥90%，整体 ≥85%
4. **性能要求**：快测 <1s，慢测 <5s，集成 <10s，整套 <5min
5. **质量检查**：所有静态检查工具（flake8、black、isort、mypy、bandit）必须通过

### 快速检查清单

- [ ] 测试目录结构符合规范（`tests/unit/`、`tests/integration/` 等）
- [ ] 单元测试文件与源代码文件 1:1 映射
- [ ] 所有测试文件使用 `test_*.py` 命名
- [ ] 测试类以 `Test*` 开头，测试函数以 `test_*` 开头
- [ ] 覆盖率达标（运行 `pytest --cov=src --cov-fail-under=85`）
- [ ] 所有测试标记正确（`@pytest.mark.unit`、`@pytest.mark.integration` 等）
- [ ] 无真实外网调用，所有外部依赖已 mock
- [ ] 静态检查通过（flake8、black、isort、mypy、bandit）


## 1. 角色与原则

### 角色定位

你扮演 **测试平台与质量治理负责人（20+年经验）**，具备以下能力：

- 熟练使用：`pytest`、`pytest-xdist`、`pytest-timeout`、`pytest-cov`、`hypothesis`、`responses`、`freezegun`、`pytest-asyncio`、`pytest-mock`、`faker`
- 深度理解：测试金字塔、AAA 模式、测试隔离、数据驱动测试、属性测试

### 核心原则

- **AAA（Arrange-Act-Assert）**：每个测试明确分为准备、执行、断言三个阶段
- **单测独立可复现**：测试之间无依赖，可单独运行，结果一致
- **最小外部依赖**：优先使用 mock，避免真实外部服务
- **禁真实外网**：网络请求一律使用 `responses` 或 `pytest-mock` 模拟
- **零生产代码改动**：遇到可测性障碍时，采用更强 mock/契约/黑盒行为测试


## 2. 工作范围

### 允许变更

- `tests/**`：所有测试代码和测试数据
- `conftest.py`：pytest 配置文件
- `pytest.ini`、`pyproject.toml`、`setup.cfg`：测试相关配置
- `.github/workflows/*.yml`：CI 配置文件

### 禁止变更

- `src/**` 及一切业务实现代码
- 生产环境的配置文件
- 业务逻辑相关的依赖项

### 可测性障碍处理

若遇到因"禁止改动生产代码"导致的可测性障碍：

1. **优先方案**：使用更强的 mock（如 `unittest.mock.patch`、`pytest-mock`）
2. **备选方案**：采用契约测试或黑盒行为测试
3. **必须记录**：在报告中说明受阻点、采用的替代方案和残余风险

### 发现生产代码 Bug 的处理方式

**重要原则**：测试治理过程中发现生产代码 bug 是正常且有益的，但**测试治理任务本身不应修复这些 bug**。

**处理流程**：

1. **记录 Bug**：
   - 在 `reports/test_audit.md` 中创建"发现的生产代码问题"章节
   - 详细描述：bug 位置、复现步骤、预期行为、实际行为、影响范围
   - 提供最小复现用例（可作为测试用例的基础）

2. **编写测试用例**：
   - 为发现的 bug 编写**失败的测试用例**（测试当前错误行为）
   - 测试用例应明确标注：`# TODO: 此测试暴露了生产代码 bug，待修复`
   - 使用 `@pytest.mark.xfail(reason="生产代码 bug，待修复")` 标记，避免阻塞测试套件

3. **优先级评估**：
   - **严重 bug**（崩溃、数据丢失、安全漏洞）：立即上报，建议暂停测试治理或创建独立 issue
   - **一般 bug**（功能异常、边界情况）：记录在报告中，建议后续修复
   - **代码质量问题**（可读性、性能）：记录在报告中，建议代码审查时处理

4. **测试策略**：
   - **不修改生产代码**：即使知道如何修复，也不在测试治理过程中修复
   - **测试先行**：先写测试用例暴露 bug，为后续修复提供基础
   - **隔离测试**：使用 mock 绕过 bug，确保其他功能测试不受影响

5. **报告格式**：

```markdown
## 发现的生产代码问题

### 问题 1：[简要描述]

**位置**：`src/path/to/file.py:行号`

**严重程度**：严重/一般/轻微

**描述**：
- 预期行为：[描述]
- 实际行为：[描述]
- 影响范围：[描述]

**复现步骤**：
1. [步骤1]
2. [步骤2]

**测试用例**：`tests/unit/path/to/test_file.py::test_bug_reproduction`

**建议**：
- [ ] 创建独立 issue
- [ ] 标记为 blocker（如为严重 bug）
- [ ] 在后续 sprint 中修复

**备注**：此问题在测试治理过程中发现，已编写测试用例但未修复生产代码。
```

6. **后续处理建议**：
   - 在 PR 草案中明确列出所有发现的问题
   - 建议创建独立的 bug fix issue 或 task
   - 如果 bug 严重，建议先修复 bug 再继续测试治理

**示例**：

```python
# tests/unit/config/test_config.py
import pytest

@pytest.mark.unit
@pytest.mark.xfail(reason="生产代码 bug：config.py 第 42 行未处理空值，待修复")
def test_load_config_with_empty_value():
    """此测试暴露了生产代码的一个 bug"""
    # Arrange
    config_data = {"key": ""}  # 空值
    
    # Act
    result = load_config(config_data)
    
    # Assert
    # 当前会抛出 KeyError，但应该返回默认值
    assert result.get("key") == "default"  # 期望行为
```

**关键点**：
- ✅ **应该做**：记录 bug、编写测试用例、评估优先级、在报告中说明
- ❌ **不应该做**：直接修复生产代码、忽略 bug、修改测试以绕过 bug

## 4. 目录与命名规范

### 标准目录结构

```text
src/
  <pkg>/...           # 业务代码（禁止改动）

tests/
  unit/               # 单元测试（1:1 文件映射）
    <pkg>/
      test_*.py
  integration/        # 集成/流程测试（跨模块/组件）
  performance/        # 性能/基准测试
  fixtures/           # 测试样例与合成数据
  utils/              # 通用断言/伪造器/匹配器/工厂
conftest.py           # pytest 配置和共享 fixtures
pytest.ini            # pytest 配置文件
```

### 1:1 单元测试映射规则

**映射规则**：`src/<pkg>/<path>.py` ↔ `tests/unit/<pkg>/test_<path>.py`

**示例**：
- `src/config/config.py` → `tests/unit/config/test_config.py`
- `src/core/io/loader.py` → `tests/unit/core/io/test_loader.py`
- `src/api/handlers/user.py` → `tests/unit/api/handlers/test_user.py`

**命名规范**：
- 测试文件：`test_<原文件名>.py`
- 测试类：以 `Test*` 开头（如 `TestConfigLoader`）
- 测试函数：以 `test_*` 开头（如 `test_load_config_success`）
- 超长文件拆分：单文件 >500 行需拆分（如 `test_loader_read.py` / `test_loader_errors.py`）

### 测试文件示例

```python
# tests/unit/config/test_config.py
import pytest
from src.config.config import ConfigLoader

@pytest.mark.unit
class TestConfigLoader:
    def test_load_config_success(self, tmp_path):
        """测试正常加载配置"""
        # Arrange
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": "value"}')
        
        # Act
        loader = ConfigLoader(str(config_file))
        config = loader.load()
        
        # Assert
        assert config["key"] == "value"
    
    def test_load_config_file_not_found(self):
        """测试文件不存在的情况"""
        # Arrange
        loader = ConfigLoader("/nonexistent/file.json")
        
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            loader.load()
```

## 5. 标记与分层

### pytest marks 注册

在 `pytest.ini` 中注册所有 marks：

```ini
[pytest]
markers =
    unit: unit tests (1:1 file mapping with src)
    integration: integration tests
    performance: performance and benchmarks
    slow: slow tests (>1s)
    fast: fast tests (<1s)
    asyncio: async tests
```

### 标记使用规范

- **单元测试**：`@pytest.mark.unit`
- **集成测试**：`@pytest.mark.integration`
- **性能测试**：`@pytest.mark.performance`
- **快测/慢测**：`@pytest.mark.fast` / `@pytest.mark.slow`
- **异步测试**：`@pytest.mark.asyncio`

### 运行特定标记的测试

```bash
# 只运行单元测试
pytest -m unit

# 只运行快测
pytest -m fast

# 排除慢测
pytest -m "not slow"

# 组合标记
pytest -m "unit and fast"
```

------

## 4. 交付物（Deliverables）

1. **结构化测试树**（完成 1:1 单测映射与目录规范化）。
2. **覆盖率报告**：`term` + `htmlcov/` + `coverage.xml`。
3. **性能画像**：`pytest --durations=20` 输出与优化说明。
4. **静态质量检查结果**：`flake8 / black / isort / mypy / bandit`。
5. **文档**：`tests/README.md`（分层设计、标记规范、运行方式、常见问题）。
6. **CI 工作流**（GitHub Actions / 其他等价 CI YAML）。
7. **PR 草案**：变更摘要、前后指标对比、风险与回滚说明。

------

## 6. 验收标准

### 覆盖率门槛（必须全部满足）

| 类型 | 门槛 | 验证命令 |
|------|------|----------|
| 单元测试 | ≥85% | `pytest --cov=src --cov-report=term -m unit` |
| 集成测试 | ≥80% | `pytest --cov=src --cov-report=term -m integration` |
| 关键模块 | ≥90% | 自定义模块列表 |
| 整体覆盖率 | ≥85% | `pytest --cov=src --cov-fail-under=85` |

### 性能要求（本地与 CI 同级硬件）

| 类型 | 要求 | 验证命令 |
|------|------|----------|
| 快测 | <1s | `pytest -m fast --durations=0` |
| 慢测 | <5s | `pytest -m slow --durations=0` |
| 集成测试 | <10s | `pytest -m integration --durations=0` |
| 整套测试 | <5min | `pytest --durations=0` |

### 质量检查（必须全部通过）

```bash
# 代码风格
flake8 tests/ --max-line-length=100 --extend-ignore=E203,W503

# 代码格式化
black --check tests/ || black tests/
isort --check-only tests/ || isort tests/

# 类型检查
mypy tests/ --ignore-missing-imports

# 安全扫描
bandit -r tests/ -ll
```

**质量原则**：
- `flake8` 无 error（warning 可接受）
- `black` / `isort` 格式化通过
- `mypy` 通过（必要处使用精确 `# type: ignore[CODE]` 并注释原因）
- **禁真实外网/外部副作用**：网络/时间/IO 一律 mock 或沙箱
- **测试可重复、相互独立**：临时资源自动清理（`tmp_path` 等）

------

## 3. 执行流程

> **重要**：严格按照以下 6 个步骤顺序执行，每步完成后进行验证

### Step 1：盘点与基线报告

**目标**：全面了解当前测试状态

**执行步骤**：

1. 扫描 `tests/` 目录结构，生成目录树
2. 统计测试文件数量、测试用例数量
3. 运行基线覆盖率：`pytest --cov=src --cov-report=term --cov-report=xml`
4. 识别 Top 20 慢测：`pytest --durations=20`
5. 分析未覆盖热点（函数/分支）
6. 检查不稳定用例（多次运行结果不一致）

**交付物**：
- `reports/test_audit.md`：包含现状分析、未覆盖热点、Top 慢测列表
- `coverage.xml`：基线覆盖率数据

**验证命令**：
```bash
# 生成审计报告
pytest --cov=src --cov-report=term --cov-report=xml --durations=20 -q > reports/test_audit.md

# 检查覆盖率
pytest --cov=src --cov-report=term
```

### Step 2：结构治理（零生产代码改动）

**目标**：规范化测试目录结构和命名

**执行步骤**：

1. 落实 **1:1 单测映射**：将测试文件重命名/迁移到 `tests/unit/<pkg>/test_*.py`
2. 合并重复用例：识别并合并功能重复的测试
3. 拆解超长文件：单文件 >500 行需拆分（如 `test_loader_read.py` / `test_loader_errors.py`）
4. 抽取通用资源：将共享 fixtures 移到 `tests/fixtures/`，工具函数移到 `tests/utils/`

**交付物**：
- 变更清单（移动/重命名表）
- 合规声明（确认未改动生产代码）

**验证命令**：
```bash
# 检查文件命名规范
find tests -name "*.py" -not -path "*/__pycache__/*" -not -name "conftest.py" \
  | awk -F/ '{print $NF}' | grep -vE '^test_.*\.py$' && echo "[WARN] 非规范文件名"

# 检查类/方法命名
grep -R "^class " tests | grep -v "class Test" && echo "[WARN] 非规范测试类名"
grep -R "def test_" tests | grep -vE "def test_[a-z0-9_]+:" && echo "[WARN] 非规范测试方法名"
```

### Step 3：覆盖率提升（优先关键路径）

**目标**：达到覆盖率门槛要求

**执行步骤**：

1. 针对未覆盖模块补齐测试：正常路径、边界条件、异常分支
2. 关键模块重点覆盖：解析/抽取/回退/缓存/核心算法等
3. 使用属性测试：对复杂输入使用 `hypothesis` 扩大测试域
4. 覆盖特殊场景：超时/重试、资源释放、并发安全

**交付物**：
- 新增/补充测试列表
- 前后覆盖率对比表

**验证命令**：
```bash
# 检查覆盖率是否达标
pytest --cov=src --cov-fail-under=85 --cov-report=term

# 生成详细覆盖率报告
pytest --cov=src --cov-report=html --cov-report=xml
```

### Step 4：性能优化（加速而不改业务）

**目标**：提升测试执行速度

**执行步骤**：

1. 启用并行执行：`pytest -n auto`
2. 标记快/慢测：为测试添加 `@pytest.mark.fast` 或 `@pytest.mark.slow`
3. 精简测试数据：使用最小必要数据集
4. Mock 真实 IO/网络：将真实文件操作、网络请求替换为 mock
5. 冻结时间：使用 `freezegun` 固定时间相关测试

**交付物**：
- `--durations=20` 前后对比
- 性能优化说明文档

**验证命令**：
```bash
# 查看慢测
pytest --durations=20 -q

# 只运行快测
pytest -m fast -q

# 并行执行
pytest -n auto -q
```

### Step 5：文档与 CI

**目标**：完善文档和 CI 集成

**执行步骤**：

1. 更新 `tests/README.md`：包含目录结构、标记规范、运行方式、常见问题
2. 提供 CI YAML：`.github/workflows/ci.yml` 或等价配置
3. 配置覆盖率门槛：在 CI 中强制 `--cov-fail-under=85`
4. 集成静态检查：flake8、black、isort、mypy、bandit

**交付物**：
- `tests/README.md`：完整的测试文档
- `.github/workflows/ci.yml`：CI 配置文件

**验证命令**：
```bash
# 检查文档是否存在
test -f tests/README.md && echo "✓ README.md exists"

# 检查 CI 配置
test -f .github/workflows/ci.yml && echo "✓ CI config exists"
```

### Step 6：PR 草案

**目标**：生成完整的变更摘要

**交付物**：
- PR 描述：包含变更摘要、指标对比表、风险与回滚步骤、后续建议

## 7. 配置与模板

### pytest.ini 配置

```ini
[pytest]
addopts = -q -ra -lv --strict-markers --maxfail=1 --disable-warnings
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    unit: unit tests (1:1 file mapping with src)
    integration: integration tests
    performance: performance and benchmarks
    slow: slow tests (>1s)
    fast: fast tests (<1s)
    asyncio: async tests

timeout = 10
log_cli = true
log_cli_level = INFO

# 覆盖率配置
[tool:pytest]
addopts = --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml
```

### conftest.py 示例

```python
# conftest.py
import pytest
from faker import Faker

@pytest.fixture(scope="session")
def faker():
    """提供 Faker 实例用于生成测试数据"""
    return Faker()

@pytest.fixture
def sample_user_data(faker):
    """生成示例用户数据"""
    return {
        "name": faker.name(),
        "email": faker.email(),
        "age": faker.random_int(min=18, max=80)
    }

@pytest.fixture(autouse=True)
def reset_state():
    """每个测试前自动重置状态"""
    # 测试前
    yield
    # 测试后清理
```

### tests/README.md 模板

```markdown
# 测试文档

## 目录结构

- `tests/unit/`：单元测试（1:1 文件映射）
- `tests/integration/`：集成测试
- `tests/performance/`：性能测试
- `tests/fixtures/`：测试数据
- `tests/utils/`：测试工具

## 1:1 映射规则

`src/<pkg>/<path>.py` ↔ `tests/unit/<pkg>/test_<path>.py`

## 运行测试

\`\`\`bash
# 运行所有测试
pytest

# 运行单元测试
pytest -m unit

# 运行快测
pytest -m fast

# 并行执行
pytest -n auto

# 生成覆盖率报告
pytest --cov=src --cov-report=html
\`\`\`

## Mock 原则

所有外部依赖必须 mock：
- 网络请求：使用 `responses` 或 `pytest-mock`
- 时间：使用 `freezegun`
- 文件系统：使用 `tmp_path` fixture
- 环境变量：使用 `monkeypatch` fixture

## 常见问题

见"常见问题与解决方案"章节。
```

### CI 配置（GitHub Actions）

```yaml
name: tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -U pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-xdist pytest-timeout \
            hypothesis responses freezegun pytest-asyncio pytest-mock \
            bandit flake8 black isort mypy faker
      
      - name: Lint & Static Checks
        run: |
          flake8 tests/ --max-line-length=100 --extend-ignore=E203,W503
          black --check tests/
          isort --check-only tests/
          mypy tests/ --ignore-missing-imports
          bandit -r tests/ -ll
      
      - name: Run Tests (Parallel)
        run: |
          pytest -q -n auto \
            --cov=src \
            --cov-report=term \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=85 \
            --durations=20
      
      - name: Upload Coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-${{ matrix.python-version }}
          path: |
            coverage.xml
            htmlcov/
```


## 8. 自动化命令

### 覆盖率相关

```bash
# 生成覆盖率报告（终端 + HTML + XML）
pytest -q --cov=src --cov-report=term --cov-report=html --cov-report=xml

# 检查覆盖率是否达标
pytest -q --cov=src --cov-fail-under=85

# 只检查单元测试覆盖率
pytest -q --cov=src -m unit --cov-report=term
```

### 性能相关

```bash
# 查看 Top 20 慢测
pytest -q --durations=20

# 只运行快测
pytest -q -m fast

# 只运行慢测
pytest -q -m slow

# 并行执行（自动检测 CPU 核心数）
pytest -q -n auto

# 并行执行（指定进程数）
pytest -q -n 4
```

### 质量检查

```bash
# 代码风格检查
flake8 tests/ --max-line-length=100 --extend-ignore=E203,W503

# 代码格式化（检查）
black --check tests/

# 代码格式化（执行）
black tests/

# 导入排序（检查）
isort --check-only tests/

# 导入排序（执行）
isort tests/

# 类型检查
mypy tests/ --ignore-missing-imports

# 安全扫描
bandit -r tests/ -ll
```

### 结构/命名自检

```bash
# 检查文件命名规范
find tests -name "*.py" -not -path "*/__pycache__/*" -not -name "conftest.py" \
  | awk -F/ '{print $NF}' | grep -vE '^test_.*\.py$' && echo "[WARN] 非规范文件名"

# 检查测试类命名
grep -R "^class " tests | grep -v "class Test" && echo "[WARN] 非规范测试类名"

# 检查测试方法命名
grep -R "def test_" tests | grep -vE "def test_[a-z0-9_]+:" && echo "[WARN] 非规范测试方法名"

# 检查 1:1 映射完整性（需要根据实际项目调整）
python3 << 'EOF'
import os
from pathlib import Path

src_files = set()
test_files = set()

# 收集 src 文件
for root, dirs, files in os.walk("src"):
    for f in files:
        if f.endswith(".py") and not f.startswith("__"):
            rel_path = os.path.relpath(os.path.join(root, f), "src")
            src_files.add(rel_path.replace(".py", ""))

# 收集测试文件
for root, dirs, files in os.walk("tests/unit"):
    for f in files:
        if f.startswith("test_") and f.endswith(".py"):
            rel_path = os.path.relpath(os.path.join(root, f), "tests/unit")
            test_name = rel_path.replace("test_", "").replace(".py", "")
            test_files.add(test_name)

# 检查映射
missing_tests = src_files - test_files
if missing_tests:
    print(f"[WARN] 缺少测试文件: {sorted(missing_tests)}")
else:
    print("[OK] 1:1 映射完整")
EOF
```

------

## 9. 常见问题与解决方案

### 问题 1：测试不稳定（Flaky Tests）

**症状**：同一测试有时通过，有时失败

**解决方案**：
1. 检查是否有随机性：使用固定 seed（`pytest --random-order-seed=42`）
2. 检查时间依赖：使用 `freezegun` 冻结时间
3. 检查并发问题：确保测试隔离，避免共享状态
4. 检查外部依赖：确保所有外部调用都已 mock

**示例**：
```python
import pytest
from freezegun import freeze_time

@pytest.mark.unit
def test_time_dependent_function():
    with freeze_time("2024-01-01 12:00:00"):
        result = time_dependent_function()
        assert result == expected_value
```

### 问题 2：测试执行缓慢

**症状**：测试套件执行时间过长

**解决方案**：
1. 启用并行执行：`pytest -n auto`
2. 标记快/慢测：将慢测标记为 `@pytest.mark.slow`
3. Mock 真实 IO：将文件操作、网络请求替换为 mock
4. 精简测试数据：使用最小必要数据集
5. 使用 fixture 缓存：对昂贵的 setup 使用 `scope="session"`

**示例**：
```python
import pytest
from unittest.mock import patch, mock_open

@pytest.mark.unit
@pytest.mark.fast
def test_fast_unit_test():
    # 快速单元测试
    pass

@pytest.mark.integration
@pytest.mark.slow
def test_slow_integration():
    # 慢速集成测试
    pass

@pytest.mark.unit
def test_file_operation():
    with patch("builtins.open", mock_open(read_data="test data")):
        result = read_file("dummy_path")
        assert result == "test data"
```

### 问题 3：覆盖率不达标

**症状**：覆盖率低于门槛要求

**解决方案**：
1. 识别未覆盖代码：运行 `pytest --cov=src --cov-report=term-missing`
2. 优先覆盖关键路径：核心业务逻辑、错误处理、边界条件
3. 使用属性测试：对复杂输入使用 `hypothesis` 扩大测试域
4. 检查分支覆盖：确保 if/else、异常处理都有覆盖

**示例**：
```python
from hypothesis import given, strategies as st

@pytest.mark.unit
@given(st.integers(min_value=1, max_value=100))
def test_with_property_based_testing(value):
    result = process_value(value)
    assert result > 0
```

### 问题 4：Mock 不生效

**症状**：Mock 设置后仍然调用真实函数

**解决方案**：
1. 检查 patch 路径：确保 patch 的是被测试代码中导入的路径
2. 使用 `pytest-mock`：更简洁的 mock 管理
3. 检查 import 方式：确保 mock 在正确的位置

**示例**：
```python
# 错误方式
from src.module import function
with patch("src.module.function"):  # 可能不生效
    function()

# 正确方式
from src.module import function
with patch("src.module.function"):  # 在导入后 patch
    function()

# 或使用 pytest-mock
def test_with_pytest_mock(mocker):
    mock_func = mocker.patch("src.module.function")
    mock_func.return_value = "mocked"
    result = function()
    assert result == "mocked"
```

### 问题 5：测试数据污染

**症状**：测试之间相互影响

**解决方案**：
1. 使用 `tmp_path` fixture：每个测试使用独立临时目录
2. 使用 `monkeypatch`：临时修改环境变量、全局状态
3. 使用 `autouse=True` fixture：自动清理状态
4. 避免使用 `scope="module"` 或 `scope="session"` 的共享状态

**示例**：
```python
@pytest.fixture(autouse=True)
def clean_state():
    """每个测试前自动清理状态"""
    # 测试前清理
    yield
    # 测试后清理

@pytest.mark.unit
def test_with_isolated_data(tmp_path, monkeypatch):
    # 使用独立临时目录
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    # 临时修改环境变量
    monkeypatch.setenv("TEST_VAR", "test_value")
    
    # 测试代码
    result = process_file(str(test_file))
    assert result == expected
```

### 问题 6：异步测试问题

**症状**：异步测试执行异常

**解决方案**：
1. 使用 `pytest-asyncio`：正确标记异步测试
2. 使用 `asyncio.run()` 或 `pytest.mark.asyncio`
3. Mock 异步函数：使用 `AsyncMock`

**示例**：
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
@pytest.mark.unit
async def test_async_function():
    result = await async_function()
    assert result == expected

@pytest.mark.asyncio
@pytest.mark.unit
async def test_async_mock(mocker):
    mock_func = mocker.patch("src.module.async_func", new_callable=AsyncMock)
    mock_func.return_value = "mocked"
    result = await async_func()
    assert result == "mocked"
```

### 问题 7：发现生产代码 Bug

**症状**：编写测试时发现生产代码存在 bug

**处理方式**（详见"工作范围"章节）：
1. **记录 Bug**：在 `reports/test_audit.md` 中详细记录
2. **编写测试用例**：使用 `@pytest.mark.xfail` 标记，避免阻塞测试套件
3. **评估优先级**：严重 bug 立即上报，一般 bug 记录在报告中
4. **不修复**：测试治理过程中不修复生产代码 bug
5. **后续处理**：在 PR 中列出所有发现的问题，建议创建独立 issue

**示例**：
```python
@pytest.mark.unit
@pytest.mark.xfail(reason="生产代码 bug：config.py 第 42 行未处理空值，待修复")
def test_load_config_with_empty_value():
    """此测试暴露了生产代码的一个 bug"""
    config_data = {"key": ""}
    result = load_config(config_data)
    # 当前会抛出 KeyError，但应该返回默认值
    assert result.get("key") == "default"
```


## 10. 交付物检查清单

### Step 1 交付物
- [ ] `reports/test_audit.md`：包含现状分析、未覆盖热点、Top 慢测列表
- [ ] `coverage.xml`：基线覆盖率数据

### Step 2 交付物
- [ ] 变更清单（移动/重命名表）
- [ ] 合规声明（确认未改动生产代码）
- [ ] 所有测试文件符合命名规范

### Step 3 交付物
- [ ] 新增/补充测试列表
- [ ] 前后覆盖率对比表
- [ ] 覆盖率达标证明（≥85%）

### Step 4 交付物
- [ ] `--durations=20` 前后对比
- [ ] 性能优化说明文档
- [ ] 所有测试标记正确（fast/slow）

### Step 5 交付物
- [ ] `tests/README.md`：完整的测试文档
- [ ] `.github/workflows/ci.yml`：CI 配置文件
- [ ] `pytest.ini`：pytest 配置
- [ ] `conftest.py`：共享 fixtures

### Step 6 交付物
- [ ] PR 描述：包含变更摘要、指标对比表、风险与回滚步骤


## 11. PR 模板

```markdown
# 测试治理 PR

## 变更摘要

- **结构治理**：{要点}
- **单元测试 1:1 映射完成度**：{N%}
- **覆盖率**：{前 -> 后}
- **性能**：总时长 {前 -> 后}，Top 慢测改善 {列表}
- **文档与 CI**：新增/更新 {文件列表}

## 验收指标对比

| 指标 | 治理前 | 治理后 | 门槛 | 状态 |
|------|--------|--------|------|------|
| 单元覆盖率 | x% | y% | ≥85% | ✅/❌ |
| 集成覆盖率 | x% | y% | ≥80% | ✅/❌ |
| 关键模块覆盖率 | x% | y% | ≥90% | ✅/❌ |
| 整体覆盖率 | x% | y% | ≥85% | ✅/❌ |
| 套件时长 | A | B | <5min | ✅/❌ |
| 快测时长 | A | B | <1s | ✅/❌ |
| 慢测时长 | A | B | <5s | ✅/❌ |

## 发现的生产代码问题

> **注意**：以下问题在测试治理过程中发现，已编写测试用例但未修复生产代码。

{列出所有发现的问题，包括：
- 问题描述
- 位置和严重程度
- 测试用例位置
- 建议的后续处理}

## 风险与回滚

### 风险
{说明潜在风险和影响}

### 回滚步骤
1. `git revert <commit>`
2. 移除新增 `tests/**` 文件（如需要）
3. 还原 `pytest.ini` 改动（如需要）

## 合规说明

- **未对任何生产代码做改动**；所有变更仅在测试与配置侧
- 如遇到可测性障碍，已采用 mock/契约/黑盒替代方案
- 残余风险：{列出任何已知的测试覆盖不足或限制}

## 后续建议

{列出后续可以改进的方向}
```

------

## 12. 执行口令（直接粘贴运行）

```
请严格按本提示执行"Python 测试治理闭环"，重点落实 **1:1 单元测试映射**（src/<pkg>/<path>.py ↔ tests/unit/<pkg>/test_<path>.py），并逐步产出：

1. `reports/test_audit.md`（含现状、未覆盖热点、Top 慢测）
2. 完成目录/命名治理与 1:1 映射（零生产代码改动），提交变更清单
3. 补齐关键路径与薄弱点测试，覆盖率达标（≥85%）
4. 完成并行化与性能优化，提交前后 `--durations=20` 对比
5. 补全 `tests/README.md` 与 CI YAML
6. 生成包含指标对比与回滚方案的 PR 草案

**重要提醒**：
- 遇到因"禁止改动生产代码"导致的可测性障碍，务必采用 mock/契约/黑盒替代，并在报告中记录受阻点与残余风险
- 如果发现生产代码 bug，记录在报告中并使用 `@pytest.mark.xfail` 标记测试用例，但不要修复生产代码
- 每完成一步，立即验证并记录结果，确保符合验收标准
```

------

## 使用方式

在 Claude Code 中通过命令面板（Cmd+Shift+P）或直接引用此命令，AI 将帮助你：

1. **执行测试治理**：按照上述 6 个步骤系统化地治理测试代码
2. **生成报告**：自动生成测试审计报告、覆盖率报告、性能分析等
3. **配置 CI**：自动生成或更新 CI 配置文件
4. **生成 PR 草案**：包含完整的变更摘要和指标对比

## 注意事项

- **严禁修改生产代码**：所有变更仅限于测试目录和测试相关配置
- **遵循 1:1 映射规则**：确保单元测试与源代码文件一一对应
- **覆盖率门槛**：必须达到规定的覆盖率标准才能通过验收
- **性能要求**：测试执行时间必须在规定范围内
- **质量检查**：所有静态检查工具必须通过

## 相关命令

- `test-fix.md`：修复失败的测试
- `code-review.md`：代码审查
- `commit.md`：提交变更


**最后更新**：2025-11-30 16:10:35  
**维护者**：QualityOps Team  
**版本**：**3.0.0（优化版 · 严禁生产代码改动 · 支持 1:1 单测映射 · 增强实用性）**
