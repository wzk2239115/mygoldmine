#!/usr/bin/env python3
"""统一报告身份及交付边界；运行环境只形成快照，不作为可移植证据。"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path


def report_project(report, expected=None):
    values = []
    if isinstance(report, dict):
        if "project" in report:
            values.append(("project", report["project"]))
        metadata = report.get("metadata")
        if isinstance(metadata, dict) and "project_id" in metadata:
            values.append(("metadata.project_id", metadata["project_id"]))
    for field, value in values:
        if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", value
        ):
            raise ValueError(
                f"报告项目编号必须为 {expected or '有效项目标识'}，{field} 字段无效；"
                "显示名称应写入 project_name"
            )
    if not values:
        raise ValueError(
            f"报告项目编号必须为 {expected or '有效项目标识'}，缺少 project 或 metadata.project_id"
        )
    if len({value for _, value in values}) != 1:
        raise ValueError("报告项目编号冲突：project 与 metadata.project_id 必须一致")
    value = values[0][1]
    if expected and value != expected:
        raise ValueError(
            f"报告项目编号必须为 {expected}，实际为 {value}；显示名称应写入 project_name"
        )
    return value


def file_hash(file):
    descriptor = os.open(file, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return digest


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def runtime_environment(directory):
    """只识别有完整配置的 Python 虚拟环境，不按目录名称排除任意产物。"""
    directory = Path(directory)
    config = directory / "pyvenv.cfg"
    if directory.is_symlink() or config.is_symlink() or not config.is_file():
        return None
    if config.stat().st_size > 65536:
        return None
    fields = {}
    for line in config.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    if not fields.get("home") or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", fields.get("version", "")):
        return None
    if not any(os.path.lexists(directory / name) for name in ("bin/python", "Scripts/python.exe")):
        return None
    entries = []

    def walk(folder):
        for file in sorted(folder.iterdir()):
            metadata = file.lstat()
            row = {"path": file.relative_to(directory).as_posix()}
            if stat.S_ISLNK(metadata.st_mode):
                row.update(type="symlink", link=os.readlink(file))
            elif stat.S_ISDIR(metadata.st_mode):
                row["type"] = "directory"
            elif stat.S_ISREG(metadata.st_mode):
                row.update(type="file", size=metadata.st_size, sha256=file_hash(file))
            else:
                raise ValueError(f"运行环境含不支持的文件类型：{file}")
            entries.append(row)
            if row["type"] == "directory":
                walk(file)

    walk(directory)
    snapshot = {
        "schema_version": 1,
        "kind": "python-venv",
        "role": "runtime_only",
        "portable": False,
        "configuration": fields,
        "entries": entries,
        "notice": (
            "仅记录配置、文件摘要和链接文本，不解析容器解释器链接，"
            "不把环境文件作为验证证据；重建时使用原镜像及环境定义。"
        ),
    }
    snapshot["sha256"] = fingerprint(snapshot)
    return snapshot


def validate_verification_report(file, boundary):
    """校验报告明确引用的附件；不能以环境快照代替缺失的脚本或证据。"""
    file, boundary = Path(file), Path(boundary).resolve()
    data = json.loads(file.read_text())
    parent = file.parent

    def required(value, base, kind=None):
        if not isinstance(value, str) or not value:
            raise ValueError(f"验证附件路径无效：{file}")
        relative = Path(value)
        if ".." in relative.parts:
            raise ValueError(f"验证附件路径越界：{value}")
        candidate = relative if relative.is_absolute() else base / relative
        # /verify 是一次性容器内固定挂载点，不是宿主机绝对路径。
        if relative.is_absolute() and str(relative).startswith("/verify/"):
            candidate = parent / relative.relative_to("/verify")
        if relative.is_absolute() and not candidate.resolve().is_relative_to(boundary):
            portable = None
            if kind == "harness" and "/harness/" in value:
                portable = parent / "harness" / value.split("/harness/", 1)[1]
            elif kind == "finding_file" and relative.name in {"finding.json", "finding.md"}:
                portable = parent / relative.name
            if portable is not None and portable.is_file() and not portable.is_symlink():
                if (
                    candidate.is_file()
                    and not candidate.is_symlink()
                    and file_hash(candidate) != file_hash(portable)
                ):
                    raise ValueError("旧版引用与交付副本内容不一致")
                candidate = portable
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError(f"验证报告引用的附件缺失或不是普通文件：{candidate}")
        actual = candidate.resolve()
        if not actual.is_relative_to(boundary):
            raise ValueError(f"验证附件路径超出交付目录：{candidate}")
        for ancestor in [candidate.parent, *candidate.parents]:
            if not ancestor.is_relative_to(boundary):
                break
            if runtime_environment_marker(ancestor):
                raise ValueError(f"验证证据不能仅位于临时运行环境中：{candidate}")
        return str(actual)

    files = []
    evidence = data.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("验证报告 evidence 必须是路径数组")
    if data.get("verdict") == "confirmed" and not evidence:
        raise ValueError("蓝队确认缺少明确的证据附件")
    for value in evidence:
        if not isinstance(value, str):
            raise ValueError("验证证据路径必须是字符串")
        relative = Path(value)
        base = parent if relative.parts and relative.parts[0] == "evidence" else parent / "evidence"
        files.append(required(value, base))
    for key in ("harness", "finding_file"):
        if data.get(key):
            files.append(required(data[key], parent, key))
    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("验证附件清单必须是对象")
    for value in artifacts.values():
        files.append(required(value, parent))
    return {"files": sorted(set(files))}


def runtime_environment_marker(directory):
    config = directory / "pyvenv.cfg"
    return config.is_file() and not config.is_symlink()


def recover_verification_delivery(report, source):
    """只从报告字节完全相同的执行目录补齐附件，不生成日志或覆盖既有内容。"""
    import shutil

    report, source = Path(report).resolve(), Path(source).resolve()
    original = source / report.name
    if not original.is_file() or file_hash(original) != file_hash(report):
        raise ValueError("恢复源报告与当前报告摘要不同，禁止迁移")
    checked = validate_verification_report(original, source)
    files = [Path(name) for name in checked["files"]]
    for name in ("verdict.json",):
        if (source / name).is_file():
            files.append(source / name)
    restored = []
    for file in files:
        relative = file.relative_to(source)
        target = report.parent / relative
        if not target.resolve().is_relative_to(report.parent):
            raise ValueError("恢复目标越界")
        if target.exists():
            if target.is_symlink() or file_hash(target) != file_hash(file):
                raise ValueError("恢复目标已有不同内容，禁止覆盖")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target, follow_symlinks=False)
            restored.append({"path": str(relative), "sha256": file_hash(target)})
    validate_verification_report(report, report.parent)
    receipt = {
        "schema_version": 1,
        "source": str(source),
        "report_sha256": file_hash(report),
        "restored": restored,
    }
    (report.parent / "delivery-recovery.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description="统一阶段交付契约")
    parser.add_argument("action", choices=["project", "runtime", "verification", "recover"])
    parser.add_argument("--expected")
    parser.add_argument("--path")
    parser.add_argument("--boundary")
    parser.add_argument("--source")
    args = parser.parse_args()
    try:
        if args.action == "project":
            value = {"project": report_project(json.load(sys.stdin), args.expected)}
        elif args.action == "runtime":
            value = runtime_environment(args.path)
        elif args.action == "recover":
            value = recover_verification_delivery(args.path, args.source)
        else:
            value = validate_verification_report(args.path, args.boundary)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
