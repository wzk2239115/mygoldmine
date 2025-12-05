#!/usr/bin/env python3
# .claude/plugins/code-audit/hooks/code-auditor-stop.py
# Python版本：产物完整性检查钩子
#
# 功能：检查任务文件状态和产物完整性
# 在Agent退出时运行，如果任务未完成或产物缺失，阻止退出并提示

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# 配置
WORKSPACE_DIR = Path(".workspace/tasks")
LOG_FILE = Path("/tmp/code-auditor-stop.log")
ARTIFACT_CHECK_ENABLED = True  # 是否启用产物检查

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

class TaskChecker:
    """任务检查器"""

    def __init__(self):
        self.has_issues = False
        self.coordinator_issues: List[str] = []
        self.scanner_issues: List[str] = []
        self.artifact_issues: List[str] = []
        self.task_file_count = 0

    def log_message(self, message: str):
        """记录日志"""
        logger.info(message)

    def get_expected_artifacts(self, agent_name: str) -> List[str]:
        """根据 agent 名称获取约定的产物路径列表"""
        results_dir = Path(".workspace/results")
        artifacts = []

        if agent_name == "project-analyzer":
            artifacts.append(str(results_dir / "project-analysis.json"))
        elif agent_name == "threat-modeler":
            artifacts.append(str(results_dir / "threat-model.json"))
            artifacts.append(str(results_dir / "threat-task-list.json"))
        elif agent_name == "report-generator":
            artifacts.append(str(results_dir / "audit-report.md"))
            artifacts.append(str(results_dir / "audit-report.json"))
        elif agent_name.endswith("-scanner"):
            # 扫描器：{scanner-name}-results.json
            scanner_base = agent_name.replace("-scanner", "")
            artifacts.append(str(results_dir / f"{scanner_base}-results.json"))
        else:
            # 未知 agent，不检查产物
            self.log_message(f"未知 agent 类型: {agent_name}，跳过产物检查")
            return []

        return artifacts

    def check_workspace_directory(self) -> bool:
        """检查工作区目录是否存在"""
        self.log_message(f"检查工作区目录: {WORKSPACE_DIR}")
        if not WORKSPACE_DIR.exists() or not WORKSPACE_DIR.is_dir():
            self.log_message("工作区目录不存在，无审计进行中，允许退出")
            print("No audit in progress, allow exit")
            sys.exit(0)  # 直接退出，允许结束
        return True

    def check_artifact_completeness(self, task_file: Path, identifier: str, artifact_path: str) -> bool:
        """检查产物完整性
        
        Args:
            task_file: 任务文件路径
            identifier: 标识符（agent_name 或 task_id）
            artifact_path: 产物文件路径
        """
        if not artifact_path or artifact_path == "null":
            self.log_message(f"{identifier} 未指定产物路径，跳过检查")
            return True

        artifact = Path(artifact_path)

        if not artifact.exists():
            self.log_message(f"❌ {identifier} 产物缺失: {artifact_path}")
            print(f"  ✗ 产物缺失: {artifact_path}")
            return False

        # 简单的完整性检查：文件非空
        if artifact.stat().st_size == 0:
            self.log_message(f"⚠️  {identifier} 产物为空: {artifact_path}")
            print(f"  ⚠️  产物为空: {artifact_path}")
            return False

        self.log_message(f"✅ {identifier} 产物完整: {artifact_path}")
        return True

    def process_scanner_task(self, task_file: Path, data: Dict[str, Any]) -> bool:
        """处理扫描器类型任务"""
        agent_name = data.get('agent', 'unknown')

        if 'scan_targets' not in data:
            return False

        scan_targets = data.get('scan_targets', [])
        incomplete_targets = []

        for target in scan_targets:
            if isinstance(target, dict):
                status = target.get('status', '')
                if status not in ['completed', 'failed']:
                    incomplete_targets.append(target)

        if incomplete_targets:
            incomplete_count = len(incomplete_targets)
            self.log_message(f"扫描器 '{agent_name}' 发现未完成目标: {incomplete_count} 个")
            self.has_issues = True

            total_targets = len(scan_targets)
            completed_targets = sum(1 for t in scan_targets if isinstance(t, dict) and t.get('status') == 'completed')

            self.log_message(f"扫描器 '{agent_name}' 进度: {completed_targets}/{total_targets} 已完成")

            # 获取未完成目标详情
            incomplete_details = []
            for target in incomplete_targets:
                target_id = target.get('path') or target.get('id', 'unknown')
                status = target.get('status', 'unknown')
                incomplete_details.append(f"  - {target_id} ({status})")

            self.scanner_issues.append(f"【{agent_name} (扫描器)】")
            self.scanner_issues.append(f"进度: {completed_targets}/{total_targets} 已完成")
            self.scanner_issues.append(f"未完成目标 ({incomplete_count} 个):")
            if incomplete_details:
                self.scanner_issues.extend(incomplete_details)
            self.scanner_issues.append("")

        return True

    def process_general_task(self, task_file: Path, data: Dict[str, Any]) -> bool:
        """处理通用智能体任务"""
        agent_name = data.get('agent', 'unknown')

        if 'tasks' not in data:
            return False

        tasks = data.get('tasks', [])
        incomplete_tasks = []

        for task in tasks:
            if isinstance(task, dict):
                status = task.get('status', '')
                if status not in ['completed', 'failed']:
                    incomplete_tasks.append(task)

        if incomplete_tasks:
            incomplete_count = len(incomplete_tasks)
            self.log_message(f"智能体 '{agent_name}' 发现未完成任务: {incomplete_count} 个")
            self.has_issues = True

            # 确定智能体类型用于显示
            if agent_name == "code-auditor":
                agent_type = "调度智能体"
            elif agent_name == "threat-modeler":
                agent_type = "威胁建模智能体"
            elif agent_name == "project-analyzer":
                agent_type = "项目分析智能体"
            else:
                agent_type = "智能体"

            self.log_message(f"智能体类型: {agent_name} ({agent_type})")

            # 获取未完成任务详情
            task_details = []
            for task in incomplete_tasks:
                description = task.get('description') or task.get('type') or task.get('id', 'unknown')
                status = task.get('status', 'unknown')
                task_details.append(f"  - {description} ({status})")

            self.coordinator_issues.append(f"【{agent_name} ({agent_type})】")
            self.coordinator_issues.append("未完成任务:")
            self.coordinator_issues.extend(task_details)
            self.coordinator_issues.append("")

        return True

    def check_artifact_integrity(self, task_file: Path, data: Dict[str, Any]):
        """检查产物完整性"""
        if not ARTIFACT_CHECK_ENABLED:
            return

        self.log_message("开始产物完整性检查")

        agent_name = data.get('agent', 'unknown')
        
        # 对于扫描器类型，需要检查所有 scan_targets 是否都完成
        if 'scan_targets' in data:
            scan_targets = data.get('scan_targets', [])
            incomplete_targets = [t for t in scan_targets 
                                 if isinstance(t, dict) and t.get('status') not in ['completed', 'failed']]
            if incomplete_targets:
                self.log_message(f"扫描器 '{agent_name}' 仍有未完成目标，跳过产物检查")
                return
        
        # 对于通用智能体类型，需要检查所有 tasks 是否都完成
        if 'tasks' in data:
            tasks = data.get('tasks', [])
            incomplete_tasks = [t for t in tasks 
                              if isinstance(t, dict) and t.get('status') not in ['completed', 'failed']]
            if incomplete_tasks:
                self.log_message(f"智能体 '{agent_name}' 仍有未完成任务，跳过产物检查")
                return

        expected_artifacts = self.get_expected_artifacts(agent_name)

        if not expected_artifacts:
            self.log_message(f"Agent '{agent_name}' 无约定产物，跳过产物检查")
            return

        # 检查所有约定的产物
        for artifact_path in expected_artifacts:
            self.log_message(f"检查 Agent '{agent_name}' 的约定产物: {artifact_path}")

            if not self.check_artifact_completeness(task_file, agent_name, artifact_path):
                self.has_issues = True

                self.artifact_issues.append(f"【产物缺失】Agent: {agent_name}")
                self.artifact_issues.append(f"  预期产物: {artifact_path}")
                self.artifact_issues.append("")

    def process_task_file(self, task_file: Path):
        """处理单个任务文件"""
        self.task_file_count += 1
        self.log_message(f"检查任务文件 [{self.task_file_count}]: {task_file.name}")

        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.log_message(f"❌ 无法解析任务文件 {task_file}: {e}")
            return

        agent_name = data.get('agent', 'unknown')

        # 检查是否为扫描器类型
        if 'scan_targets' in data:
            self.process_scanner_task(task_file, data)
        else:
            self.process_general_task(task_file, data)

        # 检查产物完整性
        self.check_artifact_integrity(task_file, data)

    def check_all_tasks(self):
        """检查所有任务文件"""
        self.log_message("脚本启动: code-auditor-stop.py (Python版本)")

        if not self.check_workspace_directory():
            return False

        # 查找所有任务文件
        task_files = list(WORKSPACE_DIR.glob("*-tasks.json"))
        if not task_files:
            self.log_message("未找到任务文件，允许退出")
            print("No task files found, allow exit")
            return True

        for task_file in task_files:
            self.process_task_file(task_file)

        self.log_message(f"任务文件检查完成，共发现 {self.task_file_count} 个任务文件")

        if not self.has_issues:
            self.log_message("所有任务均已完成，产物完整，允许退出")
        else:
            self.log_message("发现未完成任务或缺失产物，将阻止退出")

        return not self.has_issues

    def display_results(self):
        """显示检查结果"""
        if not self.has_issues:
            print("\n" + "━" * 55)
            print("✅  所有审计任务已完成，产物完整")
            print("━" * 55)
            return

        print("\n" + "━" * 55)
        print("⚠️  审计任务未完成，无法退出")
        print("━" * 55 + "\n")

        # 显示协调器问题
        if self.coordinator_issues:
            print("\n".join(self.coordinator_issues))

        # 显示扫描器问题
        if self.scanner_issues:
            print("\n".join(self.scanner_issues))

        # 显示产物问题
        if self.artifact_issues:
            print("━" * 55)
            print("📁 产物完整性检查结果")
            print("━" * 55)
            print("\n".join(self.artifact_issues))

            print("需要完成的产物：")
            for issue in self.artifact_issues:
                if issue.startswith("  预期产物:"):
                    artifact_path = issue.split(":", 1)[1].strip()
                    print(f"  - {artifact_path}")
            print("\n请先生成上述产物文件后再退出。")

        print("\n" + "━" * 55)
        print("请继续完成上述未完成任务后再退出。")
        print("━" * 55 + "\n")


def main():
    """主函数"""
    checker = TaskChecker()

    try:
        if checker.check_all_tasks():
            checker.display_results()
            sys.exit(0)  # 允许退出
        else:
            checker.display_results()
            sys.exit(2)  # 退出码2表示让输出转交给Agent处理
    except Exception as e:
        logger.exception(f"检查过程中发生错误: {e}")
        sys.exit(1)  # 无法处理的异常，记录异常


if __name__ == "__main__":
    main()