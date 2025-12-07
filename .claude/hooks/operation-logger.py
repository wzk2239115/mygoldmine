#!/usr/bin/env python3
# .claude/hooks/operation-logger.py
# 操作记录钩子
#
# 功能：记录所有工具操作，包括工具类型、输入、输出和时间戳

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 配置：使用当前工作目录下的 .workspace/logs
LOG_DIR = Path.cwd() / ".workspace" / "logs"
LOG_FILE = LOG_DIR / "operations.log"
JSON_LOG_FILE = LOG_DIR / "operations.jsonl"
# 简单日志轮转策略
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
MAX_BACKUPS = 2  # 保留 operations.log.1、operations.log.2

# 确保日志目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
def setup_logging():
    """配置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z',
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
        
        # 记录到JSONL文件（结构化日志）
        try:
            with open(JSON_LOG_FILE, 'a', encoding='utf-8') as f:
                json.dump(operation_record, f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            logger.error(f"写入JSONL日志失败: {e}")
        
        # 记录到文本日志（人类可读）
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
            
            logger.info(log_message)
        except Exception as e:
            logger.error(f"写入文本日志失败: {e}")
            
    except Exception as e:
        logger.error(f"记录操作时出错: {e}", exc_info=True)

def main():
    """主函数"""
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

