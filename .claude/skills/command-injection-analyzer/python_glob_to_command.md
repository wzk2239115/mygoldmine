# Python | Glob结果用于命令构造漏洞

## 基本信息
- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 15-20分钟

## 🚀 30秒快速清单
- [ ] 是否使用了glob.glob()或pathlib.Path.glob()？
- [ ] glob结果是否直接用于命令构造或字符串拼接？
- [ ] 是否验证了glob返回的文件路径？
- [ ] 是否使用了参数列表而非字符串拼接？

## Details

### 漏洞成因
Python的glob.glob()或pathlib.Path.glob()返回与模式匹配的文件路径列表。如果这些路径直接用于命令构造（特别是使用字符串拼接或shell=True的方式），文件名中的特殊字符（空格、特殊符号、shell元字符等）可能导致命令注入。此问题常见于日志处理、文件批处理、日志轮转等场景。

### 代码示例

```python
# 漏洞1：glob结果直接拼接到命令字符串
import glob
import subprocess

def process_logs():
    # 获取所有日志文件
    log_files = glob.glob('/var/log/app/*.log')

    # 问题：直接拼接到命令字符串
    for log_file in log_files:
        # 如果文件名包含空格或特殊字符，命令会被分割
        cmd = f"gzip -9 {log_file}"  # 问题：未转义
        subprocess.run(cmd, shell=True)

# 攻击场景：
# 创建文件 /var/log/app/access.log; rm -rf /*
# 当subprocess执行时，;后面的命令也会执行
```

```python
# 漏洞2：glob与shell模式结合
import subprocess

def backup_databases():
    pattern = "/data/db/*.db"

    # 虽然glob.glob只返回真实存在的文件
    # 但如果文件名可被攻击者控制，仍有风险
    import glob
    db_files = glob.glob(pattern)

    for db_file in db_files:
        # 问题：在shell模式下，特殊字符未转义
        cmd = f"mysqldump -u root {db_file} > /backups/{db_file}.sql"
        result = subprocess.run(cmd, shell=True)
```

```python
# 漏洞3：使用pathlib.glob且未转义
from pathlib import Path
import subprocess

def find_and_compress(directory):
    path = Path(directory)

    # 获取所有.txt文件
    for txt_file in path.glob('*.txt'):
        # 问题：将Path对象转为字符串后未转义
        filename = str(txt_file)

        # 如果文件名为 "file with spaces.txt"
        # 此命令会分割为 ["gzip", "-9", "file", "with", "spaces.txt"]
        cmd = f"gzip -9 {filename}"
        subprocess.run(cmd, shell=True)
```

```python
# 漏洞4：glob与subprocess.run字符串模式
import glob
import subprocess

def cleanup_old_files(days=30):
    import time
    import os

    current_time = time.time()
    cutoff = current_time - (days * 24 * 60 * 60)

    for file_path in glob.glob('/tmp/*'):
        # 问题1：glob结果直接用于字符串拼接
        # 问题2：未考虑文件名中的特殊字符
        if os.path.getmtime(file_path) < cutoff:
            # 问题：拼接包含glob结果的命令
            subprocess.run(f"rm -f {file_path}", shell=True)
```

```python
# 漏洞5：glob与find命令结合
import glob
import subprocess

def process_batch():
    # 获取所有要处理的目录
    directories = glob.glob('/data/*/results')

    for directory in directories:
        # 问题：在find命令中使用glob结果
        # 如果directory包含引号或其他特殊字符
        cmd = ['find', directory, '-type', 'f', '-exec', 'process_tool', '{}', ';']

        # 虽然使用了列表模式，但如果-exec后有glob结果
        # 仍然可能有问题
        subprocess.run(cmd)
```

### 快速定位核心操作
- **关键词扫描**：`glob.glob`, `Path.glob`, `subprocess.run`, `shell=True`, `f"..."` 字符串拼接
- **glob使用**：`for ... in glob.glob(...)` 或 `for ... in path.glob(...)`
- **命令构造**：`f"{glob_result}"`, `"{}" .format(glob_result)`, 字符串拼接
- **缺少转义**：无 `shlex.quote()` 或 `pipes.quote()`
- **shell=True**：使用shell模式执行字符串命令

### 快速定位保护机制
- **参数列表**：使用subprocess的列表模式，不使用shell=True
- **转义**：使用 `shlex.quote()` 转义glob结果
- **避免shell**：将glob结果作为参数列表传递
- **验证文件名**：检查glob结果的文件名是否合法

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **glob结果用于字符串拼接**：`f"{glob_result}"` 或 `"cmd " + glob_result`
2. **使用shell=True且拼接glob结果**：`subprocess.run(f"..{glob_result}..", shell=True)`
3. **未转义特殊字符**：缺少 `shlex.quote()`
4. **不安全的find命令**：`-exec` 中的参数来自glob

**典型漏洞特征**：
- `for file in glob.glob(...): subprocess.run(f"cmd {file}", shell=True)`
- `subprocess.run(f"gzip -9 {glob_result}")` 带 `shell=True`
- 缺少 `shlex.quote()`
- `"...".format(glob.glob(...))` 或 f-string拼接

### 误报排除
- ✗ 使用参数列表模式：`subprocess.run([cmd, arg1, arg2, glob_result])`
- ✗ 使用 `shlex.quote(glob_result)` 转义
- ✗ 不使用 `shell=True`
- ✗ 验证文件名不包含特殊字符

### 代码异味（需进一步验证）
- △ 使用glob但有某种转义（可能不完整）
- △ 有shell=True但同时有转义

---

## Low Risk

给予低风险评级的场景需满足以下条件之一：
1. 使用参数列表模式，不使用shell=True
2. 使用 `shlex.quote()` 转义所有glob结果
3. 验证glob结果的文件名仅包含安全字符

---

## 安全实现

```python
# secure_glob_usage.py
import glob
import shlex
import subprocess
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

class SecureGlobProcessor:
    """安全处理glob结果的工具类"""

    @staticmethod
    def process_files_safely(pattern: str, operation: str) -> List[str]:
        """
        安全处理glob匹配的文件

        Args:
            pattern: glob模式
            operation: 要执行的操作

        Returns:
            处理结果列表
        """

        # 1. 获取glob结果
        files = glob.glob(pattern)

        if not files:
            logger.info(f"No files found matching pattern: {pattern}")
            return []

        results = []

        # 2. 对每个文件进行操作
        for file_path in files:
            # 验证文件
            if not SecureGlobProcessor._validate_file(file_path):
                logger.warning(f"Skipping invalid file: {file_path}")
                continue

            try:
                # 根据operation执行不同操作
                if operation == 'gzip':
                    SecureGlobProcessor._compress_file(file_path)
                    results.append(f"Compressed: {file_path}")

                elif operation == 'remove':
                    SecureGlobProcessor._remove_file(file_path)
                    results.append(f"Removed: {file_path}")

                elif operation == 'backup':
                    SecureGlobProcessor._backup_file(file_path)
                    results.append(f"Backed up: {file_path}")

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                results.append(f"Error: {file_path}")

        return results

    @staticmethod
    def _validate_file(file_path: str) -> bool:
        """验证文件路径安全性"""

        # 1. 检查空路径
        if not file_path:
            return False

        # 2. 检查目录遍历
        if '..' in file_path:
            return False

        # 3. 检查文件名长度
        if len(file_path) > 4096:
            return False

        # 4. 验证文件存在
        import os
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return False

        # 5. 检查文件权限（可选）
        if not os.access(file_path, os.R_OK):
            return False

        return True

    @staticmethod
    def _compress_file(file_path: str) -> None:
        """
        安全地压缩文件

        问题：使用参数列表而非字符串拼接
        """

        # 错误方式：
        # subprocess.run(f"gzip -9 {file_path}", shell=True)

        # 正确方式：使用参数列表
        cmd = ['/usr/bin/gzip', '-9', file_path]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Gzip failed: {result.stderr}")

        logger.info(f"Successfully compressed: {file_path}")

    @staticmethod
    def _remove_file(file_path: str) -> None:
        """
        安全地删除文件

        使用os.remove而非rm命令
        """

        import os

        # 不使用 subprocess.run("rm -f ...", shell=True)
        # 而是使用Python内置函数
        os.remove(file_path)
        logger.info(f"Successfully removed: {file_path}")

    @staticmethod
    def _backup_file(file_path: str) -> None:
        """安全地备份文件"""

        import shutil
        import datetime

        # 生成备份文件名
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{file_path}.backup_{timestamp}"

        # 使用shutil.copy而非cp命令
        shutil.copy2(file_path, backup_path)
        logger.info(f"Successfully backed up: {file_path} -> {backup_path}")

    @staticmethod
    def cleanup_old_files(directory: str, days: int = 30) -> List[str]:
        """
        安全地清理旧文件

        Args:
            directory: 目录路径
            days: 旧文件定义（天数）

        Returns:
            清理结果列表
        """

        import os
        import time

        # 验证目录
        if not os.path.isdir(directory):
            raise ValueError(f"Invalid directory: {directory}")

        results = []
        current_time = time.time()
        cutoff = current_time - (days * 24 * 60 * 60)

        # 使用os.listdir而非glob
        try:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)

                # 验证是普通文件
                if not os.path.isfile(file_path):
                    continue

                # 检查修改时间
                if os.path.getmtime(file_path) < cutoff:
                    try:
                        os.remove(file_path)
                        results.append(f"Removed: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to remove {file_path}: {e}")
                        results.append(f"Failed: {file_path}")

        except Exception as e:
            logger.error(f"Error listing directory: {e}")

        return results

    @staticmethod
    def process_with_find_command(directory: str, pattern: str) -> str:
        """
        使用find命令但安全地处理结果

        Args:
            directory: 搜索目录
            pattern: 文件名模式

        Returns:
            命令输出
        """

        # 验证输入
        if not SecureGlobProcessor._validate_directory(directory):
            raise ValueError("Invalid directory")

        if not SecureGlobProcessor._validate_pattern(pattern):
            raise ValueError("Invalid pattern")

        # 使用参数列表，不使用shell拼接
        cmd = [
            '/usr/bin/find',
            directory,
            '-maxdepth', '3',
            '-name', pattern,
            '-type', 'f'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            logger.error(f"Find command failed: {result.stderr}")
            return ""

        return result.stdout

    @staticmethod
    def _validate_directory(directory: str) -> bool:
        """验证目录安全性"""
        import os

        if not directory or '..' in directory:
            return False

        if not os.path.isdir(directory):
            return False

        return True

    @staticmethod
    def _validate_pattern(pattern: str) -> bool:
        """验证搜索模式"""
        if not pattern or len(pattern) > 100:
            return False

        # 不允许shell特殊字符
        dangerous = ['/', '`', '$', '{', '}', ';', '|', '&']
        return not any(char in pattern for char in dangerous)


# 使用示例
if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.INFO)

    # 示例1：压缩日志文件
    results = SecureGlobProcessor.process_files_safely(
        '/var/log/app/*.log',
        'gzip'
    )
    for result in results:
        print(result)

    # 示例2：清理旧临时文件
    results = SecureGlobProcessor.cleanup_old_files('/tmp', days=7)
    for result in results:
        print(result)

    # 示例3：使用find命令
    output = SecureGlobProcessor.process_with_find_command('/data', '*.txt')
    print(output)
```

## 修复优先级

1. **立即修复（当天）**：停止使用shell=True和字符串拼接处理glob结果
2. **快速修复（3天内）**：改为使用参数列表模式，或使用shlex.quote()转义
3. **短期改善（1周内）**：用Python内置函数代替shell命令（如os.remove代替rm）
4. **长期改进（1个月）**：审计所有subprocess调用，完整的安全测试
