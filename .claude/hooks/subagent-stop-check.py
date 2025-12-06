#!/usr/bin/env python3
# .claude/hooks/subagent-stop-check.py
# SubAgentStop 事件检查钩子
#
# 功能：检查所有子智能体的任务完成情况
# 当子代理任务完成时运行，检查所有未执行的subagent任务
# 明确区分是哪个扫描任务没有完成

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# 配置
WORKSPACE_TASKS_DIR = Path(".workspace/tasks")
LOG_FILE = Path("/tmp/subagent-stop-check.log")

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

class SubAgentTaskChecker:
    """子智能体任务检查器"""
    
    def __init__(self):
        self.incomplete_tasks: List[Dict[str, Any]] = []
        self.task_files: List[Path] = []
        
    def log_message(self, message: str):
        """记录日志"""
        logger.info(message)
        
    def find_all_task_files(self) -> List[Path]:
        """查找所有 tasks.json 文件"""
        task_files = []
        
        if not WORKSPACE_TASKS_DIR.exists():
            self.log_message(f"工作区目录不存在: {WORKSPACE_TASKS_DIR}")
            return task_files
            
        # 查找所有 *-tasks.json 文件
        for task_file in WORKSPACE_TASKS_DIR.glob("*-tasks.json"):
            if task_file.is_file():
                task_files.append(task_file)
                self.log_message(f"找到任务文件: {task_file}")
                
        return task_files
    
    def load_task_file(self, task_file: Path) -> Optional[Dict[str, Any]]:
        """加载任务文件"""
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            self.log_message(f"JSON 解析错误 {task_file}: {e}")
            return None
        except Exception as e:
            self.log_message(f"读取文件错误 {task_file}: {e}")
            return None
    
    def get_agent_display_name(self, agent_name: str) -> str:
        """获取智能体的显示名称"""
        agent_names = {
            "security-orchestrator": "安全协调智能体",
            "project-profiler": "项目画像智能体",
            "threat-modeler": "威胁建模智能体",
            "general-scanner": "通用扫描智能体",
            "report-generator": "报告生成智能体"
        }
        return agent_names.get(agent_name, agent_name)
    
    def check_task_file(self, task_file: Path) -> List[Dict[str, Any]]:
        """检查单个任务文件，返回未完成的任务列表"""
        incomplete = []
        
        data = self.load_task_file(task_file)
        if not data:
            return incomplete
            
        agent_name = data.get('agent', 'unknown')
        agent_task_id = data.get('agent_task_id', 'unknown')
        tasks = data.get('tasks', [])
        summary = data.get('summary', {})
        
        # 检查是否有未完成的任务（排除失败的任务）
        pending_count = summary.get('pending', 0)
        in_progress_count = summary.get('in_progress', 0)
        
        if pending_count == 0 and in_progress_count == 0:
            self.log_message(f"任务文件 {task_file.name} 所有任务已完成")
            return incomplete
        
        # 收集未完成的任务详情（排除失败的任务）
        for task in tasks:
            status = task.get('status', 'unknown')
            if status in ['pending', 'in_progress']:
                task_info = {
                    'task_file': str(task_file),
                    'task_file_name': task_file.name,
                    'agent': agent_name,
                    'agent_display_name': self.get_agent_display_name(agent_name),
                    'agent_task_id': agent_task_id,
                    'task_id': task.get('id', 'unknown'),
                    'task_type': task.get('type', 'unknown'),
                    'task_description': task.get('description', ''),
                    'task_status': status,
                    'task_optional': task.get('optional', False)
                }
                incomplete.append(task_info)
                self.log_message(f"发现未完成任务: {agent_name}/{agent_task_id}/{task.get('id')} ({status})")
        
        return incomplete
    
    def check_all_subagent_tasks(self) -> List[Dict[str, Any]]:
        """检查所有子智能体的任务"""
        self.log_message("开始检查所有子智能体任务")
        
        task_files = self.find_all_task_files()
        if not task_files:
            self.log_message("未找到任何任务文件")
            return []
        
        all_incomplete = []
        for task_file in task_files:
            incomplete = self.check_task_file(task_file)
            all_incomplete.extend(incomplete)
        
        self.log_message(f"总共发现 {len(all_incomplete)} 个未完成任务")
        return all_incomplete
    
    def report_incomplete_tasks(self, incomplete_tasks: List[Dict[str, Any]]):
        """报告未完成的任务（仅显示统计信息）"""
        if not incomplete_tasks:
            self.log_message("所有子智能体任务已完成")
            print("✓ 所有子智能体任务已完成")
            return
        
        # 先按 agent_name 分组，再按 agent_task_id 分组
        grouped_tasks: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for task in incomplete_tasks:
            agent_name = task.get('agent', 'unknown')
            agent_task_id = task.get('agent_task_id', 'unknown')
            if agent_name not in grouped_tasks:
                grouped_tasks[agent_name] = {}
            if agent_task_id not in grouped_tasks[agent_name]:
                grouped_tasks[agent_name][agent_task_id] = []
            grouped_tasks[agent_name][agent_task_id].append(task)
        
        # 输出报告
        print("\n" + "="*60)
        print("⚠️  发现未完成的子智能体任务")
        print("="*60 + "\n")
        
        total_count = len(incomplete_tasks)
        
        # 按 agent_name 分组显示统计信息
        for agent_name, agent_tasks_by_id in sorted(grouped_tasks.items()):
            agent_display = self.get_agent_display_name(agent_name)
            agent_incomplete_count = sum(len(tasks) for tasks in agent_tasks_by_id.values())
            
            print(f"【{agent_display} ({agent_name})】")
            print(f"未完成任务数: {agent_incomplete_count}")
            print("-" * 60)
            
            # 按 agent_task_id 分组显示统计信息
            for agent_task_id, tasks in sorted(agent_tasks_by_id.items()):
                # 统计各状态的任务数量（排除失败的任务）
                status_counts = {
                    'pending': 0,
                    'in_progress': 0
                }
                for task in tasks:
                    status = task.get('task_status', 'unknown')
                    if status in status_counts:
                        status_counts[status] += 1
                
                # 构建状态统计字符串
                status_parts = []
                if status_counts['pending'] > 0:
                    status_parts.append(f"待处理: {status_counts['pending']}")
                if status_counts['in_progress'] > 0:
                    status_parts.append(f"进行中: {status_counts['in_progress']}")
                
                status_summary = " | ".join(status_parts) if status_parts else "未知状态"
                
                print(f"  任务列表ID: {agent_task_id} - {len(tasks)} 个未完成任务 ({status_summary})")
            
            print()  # 每个 agent_name 组后添加空行
        
        print("="*60)
        print(f"\n提示: 总计发现 {total_count} 个未完成任务。请检查上述任务，确保所有子智能体任务都已完成")
        print("="*60 + "\n")
        
        # 记录到日志
        self.log_message(f"发现 {total_count} 个未完成任务，已输出报告")

def main():
    """主函数"""
    try:
        checker = SubAgentTaskChecker()
        
        # 检查所有子智能体任务
        incomplete_tasks = checker.check_all_subagent_tasks()
        
        # 报告未完成的任务
        checker.report_incomplete_tasks(incomplete_tasks)
        
        # 如果有未完成的任务，返回非零退出码（但不阻止退出）
        if incomplete_tasks:
            sys.exit(0)  # 不阻止退出，只报告
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"执行错误: {e}", exc_info=True)
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(0)  # 错误时不阻止退出

if __name__ == '__main__':
    main()

