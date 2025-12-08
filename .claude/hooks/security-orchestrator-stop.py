#!/usr/bin/env python3
# .claude/hooks/security-orchestrator-stop.py
# 产物完整性检查钩子
#
# 功能：检查任务文件状态和产物完整性
# 在Agent退出时运行，如果任务未完成或产物缺失，阻止退出并提示
# 适配最新的 tasks.json 格式（agent, agent_task_id, tasks, summary）

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 配置
WORKSPACE_DIR = Path(".workspace/tasks")
WORKSPACE_ROOT = Path(".workspace")
EXIT_CHECK_COUNTER = WORKSPACE_ROOT / ".exit-check-counter.json"  # 退出检查计数器文件
EXIT_CHECK_THRESHOLD = 1  # 异常触发达到此次数时显示严重警告，超过则跳过检查
LOG_FILE = Path("/tmp/security-orchestrator-stop.log")
ARTIFACT_CHECK_ENABLED = True  # 是否启用产物检查

# 警告级别定义
WARNING_LEVEL_NORMAL = "normal"       # 普通警告（第1次触发，count=0）
WARNING_LEVEL_SEVERE = "severe"       # 严重警告（第2次触发，count=1）
WARNING_LEVEL_SKIP = "skip"           # 跳过检查（第3次及以上，count>1）

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
        self.agent_issues: List[str] = []
        self.artifact_issues: List[str] = []
        self.task_file_count = 0
        self.skipped_by_counter = False  # 标记是否因计数器超过阈值而跳过检查
        # 用于按 agent_task_id 分组存储 general-scanner 的数据
        self.general_scanner_groups: Dict[str, Dict[str, Any]] = {}
        # 用于存储执行时间异常的任务（小于10秒）
        self.abnormal_duration_tasks: List[Dict[str, Any]] = []
        # 当前警告级别
        self.warning_level: str = WARNING_LEVEL_NORMAL
        # 计数器值
        self.counter_value: int = 0

    def log_message(self, message: str):
        """记录日志"""
        logger.info(message)

    def get_expected_artifacts(self, agent_name: str) -> List[str]:
        """根据 agent 名称获取约定的产物路径列表
        
        Args:
            agent_name: Agent 名称
        """
        reports_dir = Path(".workspace/reports")
        artifacts = []

        if agent_name == "report-generator":
            artifacts.append(str(reports_dir / "audit-report.md"))
            artifacts.append(str(reports_dir / "audit-report.json"))

        return artifacts

    def check_workspace_directory(self) -> bool:
        """检查工作区目录是否存在"""
        self.log_message(f"检查工作区目录: {WORKSPACE_DIR}")
        if not WORKSPACE_DIR.exists() or not WORKSPACE_DIR.is_dir():
            self.log_message("工作区目录不存在，无审计进行中，允许退出")
            print("No audit in progress, allow exit")
            sys.exit(0)  # 直接退出，允许结束
        return True

    def check_artifact_completeness(self, identifier: str, artifact_path: str) -> bool:
        """检查产物完整性

        Args:
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

    def process_general_task(self, task_file: Path, data: Dict[str, Any]) -> bool:
        """处理通用智能体任务"""
        agent_name = data.get('agent', 'unknown')
        agent_task_id = data.get('agent_task_id', 'unknown')

        # 对于 general-scanner，如果 agent_task_id 无效（为空或等于 agent_name），从文件名提取
        if agent_name == "general-scanner":
            if not agent_task_id or agent_task_id == agent_name or agent_task_id == 'unknown':
                # 从文件名提取 agent_task_id，格式：{agent_task_id}-tasks.json
                file_stem = task_file.stem  # 获取不带扩展名的文件名
                if file_stem.endswith('-tasks'):
                    extracted_id = file_stem[:-6]  # 移除 '-tasks' 后缀
                    if extracted_id:
                        agent_task_id = extracted_id
                        self.log_message(f"从文件名提取 agent_task_id: {agent_task_id}")

        if 'tasks' not in data:
            return False

        tasks = data.get('tasks', [])
        pending_count = 0
        in_progress_count = 0
        abnormal_duration_count = 0
        DURATION_THRESHOLD = 10  # 10秒阈值

        for task in tasks:
            if isinstance(task, dict):
                status = task.get('status', '')
                task_id = task.get('id', 'unknown')
                duration = task.get('duration')

                if status == 'pending':
                    pending_count += 1
                elif status == 'in_progress':
                    in_progress_count += 1
                elif status in ['completed', 'failed']:
                    # 检查已完成或失败任务的执行时间
                    # duration 可能是 None/null，需要检查
                    if duration is not None and isinstance(duration, (int, float)):
                        if duration < DURATION_THRESHOLD:
                            abnormal_duration_count += 1
                            self.log_message(f"发现异常任务 [{task_id}]: 执行时间仅 {duration} 秒（< {DURATION_THRESHOLD}秒）")
                            self.abnormal_duration_tasks.append({
                                'agent_name': agent_name,
                                'agent_task_id': agent_task_id,
                                'task_id': task_id,
                                'status': status,
                                'duration': duration,
                                'description': task.get('description', '无描述')
                            })

        # 统计未完成任务
        if pending_count > 0 or in_progress_count > 0:
            total_incomplete = pending_count + in_progress_count
            self.log_message(f"智能体 '{agent_name}' 发现未完成任务: {total_incomplete} 个 (pending: {pending_count}, in_progress: {in_progress_count})")
            self.has_issues = True

            # 确定智能体类型用于显示
            if agent_name == "security-orchestrator":
                agent_type = "安全协调智能体"
            elif agent_name == "project-profiler":
                agent_type = "项目画像智能体"
            elif agent_name == "threat-modeler":
                agent_type = "威胁建模智能体"
            elif agent_name == "general-scanner":
                agent_type = "通用扫描智能体"
            elif agent_name == "report-generator":
                agent_type = "报告生成智能体"
            else:
                agent_type = "智能体"

            self.log_message(f"智能体类型: {agent_name} ({agent_type})")

            # 只记录统计信息，不显示任务详情
            status_parts = []
            if pending_count > 0:
                status_parts.append(f"待处理: {pending_count}")
            if in_progress_count > 0:
                status_parts.append(f"进行中: {in_progress_count}")

            status_summary = " | ".join(status_parts) if status_parts else "未知状态"

            # 对于 general-scanner，按 agent_task_id 分组存储
            if agent_name == "general-scanner":
                if agent_task_id not in self.general_scanner_groups:
                    self.general_scanner_groups[agent_task_id] = {
                        'agent_type': agent_type,
                        'pending_count': 0,
                        'in_progress_count': 0,
                        'total_incomplete': 0
                    }
                self.general_scanner_groups[agent_task_id]['pending_count'] += pending_count
                self.general_scanner_groups[agent_task_id]['in_progress_count'] += in_progress_count
                self.general_scanner_groups[agent_task_id]['total_incomplete'] += total_incomplete
            else:
                # 其他智能体直接添加到 agent_issues
                self.agent_issues.append(f"【{agent_name} ({agent_type})】")
                self.agent_issues.append(f"未完成任务: {total_incomplete} 个 ({status_summary})")
                self.agent_issues.append("")

        # 如果发现异常执行时间的任务，也标记为有问题
        if abnormal_duration_count > 0:
            self.has_issues = True
            self.log_message(f"智能体 '{agent_name}' 发现 {abnormal_duration_count} 个执行时间异常的任务（< {DURATION_THRESHOLD}秒）")

        return True

    def check_artifact_integrity(self, data: Dict[str, Any]):
        """检查产物完整性"""
        if not ARTIFACT_CHECK_ENABLED:
            return
        agent_name = data.get('agent', 'unknown')

        # 仅检查 report-generator，其余产物一律跳过
        if agent_name != "report-generator":
            self.log_message(f"产物检查仅针对 report-generator，跳过 {agent_name}")
            return

        self.log_message("开始产物完整性检查")

        # 检查所有 tasks 是否都完成
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

            if not self.check_artifact_completeness(agent_name, artifact_path):
                self.has_issues = True

                # 其他智能体的产物问题直接添加到 artifact_issues
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

        # 验证 tasks.json 格式（必须包含 agent, agent_task_id, tasks, summary）
        required_fields = ['agent', 'agent_task_id', 'tasks', 'summary']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            self.log_message(f"⚠️  任务文件格式不完整，缺少字段: {', '.join(missing_fields)}")
            # 继续处理，但记录警告

        # 处理通用智能体任务（新格式统一使用 tasks 数组）
        self.process_general_task(task_file, data)

        # 检查产物完整性
        self.check_artifact_integrity(data)

    def get_counter_value(self) -> int:
        """获取当前计数器值

        Returns:
            当前计数器值，文件不存在返回0
        """
        if not EXIT_CHECK_COUNTER.exists():
            return 0

        try:
            with open(EXIT_CHECK_COUNTER, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('count', 0)
        except Exception as e:
            self.log_message(f"读取计数器文件失败: {e}")
            return 0

    def check_counter(self) -> bool:
        """检查计数器并确定警告级别

        Returns:
            True: 计数器超过阈值，跳过检查
            False: 计数器未超过阈值，需要执行检查
        """
        count = self.get_counter_value()
        self.counter_value = count

        # 根据计数器值确定警告级别
        if count > EXIT_CHECK_THRESHOLD:
            self.warning_level = WARNING_LEVEL_SKIP
            self.skipped_by_counter = True
            self.log_message(f"退出检查计数器已超过阈值 ({count} > {EXIT_CHECK_THRESHOLD})，跳过任务检查，允许退出")
            print(f"Exit check counter exceeded threshold ({count} > {EXIT_CHECK_THRESHOLD}), allow exit")
            return True
        elif count == EXIT_CHECK_THRESHOLD:
            self.warning_level = WARNING_LEVEL_SEVERE
            self.log_message(f"退出检查计数器达到阈值 ({count} = {EXIT_CHECK_THRESHOLD})，将显示严重警告")
        else:
            self.warning_level = WARNING_LEVEL_NORMAL
            self.log_message(f"退出检查计数器: {count}，将显示普通警告")

        return False

    def increment_counter(self):
        """增加计数器"""
        try:
            # 确保 .workspace 目录存在
            WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

            # 读取当前计数器值
            count = self.get_counter_value()
            count += 1

            # 更新计数器文件
            counter_content = {
                "count": count,
                "created_at": datetime.now().isoformat() if count == 1 else (
                    json.loads(EXIT_CHECK_COUNTER.read_text(encoding='utf-8')).get('created_at', datetime.now().isoformat())
                ),
                "last_updated": datetime.now().isoformat()
            }

            with open(EXIT_CHECK_COUNTER, 'w', encoding='utf-8') as f:
                json.dump(counter_content, f, ensure_ascii=False, indent=2)

            self.log_message(f"退出检查计数器已更新: {count}")
        except Exception as e:
            self.log_message(f"更新计数器失败: {e}")

    def reset_counter(self):
        """重置计数器"""
        try:
            if EXIT_CHECK_COUNTER.exists():
                EXIT_CHECK_COUNTER.unlink()
                self.log_message("退出检查计数器已重置")
        except Exception as e:
            self.log_message(f"重置计数器失败: {e}")

    def check_all_tasks(self):
        """检查所有任务文件"""
        self.log_message("脚本启动: security-orchestrator-stop.py")

        # 检查计数器是否超过阈值
        if self.check_counter():
            return True  # 计数器超过阈值，跳过检查，允许退出

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
            # 重置计数器
            self.reset_counter()
        else:
            self.log_message("发现未完成任务或缺失产物，将阻止退出")
            # 发现未完成任务时，增加计数器
            self.increment_counter()

        return not self.has_issues

    def display_results(self):
        """显示检查结果"""
        # 如果是因为计数器超过阈值而跳过，不显示任何消息
        if self.skipped_by_counter:
            return

        if not self.has_issues:
            print("\n" + "━" * 55)
            print("✅  所有审计任务已完成，产物完整")
            print("━" * 55)
            return

        # 根据警告级别显示不同的标题和提示
        print("\n" + "━" * 55, file=sys.stderr)

        if self.warning_level == WARNING_LEVEL_SEVERE:
            print("🚨 【严重警告】审计任务未完成，无法退出", file=sys.stderr)
            print(f"    这是第 {self.counter_value + 1} 次检测到未完成任务！", file=sys.stderr)
        else:  # WARNING_LEVEL_NORMAL
            print("⚠️  【警告】审计任务未完成，无法退出", file=sys.stderr)

        print("━" * 55 + "\n", file=sys.stderr)

        # 显示 general-scanner 的分组信息
        if self.general_scanner_groups:
            agent_type = "通用扫描智能体"
            print(f"【general-scanner ({agent_type})】", file=sys.stderr)
            for agent_task_id, group_data in sorted(self.general_scanner_groups.items()):
                status_parts = []
                if group_data['pending_count'] > 0:
                    status_parts.append(f"待处理: {group_data['pending_count']}")
                if group_data['in_progress_count'] > 0:
                    status_parts.append(f"进行中: {group_data['in_progress_count']}")
                status_summary = " | ".join(status_parts) if status_parts else "未知状态"
                print(f"  任务ID: {agent_task_id} - {group_data['total_incomplete']} 个未完成任务 ({status_summary})", file=sys.stderr)
            print("", file=sys.stderr)

        # 显示其他智能体问题
        if self.agent_issues:
            print("\n".join(self.agent_issues), file=sys.stderr)

        # 显示执行时间异常的任务
        if self.abnormal_duration_tasks:
            print("━" * 55, file=sys.stderr)
            print("⏱️  执行时间异常任务检测", file=sys.stderr)
            print("━" * 55, file=sys.stderr)
            print(f"发现 {len(self.abnormal_duration_tasks)} 个执行时间小于10秒的任务，可能未正常完成：\n", file=sys.stderr)

            # 按 agent_name 分组显示
            grouped_tasks: Dict[str, List[Dict[str, Any]]] = {}
            for task in self.abnormal_duration_tasks:
                agent_key = f"{task['agent_name']} (ID: {task['agent_task_id']})"
                if agent_key not in grouped_tasks:
                    grouped_tasks[agent_key] = []
                grouped_tasks[agent_key].append(task)

            for agent_key, tasks in sorted(grouped_tasks.items()):
                print(f"【{agent_key}】", file=sys.stderr)
                for task in tasks:
                    print(f"  - 任务ID: {task['task_id']}", file=sys.stderr)
                    print(f"    描述: {task['description']}", file=sys.stderr)
                    print(f"    状态: {task['status']}", file=sys.stderr)
                    print(f"    执行时长: {task['duration']}秒 (< 10秒)", file=sys.stderr)
                print("", file=sys.stderr)

            print("⚠️  建议操作：", file=sys.stderr)
            print("这些任务可能因为执行过快而未正确完成，建议：", file=sys.stderr)
            print("1. 使用 update-task.sh 将这些任务的状态恢复为 pending", file=sys.stderr)
            print("2. 重新执行这些任务，确保任务充分执行", file=sys.stderr)
            print("3. 检查任务执行逻辑是否存在问题\n", file=sys.stderr)

            # 提供具体的恢复命令示例
            print("恢复命令示例：", file=sys.stderr)
            for task in self.abnormal_duration_tasks[:3]:  # 只显示前3个示例
                task_file = WORKSPACE_DIR / f"{task['agent_task_id']}-tasks.json"
                if not task_file.exists():
                    # 尝试其他可能的文件名格式
                    task_file = WORKSPACE_DIR / f"{task['agent_name']}-tasks.json"
                print(f"  .claude/skills/task-manage/scripts/tools/update-task.sh \\", file=sys.stderr)
                print(f"    {task_file} \\", file=sys.stderr)
                print(f"    {task['task_id']} \\", file=sys.stderr)
                print(f"    --status pending", file=sys.stderr)
            if len(self.abnormal_duration_tasks) > 3:
                print(f"  ... (还有 {len(self.abnormal_duration_tasks) - 3} 个任务)", file=sys.stderr)
            print("", file=sys.stderr)

        # 显示其他智能体的产物问题（general-scanner 不检查产物）
        if self.artifact_issues:
            print("━" * 55, file=sys.stderr)
            print("📁 产物完整性检查结果", file=sys.stderr)
            print("━" * 55, file=sys.stderr)
            print("\n".join(self.artifact_issues), file=sys.stderr)

            print("需要完成的产物：", file=sys.stderr)
            for issue in self.artifact_issues:
                if issue.startswith("  预期产物:"):
                    artifact_path = issue.split(":", 1)[1].strip()
                    print(f"  - {artifact_path}", file=sys.stderr)
            print("\n请先生成上述产物文件后再退出。", file=sys.stderr)

        print("\n" + "━" * 55, file=sys.stderr)

        # 根据警告级别显示不同的结束提示
        if self.warning_level == WARNING_LEVEL_SEVERE:
            print("🚨 【严重警告】请立即完成上述未完成任务！", file=sys.stderr)
            print(f"    当前触发次数: {self.counter_value + 1}/{EXIT_CHECK_THRESHOLD + 1} (严重警告阶段)", file=sys.stderr)
        else:  # WARNING_LEVEL_NORMAL
            print("⚠️  请继续完成上述未完成任务后再退出。", file=sys.stderr)

        print("━" * 55 + "\n", file=sys.stderr)


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