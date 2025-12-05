#!/usr/bin/env python3
# .claude/hooks/pre-write.py
# Write 操作拦截钩子
#
# 功能：拦截对 .workspace/tasks/*tasks.json 文件的 Write 操作
# 只允许通过 init-task-json.sh、update-task.sh 和 add-task.sh 脚本修改

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any

# 配置
LOG_FILE = Path("/tmp/claude-pre-write.log")

# 日志配置
def setup_logging():
    """配置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ',
        filename=LOG_FILE,
        filemode='a'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def is_tasks_json_file(file_path: str) -> bool:
    """检查文件路径是否匹配 .workspace/tasks/*tasks.json 模式
    
    Args:
        file_path: 文件路径
        
    Returns:
        如果是 tasks.json 文件则返回 True
    """
    if not file_path:
        return False
    
    try:
        path_obj = Path(file_path)
        
        # 检查文件名是否以 tasks.json 结尾
        if not path_obj.name.endswith('tasks.json'):
            return False
        
        # 检查路径是否匹配 .workspace/tasks/*tasks.json
        # 支持相对路径和绝对路径
        try:
            # 尝试解析为绝对路径
            normalized_path = str(path_obj.resolve())
        except (OSError, RuntimeError):
            # 如果无法解析（文件不存在），使用原始路径
            normalized_path = str(path_obj)
        
        # 检查是否在 .workspace/tasks/ 目录下
        # 支持绝对路径和相对路径
        if '/.workspace/tasks/' in normalized_path or normalized_path.endswith('.workspace/tasks'):
            return True
        
        # 也支持相对路径（不以 / 开头）
        if str(path_obj).startswith('.workspace/tasks/'):
            return True
        
        return False
        
    except Exception:
        # 路径解析出错，返回 False
        return False

def check_write_operation(data: Dict[str, Any]) -> int:
    """检查 Write 操作是否允许
    
    Args:
        data: 从 stdin 读取的 JSON 数据
        
    Returns:
        0: 允许操作
        2: 禁止操作（需要阻止）
    """
    try:
        tool_input = data.get('tool_input', {})
        file_path = tool_input.get('file_path', '')
        
        if not file_path:
            # 没有文件路径，允许通过
            return 0
        
        # 检查是否是 tasks.json 文件
        if not is_tasks_json_file(file_path):
            # 不是 tasks.json 文件，允许通过
            return 0
        
        # 是 tasks.json 文件，禁止直接修改
        logger.warning(f"禁止直接修改 tasks.json 文件: {file_path}")
        print("❌ 错误: 禁止手动修改 tasks.json 文件", file=sys.stderr)
        print("", file=sys.stderr)
        print("该文件必须通过以下脚本进行管理：", file=sys.stderr)
        print("  - init-task-json: 初始化 tasks.json 文件", file=sys.stderr)
        print("  - update-task: 更新任务状态和内容", file=sys.stderr)
        print("  - add-task: 添加新任务", file=sys.stderr)
        print("", file=sys.stderr)
        print("请使用相应的脚本工具来操作该文件。", file=sys.stderr)
        
        return 2  # 返回 2 表示阻止操作
            
    except Exception as e:
        logger.error(f"检查 Write 操作时出错: {e}", exc_info=True)
        # 出错时允许通过，避免影响正常流程
        return 0

# 主执行逻辑
def main():
    """主函数"""
    try:
        # 从 stdin 读取 JSON 数据
        input_data = json.load(sys.stdin)
        
        # 检查 Write 操作
        exit_code = check_write_operation(input_data)
        sys.exit(exit_code)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误: {e}")
        sys.exit(0)  # JSON 解析错误时允许通过
    except Exception as e:
        logger.error(f"执行错误: {e}", exc_info=True)
        sys.exit(0)  # 异常时允许通过，避免影响正常流程

if __name__ == '__main__':
    main()

