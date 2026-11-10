"""Task identity is captured by the launcher, not supplied by the submitted report."""
import hashlib
import json
from pathlib import Path


def load(file):
    try:
        data = json.loads(Path(file).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def task_context(stage, root, project=None):
    root = Path(root).resolve()
    context = {"project": project} if project and project != "unknown" else {}
    if stage == "redteam-lab":
        task = load(root / "lab-task.json")
        for key in ("project", "finding_id", "finding_sha256", "source_binding"):
            if task.get(key) is not None:
                context[key] = task[key]
    else:
        finding = load(root / "finding.json")
        if not finding and stage == "verify":
            finding = load(root.parent / "inputs" / root.name / "finding.json")
        identifier = finding.get("id") or finding.get("finding_id")
        if identifier:
            context["finding_id"] = identifier
    bound = {}
    candidates = [root / "finding.json"]
    if stage == "judge":
        candidates += [root / name for name in
                       ("judge-input-result.json", "trace.jsonl", "scenario.json")]
    for file in candidates:
        if file.is_file() and not file.is_symlink():
            bound[str(file)] = hashlib.sha256(file.read_bytes()).hexdigest()
    if bound:
        context["input_hashes"] = bound
    return context


def validate_identity(data, context, require_project=False):
    if context.get("project") and (require_project or data.get("project") is not None):
        if data.get("project") != context["project"]:
            raise ValueError("产物项目编号与启动任务不一致")
    if context.get("finding_id"):
        if (data.get("finding_id") or data.get("id")) != context["finding_id"]:
            raise ValueError("产物候选编号与启动任务不一致")


def package_file(root, file):
    root = Path(root).resolve()
    file = Path(file)
    file = file if file.is_absolute() else root / file
    if ".." in file.parts or not file.is_relative_to(root):
        raise ValueError("必需附件超出本次交付目录：" + str(file))
    cursor = root
    for part in file.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("必需附件不能包含符号链接：" + str(file))
    if not file.is_file() or file.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("必需附件缺失、不是普通文件或超过大小限制：" + str(file))
    return str(file), file.read_bytes()


def declared_files(data, base):
    """Only explicit attachment fields; source-code references are not deliverables."""
    files = []
    for key in ("artifacts", "attachments"):
        values = data.get(key, [])
        values = values.values() if isinstance(values, dict) else values
        if not isinstance(values, (list, tuple)) and not hasattr(values, "__iter__"):
            raise ValueError("附件声明必须为路径数组或对象")
        if isinstance(values, str):
            raise ValueError("附件声明必须为路径数组或对象")
        for value in values:
            if isinstance(value, dict):
                value = value.get("path")
            if not isinstance(value, str) or not value:
                raise ValueError("附件声明中缺少有效路径")
            path = Path(value)
            files.append(path if path.is_absolute() else base / path)
    return files


def validate_bound_inputs(context):
    for name, expected in context.get("input_hashes", {}).items():
        file = Path(name)
        if (file.is_symlink() or not file.is_file()
                or hashlib.sha256(file.read_bytes()).hexdigest() != expected):
            raise ValueError("启动时绑定的输入文件缺失或已改变：" + name)
