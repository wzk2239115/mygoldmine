# Python | Subprocess环境变量污染漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] subprocess调用时是否传递了 `env=...` 参数？
- [ ] env参数中是否包含用户可控的环境变量？
- [ ] 是否清理了危险的环境变量（LD_PRELOAD等）？
- [ ] 是否验证了用户输入中的环境变量值？

## Details

### 漏洛成因
Python的subprocess.Popen、subprocess.run等函数允许通过 `env` 参数自定义进程环境变量。如果env字典由用户输入构造或包含用户可控的值，攻击者可以污染关键环境变量（如PATH、LD_PRELOAD等），导致任意代码执行。此问题常见于允许用户自定义环境配置的应用中。

### 代码示例

```python
# 漏洞1：用户输入直接用于env字典
import subprocess
import os

def run_command_with_env(command, custom_env):
    # custom_env来自用户输入，如 {"PATH": "/tmp:/usr/bin"}

    # 问题：直接使用用户提供的env
    env = os.environ.copy()
    env.update(custom_env)  # 合并用户输入

    result = subprocess.run(command, env=env, shell=True)
    return result
# 攻击场景：
# 1. custom_env = {"LD_PRELOAD": "/tmp/malicious.so"}
# 2. custom_env = {"PATH": "/tmp"}（在/tmp中放置恶意脚本）
```

```python
# 漏洞2：LD_PRELOAD环境变量注入
import subprocess
import os

def compile_source(source_file, custom_flags):
    # custom_flags可能来自用户输入

    env = os.environ.copy()

    # 问题：未清理LD_PRELOAD，用户可注入恶意库
    for flag in custom_flags:
        if flag.startswith("-L"):
            # 用户可能设置 "-L/tmp -Wl,-rpath,/tmp"
            pass

    cmd = ["gcc", "-o", "output"] + custom_flags + [source_file]

    # 用户可能同时设置LD_PRELOAD环境变量
    result = subprocess.run(cmd, env=env)
    return result
```

```python
# 漏洞3：PATH环境变量污染
import subprocess
import os

def execute_tool(tool_name, tool_args):
    env = os.environ.copy()

    # 问题：用户可能通过某个地方控制PATH
    # 虽然这里直接传递tool_name，但如果tool_name来自配置文件
    # 而配置文件可被修改，攻击者可以改变搜索路径

    result = subprocess.run(
        [tool_name] + tool_args,
        env=env  # 继承所有环境变量，包括被污染的PATH
    )
    return result
```

```python
# 漏洞4：从配置文件读取环境变量
import subprocess
import os
import json

def run_with_config(config_file, command):
    with open(config_file) as f:
        config = json.load(f)

    # 问题：如果config_file可被修改，攻击者可设置恶意环境变量
    env = os.environ.copy()
    if 'env_vars' in config:
        env.update(config['env_vars'])  # 合并配置中的env_vars

    result = subprocess.run(command, env=env, shell=True)
    return result
# 攻击场景：修改配置文件，添加 "env_vars": {"LD_PRELOAD": "/tmp/evil.so"}
```

```python
# 漏洞5：传递包含空值的env字典
import subprocess
import os

def run_with_partial_env(custom_env_subset):
    # 问题：直接传递用户的env字典
    # 如果不合并os.environ，仍然可能引入危险变量

    result = subprocess.run(
        ["python", "-c", "import os; print(os.environ)"],
        env=custom_env_subset  # 完全由用户控制的env
    )
    return result
```

### 快速定位核心操作
- **关键词扫描**：`subprocess.run`, `subprocess.Popen`, `subprocess.call`, `env=`, `os.environ`
- **env参数相关**：`env.update()`, `env[...]`, `custom_env`, `os.environ.copy()` 后跟 `update()`
- **用户输入来源**：配置文件、HTTP参数、命令行参数、环境变量
- **缺少验证**：无对env字典的验证或过滤

### 快速定位保护机制
- **环境隔离**：`env = {}` 或 `env = {"PATH": "...", "HOME": "..."}` 从空白开始
- **删除危险变量**：`env.pop("LD_PRELOAD")`, `env.pop("JAVA_TOOL_OPTIONS")` 等
- **白名单变量**：仅包含必要的环境变量
- **验证变量值**：检查PATH、HOME等关键变量的值是否合法

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **用户输入用于env**：`env.update(user_input)` 或 `env = user_input`
2. **未清理危险变量**：未删除 `LD_PRELOAD`, `LD_LIBRARY_PATH`, `JAVA_TOOL_OPTIONS` 等
3. **env来自配置文件**：配置文件可被修改，影响env变量
4. **继承所有环境变量**：`env = os.environ.copy()` 后无任何清理
5. **从不可信来源读取env**：从网络、文件等来源读取环境变量配置

**典型漏洞特征**：
- `env.update(custom_env)` 或 `env.update(config['env'])`
- `env = os.environ.copy()` 后直接传递给subprocess
- 缺少 `env.pop("LD_PRELOAD")` 等危险变量删除
- `env = json.load(config_file)` 或类似来自外部的env

### 误报排除
- ✗ env从空白开始：`env = {}`
- ✗ 仅添加必要变量：`env = {"PATH": "...", "HOME": "..."}`
- ✗ 明确删除危险变量：`env.pop("LD_PRELOAD")`
- ✗ 验证用户输入：仅允许白名单中的变量名和值
- ✗ 不使用env参数，依赖进程隔离

### 代码异味（需进一步验证）
- △ 有 `env.update()` 但未验证来源
- △ 有删除危险变量但不完整
- △ 从配置文件读取但配置文件权限足够严格

---

## Low Risk

给予低风险评级的场景需满足以下全部条件：
1. env从空白开始：`env = {}`
2. 仅添加必需的环境变量
3. 从不合并用户输入或外部来源
4. 明确设置安全的PATH、HOME等关键变量
5. 不使用 `shell=True`

---

## 安全实现

```python
# secure_subprocess.py
import subprocess
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class SecureProcessExecutor:
    """安全的子进程执行器"""

    # 危险的环境变量列表
    DANGEROUS_ENV_VARS = [
        'LD_PRELOAD',
        'LD_LIBRARY_PATH',
        'LD_AUDIT',
        'JAVA_TOOL_OPTIONS',
        'DYLD_INSERT_LIBRARIES',
        'PERLLIB',
        'PYTHONPATH',  # 可能导致恶意模块被加载
    ]

    # 允许的环境变量
    ALLOWED_ENV_VARS = {
        'PATH': '/usr/bin:/bin',
        'HOME': '/tmp/sandbox',
        'LANG': 'en_US.UTF-8',
        'TMPDIR': '/tmp',
    }

    @staticmethod
    def execute_safe(
        command: List[str],
        timeout: int = 30,
        custom_env: Optional[Dict[str, str]] = None
    ) -> subprocess.CompletedProcess:
        """
        安全执行命令

        Args:
            command: 命令列表（不使用shell）
            timeout: 超时时间（秒）
            custom_env: 自定义环境变量（可选，且必须经过验证）

        Returns:
            CompletedProcess对象
        """

        # 1. 验证命令列表
        if not command or len(command) == 0:
            raise ValueError("Command cannot be empty")

        # 2. 构造隔离的环境变量
        env = SecureProcessExecutor.ALLOWED_ENV_VARS.copy()

        # 3. 如果提供了自定义env，验证后添加
        if custom_env:
            env = SecureProcessExecutor._merge_safe_env(env, custom_env)

        # 4. 验证命令不是shell模式
        # subprocess不提供shell=False时不会执行shell

        logger.info(f"Executing command: {command[0]}")

        try:
            # 5. 执行命令（不使用shell）
            result = subprocess.run(
                command,
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True
            )

            logger.info(f"Command exited with code: {result.returncode}")
            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s")
            raise

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            raise

    @staticmethod
    def _merge_safe_env(base_env: Dict[str, str],
                       custom_env: Dict[str, str]) -> Dict[str, str]:
        """
        安全地合并自定义环境变量

        Args:
            base_env: 基础环境变量（已验证）
            custom_env: 用户提供的环境变量（需验证）

        Returns:
            合并后的环境变量
        """

        for key, value in custom_env.items():
            # 1. 检查是否是危险变量
            if key in SecureProcessExecutor.DANGEROUS_ENV_VARS:
                logger.warning(f"Rejecting dangerous env var: {key}")
                continue

            # 2. 验证变量名（仅字母、数字、下划线）
            if not SecureProcessExecutor._is_valid_env_name(key):
                logger.warning(f"Invalid env var name: {key}")
                continue

            # 3. 验证变量值
            if not SecureProcessExecutor._is_valid_env_value(key, value):
                logger.warning(f"Invalid env var value for {key}: {value}")
                continue

            # 4. 添加到env
            base_env[key] = value

        return base_env

    @staticmethod
    def _is_valid_env_name(name: str) -> bool:
        """验证环境变量名合法性"""
        return bool(__import__('re').match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))

    @staticmethod
    def _is_valid_env_value(name: str, value: str) -> bool:
        """验证环境变量值合法性"""

        # 1. 长度限制
        if len(value) > 1024:
            return False

        # 2. 特殊变量的额外验证
        if name == 'PATH':
            # PATH只能包含目录路径
            return all(part.startswith('/') for part in value.split(':'))

        if name == 'HOME':
            # HOME必须是有效的目录路径
            return value.startswith('/') and '..' not in value

        if name == 'TMPDIR':
            # TMPDIR必须是有效的目录路径
            return value.startswith('/') and '..' not in value

        # 3. 通用检查：不包含危险字符
        dangerous_chars = ['$', '`', '"', "'", '\\', ';', '|', '&', '<', '>']
        if any(char in value for char in dangerous_chars):
            return False

        return True

    @staticmethod
    def find_files(directory: str, pattern: str) -> str:
        """
        安全的文件查找

        Args:
            directory: 搜索目录（必须通过验证）
            pattern: 搜索模式（仅支持*和?）

        Returns:
            命令输出
        """

        # 验证目录和模式
        if not SecureProcessExecutor._validate_path(directory):
            raise ValueError("Invalid directory")

        if not SecureProcessExecutor._validate_pattern(pattern):
            raise ValueError("Invalid pattern")

        # 构造命令（不使用shell）
        command = [
            '/usr/bin/find',
            directory,
            '-maxdepth', '3',
            '-name', pattern
        ]

        result = SecureProcessExecutor.execute_safe(command, timeout=60)

        if result.returncode != 0:
            logger.error(f"Find command failed: {result.stderr}")
            return ""

        return result.stdout

    @staticmethod
    def _validate_path(path: str) -> bool:
        """验证路径安全性"""
        if not path or '..' in path or path.startswith('-'):
            return False
        return path.startswith('/') and len(path) <= 255

    @staticmethod
    def _validate_pattern(pattern: str) -> bool:
        """验证搜索模式"""
        if not pattern or len(pattern) > 100:
            return False
        # 只允许*和?
        if any(char in pattern for char in ['/', '[', ']', '{', '}', '$', '`']):
            return False
        return True


# 使用示例
if __name__ == '__main__':
    # 简单命令执行
    try:
        result = SecureProcessExecutor.execute_safe(['/bin/echo', 'Hello World'])
        print(result.stdout)
    except Exception as e:
        print(f"Error: {e}")

    # 文件查找
    try:
        output = SecureProcessExecutor.find_files('/tmp', '*.txt')
        print(output)
    except Exception as e:
        print(f"Error: {e}")
```

## 修复优先级

1. **立即修复（当天）**：停止直接合并用户输入到env字典
2. **快速修复（3天内）**：从空白env开始，仅添加必需变量
3. **短期改善（1周内）**：实施完整的环境变量验证和白名单
4. **长期改进（1个月）**：审计所有subprocess调用，添加日志和监控
