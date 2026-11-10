import fcntl
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "runtime_paths", ROOT / "scripts/workflow/runtime_paths.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_isolated_workspaces_and_configuration(tmp_path):
    (tmp_path / ".claude/agents").mkdir(parents=True)
    output = tmp_path / "runs/project/round.meta/output/verify/F1"
    first = module.prepare_verify_work(tmp_path, "project", "F1", output)
    assert first.is_relative_to(tmp_path / ".runtime/work/project")
    assert first == module.prepare_verify_work(tmp_path, "project", "F1", output)
    assert (first / ".claude").resolve() == tmp_path / ".claude"
    assert (first / "tmp").is_dir()
    assert first != module.prepare_verify_work(
        tmp_path, "project", "F1", tmp_path / "runs/project/next/verify/F1"
    )
    assert first != module.prepare_verify_work(tmp_path, "other", "F1", output)
    with pytest.raises(ValueError):
        module.prepare_verify_work(tmp_path, "../escape", "F1", output)
    with pytest.raises(ValueError):
        module.prepare_verify_work(tmp_path, "project", "F1", tmp_path)


@pytest.mark.skipif(sys.platform != "linux", reason="原子目录交换使用 Linux renameat2")
def test_live_migration_preserves_open_files_locks_and_legacy_access(tmp_path):
    state = tmp_path / ".state"
    state.mkdir()
    queue = state / "queue.lock"
    with queue.open("a+") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        inode = os.fstat(owner.fileno()).st_ino
        assert module.relocate(tmp_path, ".state", ".runtime/state").startswith("migrated")
        assert state.is_symlink()
        assert queue.stat().st_ino == inode
        assert (tmp_path / ".runtime/state/queue.lock").stat().st_ino == inode
        with queue.open("a") as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
        owner.write("retained")
        owner.flush()
        assert queue.read_text() == "retained"
    assert module.relocate(tmp_path, ".state", ".runtime/state") == "already_migrated"


@pytest.mark.skipif(sys.platform != "linux", reason="原子目录交换使用 Linux renameat2")
def test_migration_does_not_overwrite_or_lose_legacy_files(tmp_path):
    scratch = tmp_path / ".verify-work-F1"
    scratch.mkdir()
    (scratch / "evidence.txt").write_text("original")
    module.migrate(tmp_path)
    assert (scratch / "evidence.txt").read_text() == "original"
    assert (
        tmp_path / ".runtime/legacy/verify/verify-work-F1/evidence.txt"
    ).read_text() == "original"
    occupied = tmp_path / ".state"
    occupied.mkdir()
    (tmp_path / ".runtime/state").mkdir()
    with pytest.raises(ValueError):
        module.relocate(tmp_path, ".state", ".runtime/state")
    assert occupied.is_dir() and not occupied.is_symlink()


def test_skill_snapshot_rejects_repository_root():
    import sys

    sys.path.insert(0, str(ROOT / "scripts/stages"))
    from skill_bank import instruction, spool_proposal

    with pytest.raises(ValueError, match="仓库根目录"):
        instruction("verify", ROOT, "demo")

    with pytest.raises(ValueError, match="仓库根目录"):
        spool_proposal("verify", ROOT, "general", "candidate", [])
