"""Run mining repair candidates through the real audit pipeline before publishing."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .experience import build_experience
from .mining_repair import (
    MiningRepairStore,
    _candidate_id,
    evaluate_mining_repair,
    load_finding_ledger,
    propose_mining_repairs,
)
from .verification import read_experience, write_json

CandidateRunner = Callable[..., Iterable[Mapping[str, Any]] | None]
NEXT_MINING_HEADING = "## 下一轮挖掘动作"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_json(path: str | Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    write_json(path, value)


def _records(path: Path) -> list[dict[str, Any]]:
    return read_experience(path) if path.is_file() else []


def _run_records(
    records: Iterable[Mapping[str, Any]],
    run_dir: Path,
    project: str,
) -> list[dict[str, Any]]:
    return [
        dict(record)
        for record in records
        if str(record.get("run_id") or "") == run_dir.name
        and str(record.get("project") or "") == project
    ]


def _baseline_blockers(candidate: Mapping[str, Any], baseline: list[dict[str, Any]]) -> list[str]:
    proposal = candidate["proposal"]
    if int(proposal.get("trusted_support", 0) or 0) < 1:
        return ["no_trusted_source_evidence"]
    if not baseline:
        return ["no_baseline_records"]
    outcomes = [
        str((record.get("outcome") or {}).get("verdict") or "unknown")
        for record in baseline
    ]
    positives = {"tp", "runtime-confirmed", "judge-approved", "human-confirmed", "static-supported"}
    if not any(verdict in positives for verdict in outcomes):
        return ["no_baseline_true_positive_control"]
    if proposal["kind"] == "false_positive" and "fp" not in outcomes:
        return ["no_baseline_false_positive_target"]
    return []


def _latest_run(repo_root: Path, project: str) -> Path | None:
    root = repo_root / "runs" / project
    if not root.is_dir():
        return None
    runs = [
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "audit-report.json").is_file()
    ]
    return sorted(runs, key=lambda path: path.name)[-1] if runs else None


def _environment_image(repo_root: Path, project: str) -> tuple[str, str]:
    manifest = _read_json(repo_root / "env" / project / "env-manifest.json", {})
    image = str(manifest.get("image") or "")
    miner_image = str(manifest.get("base_image") or "mygoldmine:dev")
    return image, miner_image


def _manifest_projects(repo_root: Path, manifest_path: str | Path) -> list[tuple[str, Path]]:
    payload = _read_json(manifest_path, {})
    projects = []
    for project, entry in payload.get("projects", {}).items():
        if not isinstance(entry, dict) or entry.get("status", "ok") != "ok":
            continue
        target = Path(entry.get("path") or repo_root / "targets" / project)
        if target.is_dir():
            projects.append((str(project), target))
    return projects


def _load_candidates(repo_root: Path) -> list[dict[str, Any]]:
    state = repo_root / "rsi" / "mining-repairs"
    seed_dir = state / "seed-candidates"
    if not (seed_dir / "index.json").is_file():
        seed_dir = state / "candidates"
    index = _read_json(seed_dir / "index.json", {})
    seeds = []
    for item in index.get("candidates", []):
        candidate = _read_json(item.get("path", ""), None)
        if candidate is not None:
            seeds.append(candidate)
    if not seeds:
        pools = []
        for name in ("verification-experience.jsonl", "verification-experience-labeled.jsonl"):
            path = repo_root / "rsi" / name
            if path.is_file():
                pools.extend(read_experience(path))
        seeds = propose_mining_repairs(
            pools,
            ledger=load_finding_ledger(repo_root / "ui" / "data" / "finding-ledger.json"),
        )

    candidates = []
    for seed in seeds:
        path = state / "agentic" / f"{seed['candidate_id']}.md"
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        root_cause = str(seed["proposal"]["pattern"]["root_cause"])
        if root_cause not in content or NEXT_MINING_HEADING not in content:
            raise ValueError(f"agentic repair is invalid: {path}")
        candidate = copy.deepcopy(seed)
        candidate["content"] = content
        candidate["content_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        candidate["agentic"] = {
            "harness": "claude-code",
            "agent": "mining-repair-learner",
            "skill": "mining-repair-learning",
            "seed_candidate_id": seed["candidate_id"],
        }
        candidate["candidate_id"] = _candidate_id(candidate)
        candidates.append(candidate)
    return candidates


class SubprocessCandidateRunner:
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def _execute(
        self,
        command: list[str],
        log_path: Path,
        env: Mapping[str, str],
    ) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                env=dict(env),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if completed.returncode:
            raise RuntimeError(
                f"candidate pipeline command failed ({completed.returncode}): {command[1]}"
            )

    def __call__(
        self,
        *,
        project: str,
        target: Path,
        run_dir: Path,
        image: str,
        miner_image: str,
        context_file: Path,
        attempt_dir: Path,
    ) -> None:
        env = os.environ.copy()
        env.update({
            "MYGOLDMINE_IMAGE": miner_image,
            "PERSIST_SANDBOX": "0",
            "RSI_REPAIR_CONTEXT_FILE": str(context_file),
            "RSI_VALIDATION_TRAJECTORY": str(attempt_dir / "validation.jsonl"),
        })
        timeout = env.get("RSI_REPAIR_TIMEOUT", "21600")
        model = env.get("MODEL", "360-proxy/deepseek/deepseek-v4.1-flash")
        self._execute(
            [
                "bash",
                str(self.repo_root / "scripts/mine/mine_one_docker.sh"),
                "--target", str(target),
                "--project", project,
                "--run-dir", str(run_dir),
                "--timeout", timeout,
                "--model", model,
                "--agent", "security-orchestrator",
            ],
            attempt_dir / "mining.log",
            env,
        )
        self._execute(
            [
                "python3",
                str(self.repo_root / "scripts/mine/check_report.py"),
                "--report", str(run_dir / "audit-report.json"),
                "--output", str(run_dir / "report-quality.json"),
                "--fail-missing",
                "--fail-language",
            ],
            attempt_dir / "report-quality.log",
            env,
        )
        self._execute(
            [
                "bash",
                str(self.repo_root / "scripts/verify/phase4_verify_agent.sh"),
                "--project", project,
                "--run-dir", str(run_dir),
                "--image", image,
                "--source", str(target),
                "--max", env.get("VERIFY_MAX", "10"),
                "--severity", env.get("VERIFY_SEVERITY", "critical,high"),
                "--timeout", "300",
                "--agent-timeout", env.get("VERIFY_AGENT_TIMEOUT", "900"),
                "--output", str(run_dir / "verify/agent"),
            ],
            attempt_dir / "verify.log",
            env,
        )
        self._execute(
            [
                "bash",
                str(self.repo_root / "scripts/redteam/phase5_redteam.sh"),
                "--project", project,
                "--run-dir", str(run_dir),
                "--max", env.get("REDTEAM_MAX", "5"),
                "--severity", env.get("VERIFY_SEVERITY", "critical,high"),
                "--model", env.get("REDTEAM_MODEL", "flint"),
                "--build-timeout", env.get("REDTEAM_BUILD_TIMEOUT", "1260"),
                "--agent-timeout", env.get("REDTEAM_AGENT_TIMEOUT", "900"),
                "--judge-timeout", env.get("REDTEAM_JUDGE_TIMEOUT", "360"),
                "--output", str(run_dir / "redteam"),
            ],
            attempt_dir / "redteam.log",
            env,
        )


def _candidate_experience(
    repo_root: Path,
    run_dir: Path,
    attempt_dir: Path,
) -> list[dict[str, Any]]:
    from scripts.workflow.finding_ledger import build_ledger

    runs_root = run_dir.parent.parent
    ledger = build_ledger(runs_root=runs_root, root=repo_root)
    ledger_path = attempt_dir / "finding-ledger.json"
    _write_json(ledger_path, ledger)
    records = build_experience(
        ledger_path=ledger_path,
        refine_path=None,
        auto_path=None,
        validation_path=attempt_dir / "validation.jsonl",
        runs_root=runs_root,
        output_path=attempt_dir / "experience.jsonl",
    )
    return _run_records(records, run_dir, str(run_dir.parent.name))


def _candidate_context(candidate: Mapping[str, Any], path: Path) -> None:
    content = (
        "## 本轮接受评估的挖掘修复候选\n\n"
        "以下规则正在隔离候选运行中使用，尚未发布。必须在本次挖掘中实际应用它，"
        "但仍需根据当前代码建立证据，不得直接继承历史结论。\n\n"
        f"{candidate['content']}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def drive_mining_repairs(
    repo_root: str | Path,
    *,
    scope: str,
    project: str = "",
    target: str | Path = "",
    baseline_run: str | Path = "",
    image: str = "",
    miner_image: str = "",
    manifest: str | Path = "",
    output: str | Path = "",
    max_candidates: int = 1,
    runner: CandidateRunner | None = None,
) -> dict[str, Any]:
    if scope not in {"project", "shared"}:
        raise ValueError("mining repair driver scope must be project or shared")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    root = Path(repo_root).resolve()
    runner = runner or SubprocessCandidateRunner(root)
    all_candidates = _load_candidates(root)
    if scope == "project":
        candidates = [
            candidate for candidate in all_candidates
            if candidate["proposal"]["scope"] == "project"
            and candidate["proposal"].get("project") == project
        ]
    else:
        candidates = [
            candidate for candidate in all_candidates
            if candidate["proposal"]["scope"] == "shared"
        ]
    candidates.sort(key=lambda item: (
        item["proposal"]["kind"] != "false_positive",
        -int(item["proposal"].get("trusted_support", 0) or 0),
        item["candidate_id"],
    ))

    pools = []
    for name in ("verification-experience.jsonl", "verification-experience-labeled.jsonl"):
        path = root / "rsi" / name
        if path.is_file():
            pools.extend(read_experience(path))
    manifest_path = Path(manifest) if manifest else root / "targets" / "manifest.json"
    available_targets = _manifest_projects(root, manifest_path)
    results = []
    for candidate in candidates[:max_candidates]:
        proposal = candidate["proposal"]
        source_projects = set(proposal.get("source_projects", []))
        selected_project = project
        selected_target = Path(target) if target else None
        selected_baseline = Path(baseline_run) if baseline_run else None
        selected_image = image
        selected_miner_image = miner_image
        if scope == "shared":
            choices = [
                (name, path)
                for name, path in available_targets
                if name not in source_projects
            ]
            if selected_project:
                choices = [choice for choice in choices if choice[0] == selected_project]
            if not selected_project or not selected_baseline:
                fallback = None
                for name, path in choices:
                    baseline = _latest_run(root, name)
                    if baseline is None:
                        continue
                    if fallback is None:
                        fallback = (name, path, baseline)
                    records = _run_records(pools, baseline, name)
                    if not _baseline_blockers(candidate, records):
                        selected_project = name
                        selected_target = path
                        selected_baseline = baseline
                        fallback = None
                        break
                if fallback is not None:
                    selected_project, selected_target, selected_baseline = fallback
            if not selected_image:
                selected_image, selected_miner_image = _environment_image(root, selected_project)
        if not selected_project or not selected_target or not selected_baseline:
            results.append({
                "candidate_id": candidate["candidate_id"],
                "status": "insufficient",
                "reasons": ["no_applicable_baseline_run"],
            })
            continue

        baseline_records = _run_records(pools, selected_baseline, selected_project)
        blockers = _baseline_blockers(candidate, baseline_records)
        if scope == "shared" and selected_project in source_projects:
            blockers.append("shared_holdout_required")
        if blockers:
            results.append({
                "candidate_id": candidate["candidate_id"],
                "project": selected_project,
                "baseline_run": str(selected_baseline),
                "status": "insufficient",
                "reasons": blockers,
            })
            continue

        attempt_id = f"{_stamp()}-{candidate['candidate_id'][-8:]}"
        attempt_dir = root / "rsi" / "mining-repairs" / "attempts" / attempt_id
        run_dir = (
            root / "rsi" / "mining-repairs" / "attempt-runs"
            / selected_project / f"{attempt_id}-{selected_baseline.name}"
        )
        attempt_dir.mkdir(parents=True, exist_ok=True)
        context_file = attempt_dir / "candidate-context.md"
        _candidate_context(candidate, context_file)
        result: dict[str, Any] = {
            "candidate_id": candidate["candidate_id"],
            "scope": scope,
            "project": selected_project,
            "baseline_run": str(selected_baseline),
            "candidate_run": str(run_dir),
            "context_file": str(context_file),
        }
        try:
            produced = runner(
                project=selected_project,
                target=selected_target,
                run_dir=run_dir,
                image=selected_image,
                miner_image=selected_miner_image,
                context_file=context_file,
                attempt_dir=attempt_dir,
            )
            candidate_records = (
                [dict(record) for record in produced]
                if produced is not None
                else _candidate_experience(root, run_dir, attempt_dir)
            )
            evaluation = evaluate_mining_repair(
                candidate,
                baseline_records,
                candidate_records,
                holdout_projects=[selected_project] if scope == "shared" else [],
            )
            _write_json(attempt_dir / "evaluation.json", evaluation)
            result["evaluation"] = evaluation
            result["status"] = evaluation["status"]
            if evaluation["accepted"]:
                version = MiningRepairStore(root).apply(candidate, evaluation)
                result["publication"] = {
                    "status": "published",
                    "version_id": version["version_id"],
                    "target": version["target"],
                }
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            _write_json(attempt_dir / "error.json", {"error": str(exc)})
        results.append(result)

    published = sum(item.get("publication", {}).get("status") == "published" for item in results)
    errors = sum(item.get("status") == "error" for item in results)
    accepted = sum(item.get("status") == "accepted" for item in results)
    all_insufficient = not results or all(
        item.get("status") == "insufficient" for item in results
    )
    status = (
        "error" if errors
        else "ok" if published
        else "insufficient" if all_insufficient
        else "rejected"
    )
    report = {
        "schema_version": 1,
        "generated_at": _now(),
        "scope": scope,
        "status": status,
        "candidates": len(results),
        "accepted": accepted,
        "published": published,
        "results": results,
        "candidate_execution": "isolated_real_mining_verify_redteam",
    }
    if output:
        _write_json(Path(output), report)
    return report
