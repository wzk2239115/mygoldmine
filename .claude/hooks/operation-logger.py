#!/usr/bin/env python3
# .claude/hooks/operation-logger.py
# 操作记录钩子
#
# 功能：记录所有工具操作，包括工具类型、输入、输出和时间戳
# 日志存储默认使用 base64 编码，可通过环境变量关闭：
#   OPERATION_LOGGER_BASE64_DISABLED=1  关闭 base64 编码，使用明文存储

import os
import sys
import json
import logging
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 环境变量控制：OPERATION_LOGGER_BASE64_DISABLED=1 关闭 base64 编码，默认开启 base64 编码
BASE64_DISABLED = os.environ.get('OPERATION_LOGGER_BASE64_DISABLED', '').lower() in ('1', 'true', 'yes')

# 配置：使用当前工作目录下的 .workspace/logs
LOG_DIR = Path.cwd() / ".workspace" / "logs"
LOG_FILE = LOG_DIR / "operations.log"
JSON_LOG_FILE = LOG_DIR / "operations.jsonl"
# 简单日志轮转策略
MAX_LOG_SIZE = 30 * 1024 * 1024  # 30MB
MAX_BACKUPS = 2  # 保留 operations.log.1、operations.log.2

# 确保日志目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
def setup_logging():
    """配置日志记录

    注意：format 仅包含 %(message)s，时间戳在 message 中一起编码
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        filename=LOG_FILE,
        filemode='a'
    )
    return logging.getLogger(__name__)

logger = setup_logging()


def rotate_file(path: Path):
    """简单轮转：超限时顺延 .1、.2，保留最近 MAX_BACKUPS 份"""
    try:
        if not path.exists() or path.stat().st_size <= MAX_LOG_SIZE:
            return
        # 删除最旧
        oldest = path.with_suffix(path.suffix + f".{MAX_BACKUPS}")
        if oldest.exists():
            oldest.unlink(missing_ok=True)
        # 顺延重命名
        for idx in range(MAX_BACKUPS - 1, 0, -1):
            src = path.with_suffix(path.suffix + f".{idx}")
            dst = path.with_suffix(path.suffix + f".{idx + 1}")
            if src.exists():
                src.replace(dst)
        # 当前文件转存为 .1
        path.replace(path.with_suffix(path.suffix + ".1"))
    except Exception as e:
        logger.error(f"日志轮转失败: {e}")

def get_timestamp() -> str:
    """获取当前时间戳（ISO 8601格式）"""
    return datetime.now().isoformat()

def encode_for_storage(data: str) -> str:
    """根据配置决定是否进行 base64 编码

    Args:
        data: 要处理的字符串

    Returns:
        base64 编码后的字符串（默认），或原始字符串（当 BASE64_DISABLED=1 时）
    """
    if BASE64_DISABLED:
        return data
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')


def sanitize_data(data: Any, max_length: int = 4096) -> Any:
    """清理数据，避免记录过大的内容

    Args:
        data: 要清理的数据
        max_length: 字符串最大长度

    Returns:
        清理后的数据
    """
    if isinstance(data, str):
        if len(data) > max_length:
            return data[:max_length] + f"... (truncated, total {len(data)} chars)"
        return data
    elif isinstance(data, dict):
        return {k: sanitize_data(v, max_length) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item, max_length) for item in data]
    else:
        return data


def extract_response_text(tool_response: Any, max_length: int = 4096) -> str:
    """从 tool_response 中提取 content 的 text 字段"""
    if not isinstance(tool_response, dict):
        return ""
    contents = []
    for item in tool_response.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            txt = item.get("text", "")
            if txt:
                contents.append(txt)
    if not contents:
        return ""
    joined = "\n---\n".join(contents)
    if len(joined) > max_length:
        return joined[:max_length] + f"... (truncated, total {len(joined)} chars)"
    return joined

def log_operation(data: Dict[str, Any]) -> None:
    """记录工具操作

    Args:
        data: 从 stdin 读取的 JSON 数据
    """
    try:
        # 轮转检查，避免日志无限增长
        rotate_file(LOG_FILE)
        rotate_file(JSON_LOG_FILE)

        # 提取工具信息
        tool_name = data.get('tool_name', 'unknown')
        tool_input = data.get('tool_input', {})
        tool_response = data.get('tool_response', {})
        session_id = data.get('session_id', 'unknown')
        response_text = extract_response_text(tool_response) if tool_name == "Task" else ""

        # 构建操作记录
        operation_record = {
            'timestamp': get_timestamp(),
            'session_id': session_id,
            'tool_name': tool_name,
            'tool_input': sanitize_data(tool_input),
            'tool_response': sanitize_data(tool_response),
            'response_text': sanitize_data(response_text) if tool_name == "Task" else "",
            'success': tool_response.get('error') is None if isinstance(tool_response, dict) else True
        }

        # 记录到JSONL文件（结构化日志，base64编码）
        try:
            json_str = json.dumps(operation_record, ensure_ascii=False)
            encoded_record = encode_for_storage(json_str)
            with open(JSON_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(encoded_record)
                f.write('\n')
        except Exception as e:
            logger.error(f"写入JSONL日志失败: {e}")
        
        # 记录到文本日志（通过 logger，数据经过 encode 编码）
        try:
            # 提取关键信息用于文本日志
            file_path = tool_input.get('file_path', '')
            command = tool_input.get('command', '')

            if file_path:
                log_message = f"[{tool_name}] {file_path}"
            elif command:
                # 截断过长的命令，保留前4096字节
                cmd_preview = (
                    command
                    if len(command) <= 4096
                    else command[:4096] + f"... (truncated, total {len(command)} chars)"
                )
                # 对于Bash命令，提取stdout和stderr
                if tool_name == "Bash":
                    stdout = tool_response.get('stdout', '')
                    stderr = tool_response.get('stderr', '')
                    # success来自data本身，不是tool_response
                    success = data.get('success', False)

                    # 截断过长的输出
                    stdout_preview = (
                        stdout
                        if len(stdout) <= 4096
                        else stdout[:4096] + f"... (truncated, total {len(stdout)} chars)"
                    )
                    stderr_preview = (
                        stderr
                        if len(stderr) <= 4096
                        else stderr[:4096] + f"... (truncated, total {len(stderr)} chars)"
                    )

                    log_message = f"[{tool_name}] {cmd_preview}\nstdout={stdout_preview}\nstderr={stderr_preview}\nsuccess={success}"
                else:
                    log_message = f"[{tool_name}] {cmd_preview}"
            else:
                input_json = json.dumps(tool_input, ensure_ascii=False, indent=4)
                response_json = json.dumps(tool_response, ensure_ascii=False, indent=4)
                input_preview = (
                    input_json
                    if len(input_json) <= 4096
                    else input_json[:4096] + f"... (truncated, total {len(input_json)} chars)"
                )
                response_preview = (
                    response_json
                    if len(response_json) <= 4096
                    else response_json[:4096] + f"... (truncated, total {len(response_json)} chars)"
                )
                if tool_name == "Task" and response_text:
                    log_message = f"[{tool_name}]\ninput={input_preview}\nresponse={response_preview}\nresponse_text={response_text}"
                else:
                    log_message = f"[{tool_name}]\ninput={input_preview}\nresponse={response_preview}"

            # 时间戳和日志消息一起编码后通过 logger 写入
            timestamp = get_timestamp()
            full_log_entry = f"[{timestamp}] {log_message}"
            encoded_message = encode_for_storage(full_log_entry)
            logger.info(encoded_message)
        except Exception as e:
            logger.error(f"写入文本日志失败: {e}")
            
    except Exception as e:
        logger.error(f"记录操作时出错: {e}", exc_info=True)

def decode_base64(data: str) -> str:
    """解码 base64 字符串

    Args:
        data: base64 编码的字符串

    Returns:
        解码后的原始字符串
    """
    try:
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')
    except Exception:
        return data  # 解码失败则返回原始数据


def decode_log_file(file_path: Path, output_path: Optional[Path] = None) -> None:
    """解码日志文件

    Args:
        file_path: 要解码的日志文件路径
        output_path: 输出文件路径，为 None 时输出到 stdout
    """
    if not file_path.exists():
        print(f"错误：文件不存在 {file_path}", file=sys.stderr)
        sys.exit(1)

    decoded_lines = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line:
                decoded_lines.append(decode_base64(line))

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(decoded_lines))
            f.write('\n')
        print(f"已解码到: {output_path}")
    else:
        for line in decoded_lines:
            print(line)


def decode_jsonl_file(file_path: Path, output_path: Optional[Path] = None, pretty: bool = False) -> None:
    """解码 JSONL 日志文件

    Args:
        file_path: 要解码的 JSONL 文件路径
        output_path: 输出文件路径，为 None 时输出到 stdout
        pretty: 是否格式化 JSON 输出
    """
    if not file_path.exists():
        print(f"错误：文件不存在 {file_path}", file=sys.stderr)
        sys.exit(1)

    decoded_lines = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line:
                decoded_json = decode_base64(line)
                if pretty:
                    try:
                        obj = json.loads(decoded_json)
                        decoded_lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
                    except json.JSONDecodeError:
                        decoded_lines.append(decoded_json)
                else:
                    decoded_lines.append(decoded_json)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(decoded_lines))
            f.write('\n')
        print(f"已解码到: {output_path}")
    else:
        for line in decoded_lines:
            print(line)


def print_usage():
    """打印使用说明"""
    print("""
operation-logger.py - 操作日志记录与解码工具

用法：
  作为钩子运行（从 stdin 读取 JSON）：
    echo '{"tool_name": "Read", ...}' | python operation-logger.py

  解码文本日志：
    python operation-logger.py decode [日志文件路径] [-o 输出文件]

  解码 JSONL 日志：
    python operation-logger.py decode-json [JSONL文件路径] [-o 输出文件] [--pretty]

  查看最近日志（解码后）：
    python operation-logger.py tail [行数]

  查看最近 JSONL 日志（解码后）：
    python operation-logger.py tail-json [行数] [--pretty]

选项：
  -o, --output    指定输出文件路径（默认输出到 stdout）
  --pretty        格式化 JSON 输出

环境变量：
  OPERATION_LOGGER_BASE64_DISABLED=1  关闭 base64 编码，使用明文存储

示例：
  python operation-logger.py decode .workspace/logs/operations.log
  python operation-logger.py decode-json .workspace/logs/operations.jsonl --pretty
  python operation-logger.py tail 20
  python operation-logger.py tail-json 10 --pretty
""")


def tail_log(n: int = 20) -> None:
    """查看最近 n 行日志（解码后）"""
    if not LOG_FILE.exists():
        print(f"错误：日志文件不存在 {LOG_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    recent_lines = lines[-n:] if len(lines) >= n else lines
    for line in recent_lines:
        line = line.rstrip('\n')
        if line:
            print(decode_base64(line))


def tail_jsonl(n: int = 20, pretty: bool = False) -> None:
    """查看最近 n 行 JSONL 日志（解码后）"""
    if not JSON_LOG_FILE.exists():
        print(f"错误：JSONL 日志文件不存在 {JSON_LOG_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(JSON_LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    recent_lines = lines[-n:] if len(lines) >= n else lines
    for line in recent_lines:
        line = line.rstrip('\n')
        if line:
            decoded_json = decode_base64(line)
            if pretty:
                try:
                    obj = json.loads(decoded_json)
                    print(json.dumps(obj, ensure_ascii=False, indent=2))
                except json.JSONDecodeError:
                    print(decoded_json)
            else:
                print(decoded_json)


def main():
    """主函数"""
    # 解析命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command in ('-h', '--help', 'help'):
            print_usage()
            sys.exit(0)

        elif command == 'decode':
            # 解码文本日志
            file_path = Path(sys.argv[2]) if len(sys.argv) > 2 else LOG_FILE
            output_path = None
            if '-o' in sys.argv or '--output' in sys.argv:
                try:
                    idx = sys.argv.index('-o') if '-o' in sys.argv else sys.argv.index('--output')
                    output_path = Path(sys.argv[idx + 1])
                except (IndexError, ValueError):
                    print("错误：-o/--output 需要指定输出文件路径", file=sys.stderr)
                    sys.exit(1)
            decode_log_file(file_path, output_path)
            sys.exit(0)

        elif command == 'decode-json':
            # 解码 JSONL 日志
            file_path = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else JSON_LOG_FILE
            output_path = None
            pretty = '--pretty' in sys.argv
            if '-o' in sys.argv or '--output' in sys.argv:
                try:
                    idx = sys.argv.index('-o') if '-o' in sys.argv else sys.argv.index('--output')
                    output_path = Path(sys.argv[idx + 1])
                except (IndexError, ValueError):
                    print("错误：-o/--output 需要指定输出文件路径", file=sys.stderr)
                    sys.exit(1)
            decode_jsonl_file(file_path, output_path, pretty)
            sys.exit(0)

        elif command == 'tail':
            # 查看最近日志
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            tail_log(n)
            sys.exit(0)

        elif command == 'tail-json':
            # 查看最近 JSONL 日志
            n = 20
            pretty = '--pretty' in sys.argv
            for i, arg in enumerate(sys.argv[2:], start=2):
                if not arg.startswith('-'):
                    try:
                        n = int(arg)
                    except ValueError:
                        pass
            tail_jsonl(n, pretty)
            sys.exit(0)

        else:
            print(f"未知命令: {command}", file=sys.stderr)
            print_usage()
            sys.exit(1)

    # 默认行为：作为钩子运行，从 stdin 读取 JSON
    try:
        # 从 stdin 读取 JSON 数据
        input_data = json.load(sys.stdin)

        # 记录操作
        log_operation(input_data)

        # 正常退出（不影响工具执行）
        sys.exit(0)

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误: {e}")
        sys.exit(0)  # JSON 解析错误时不影响正常流程
    except Exception as e:
        logger.error(f"执行错误: {e}", exc_info=True)
        sys.exit(0)  # 异常时不影响正常流程


if __name__ == '__main__':
    main()

