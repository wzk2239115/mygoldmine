#!/usr/bin/env python3
"""统一运行工作区；历史目录通过原子交换迁移，保留旧路径访问。"""

import argparse
import ctypes
import hashlib
import json
import os
import re
from pathlib import Path


def prepare_verify_work(repo, project, task, output):
    repo = Path(repo).resolve()
    for value in (project, task):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", value):
            raise ValueError("项目或候选编号无效")
    output = Path(output).resolve()
    if output == repo:
        raise ValueError("验证交付目录不能是仓库根目录")
    identity = hashlib.sha256(str(output).encode()).hexdigest()[:24]
    work = repo / ".runtime/work" / project / identity / "verify" / task
    work.mkdir(parents=True, exist_ok=True)
    config = work / ".claude"
    if config.is_symlink():
        if config.resolve() != (repo / ".claude").resolve():
            raise ValueError("工作区配置链接不一致")
    elif config.exists():
        raise ValueError("工作区配置路径已被占用")
    else:
        try:
            config.symlink_to(repo / ".claude", target_is_directory=True)
        except FileExistsError:
            if not config.is_symlink() or config.resolve() != (repo / ".claude").resolve():
                raise
    (work / "tmp").mkdir(exist_ok=True)
    return work


def relocate(repo, name, destination):
    """Linux renameat2 交换两个名称，无不存在窗口；锁和打开文件保持同一 inode。"""
    repo = Path(repo).resolve()
    source, target = repo / name, repo / destination
    if source.is_symlink():
        if source.resolve() != target.resolve():
            raise ValueError("历史兼容链接指向不一致：" + name)
        return "already_migrated"
    if not source.exists():
        return "absent"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise ValueError("迁移目标已存在，拒绝覆盖：" + str(target))
    # 链接在交换后位于 source，因而相对 source.parent 解释。
    target.symlink_to(os.path.relpath(target, source.parent), target_is_directory=source.is_dir())
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(target), 2):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    except BaseException:
        target.unlink()
        raise
    return "migrated_with_compatibility_link"


def migrate(repo):
    repo = Path(repo).resolve()
    result = {}
    candidates = {
        ".state": ".runtime/state",
        ".stage-skills-loaded": ".runtime/legacy/stage-skills-loaded",
        ".workspace": ".runtime/legacy/workspace",
        ".verifyscratch": ".runtime/legacy/verifyscratch",
    }
    for item in repo.glob(".verify-work-*"):
        candidates[item.name] = ".runtime/legacy/verify/" + item.name.removeprefix(".")
    for name, target in candidates.items():
        result[name] = relocate(repo, name, target)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建验证工作区或迁移旧运行目录")
    parser.add_argument("action", choices=["verify-work", "migrate"])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project")
    parser.add_argument("--task")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.action == "migrate":
        print(json.dumps(migrate(args.repo), ensure_ascii=False, indent=2))
    else:
        print(prepare_verify_work(args.repo, args.project, args.task, args.output))
