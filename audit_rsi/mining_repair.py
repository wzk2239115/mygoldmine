"""Evidence-gated mining repairs with shared/project scopes and rollback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .verification import data_hash, deduplicate_semantics

SCHEMA_VERSION = 1
TRUSTED_EVIDENCE = frozenset({"runtime", "judge", "manual", "human"})
POSITIVE_VERDICTS = frozenset(
    {"tp", "runtime-confirmed", "judge-approved", "human-confirmed", "static-supported"}
)
FALSE_POSITIVE_VERDICTS = frozenset({"fp"})
SHARED_SKILL_DIR = Path(".claude/skills/rsi-shared-experience")
PROJECT_RULE_ROOT = Path("knowledge/project-rules")
REPAIR_STATE_DIR = Path("rsi/mining-repairs")
DEFAULT_PATTERN_TITLE = "未命名模式"
DEFAULT_ROOT_CAUSE = "未提供根因"
FALSE_POSITIVE_HEADING = "误报排除"
CONFIRMED_PATTERN_HEADING = "已确认调查模式"
SHARED_SCOPE_TEXT = "共享"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read_json(path: str | Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_project(value: Any) -> str:
    project = re.sub(r"[^A-Za-z0-9._-]", "_", str(value or "")).strip("._")
    if not project:
        raise ValueError("project-scoped repair requires a safe project name")
    return project


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _outcome(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(record.get("outcome"))


def _verdict(record: Mapping[str, Any]) -> str:
    return str(_outcome(record).get("verdict") or "unknown").lower()


def _evidence(record: Mapping[str, Any]) -> str:
    return str(_outcome(record).get("evidence_class") or "none").lower()


def _trusted(record: Mapping[str, Any]) -> bool:
    return _evidence(record) in TRUSTED_EVIDENCE


def load_finding_ledger(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    payload = _read_json(path, {})
    occurrences = _mapping(payload).get("occurrences", {})
    if not isinstance(occurrences, Mapping):
        return {}
    return {
        str(key): dict(value)
        for key, value in occurrences.items()
        if isinstance(value, Mapping)
    }


def _enrich(record: Mapping[str, Any], ledger: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    enriched = dict(record)
    occurrence = _mapping(ledger.get(str(record.get("occurrence_id") or "")))
    raw = dict(_mapping(occurrence.get("raw")))
    context = dict(_mapping(record.get("context")))
    if not raw.get("category") and context.get("category"):
        raw["category"] = context["category"]
    if not raw.get("title"):
        raw["title"] = (
            context.get("finding_id")
            or record.get("semantic_id")
            or DEFAULT_PATTERN_TITLE
        )
    enriched["raw"] = raw
    return enriched


def _pattern(record: Mapping[str, Any]) -> dict[str, str]:
    raw = _mapping(record.get("raw"))
    root_cause = _normalize(raw.get("root_cause"))
    title = _normalize(raw.get("title"))
    signature_text = root_cause or title
    category = _normalize(raw.get("category") or _mapping(record.get("context")).get("category"))
    signature = hashlib.sha256(f"{category}\n{signature_text}".encode("utf-8")).hexdigest()[:20]
    return {
        "signature": signature,
        "category": str(
            raw.get("category")
            or _mapping(record.get("context")).get("category")
            or "unknown"
        ),
        "title": str(raw.get("title") or DEFAULT_PATTERN_TITLE),
        "root_cause": str(
            raw.get("root_cause") or raw.get("title") or DEFAULT_ROOT_CAUSE
        ),
    }


def _files(records: Iterable[Mapping[str, Any]]) -> list[str]:
    files: set[str] = set()
    for record in records:
        raw = _mapping(record.get("raw"))
        raw_files = raw.get("files")
        if isinstance(raw_files, list):
            files.update(str(item) for item in raw_files if isinstance(item, (str, int, float)))
        evidence = raw.get("evidence")
        if isinstance(evidence, list):
            for item in evidence:
                if isinstance(item, Mapping) and item.get("file"):
                    files.add(str(item["file"]))
    return sorted(files)[:20]


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    core = {
        "rule_id": candidate.get("rule_id"),
        "proposal": candidate.get("proposal"),
        "target": candidate.get("target"),
        "content": candidate.get("content"),
        "training_data_hash": candidate.get("training_data_hash"),
    }
    return f"mrc_{_digest(core)[:20]}"


def _render_rule(
    *,
    scope: str,
    project: str,
    kind: str,
    pattern: Mapping[str, str],
    records: Sequence[Mapping[str, Any]],
) -> str:
    is_fp = kind == "false_positive"
    heading = FALSE_POSITIVE_HEADING if is_fp else CONFIRMED_PATTERN_HEADING
    if scope == "shared":
        scope_text = SHARED_SCOPE_TEXT
    else:
        scope_text = f"仓库专属：{project}"
    occurrences = ", ".join(
        sorted(str(record.get("occurrence_id")) for record in records)
    )
    lines = [
        f"# {heading}：{pattern['title']}",
        "",
        f"- 作用域：{scope_text}",
        f"- 模式类别：{pattern['category']}",
        f"- 来源问题实例：{occurrences}",
        "",
        "## 已验证事实",
        "",
        str(pattern["root_cause"]),
        "",
        "## 下一轮挖掘动作",
        "",
    ]
    if is_fp:
        lines.extend([
            "1. 只有当根因、可达性前提和防护条件与上述已验证事实一致时，才排除同类候选问题。",
            "2. 不得只凭危险函数、文件名称、类别或关键词排除；代码或默认配置变化后必须重新判断。",
            "3. 排除时在审阅记录中引用本规则，并写明与已验证误报相同的反证。",
            "4. 缺少反证或只剩静态推测时保持待验证，不得把本规则当作运行时反证。",
        ])
    else:
        lines.extend([
            "1. 优先检查具有相同根因和信任边界的入口，但仍须重新建立当前代码的完整证据链。",
            "2. 复用已验证的调查路径，不直接复用漏洞结论；当前项目不可达时按实际证据降级。",
            "3. 发现同类候选后执行最小验证，静态相似不能写成已确认。",
        ])
    files = _files(records)
    if files and scope == "project":
        lines.extend(["", "## 相关文件", ""])
        for item in files:
            lines.append(f"- `{item}`")
    return "\n".join(lines) + "\n"


def propose_mining_repairs(
    records: Iterable[Mapping[str, Any]],
    *,
    ledger: Mapping[str, Mapping[str, Any]] | None = None,
    min_shared_projects: int = 2,
) -> list[dict[str, Any]]:
    if min_shared_projects < 2:
        raise ValueError("shared repairs require at least two source projects")
    source = [dict(record) for record in records]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in deduplicate_semantics(source):
        verdict = _verdict(record)
        if verdict not in POSITIVE_VERDICTS and verdict not in FALSE_POSITIVE_VERDICTS:
            continue
        enriched = _enrich(record, ledger or {})
        pattern = _pattern(enriched)
        if not _normalize(pattern["root_cause"]):
            continue
        kind = "false_positive" if verdict in FALSE_POSITIVE_VERDICTS else "confirmed_pattern"
        groups.setdefault((kind, pattern["signature"]), []).append(enriched)

    candidates = []
    for (kind, signature), group in sorted(groups.items()):
        projects = sorted({
            str(record.get("project") or "")
            for record in group
            if record.get("project")
        })
        if not projects:
            continue
        scopes: list[tuple[str, str, list[dict[str, Any]]]]
        if len(projects) >= min_shared_projects:
            scopes = [("shared", "", group)]
        else:
            scopes = [
                (
                    "project",
                    project,
                    [record for record in group if record.get("project") == project],
                )
                for project in projects
            ]
        for scope, project, selected in scopes:
            pattern = _pattern(selected[0])
            evidence_classes = sorted({_evidence(record) for record in selected})
            trusted_support = sum(_trusted(record) for record in selected)
            trusted_projects = sorted({
                str(record.get("project")) for record in selected if _trusted(record)
            })
            target = (
                str(SHARED_SKILL_DIR / "rules" / f"mr-{signature}.md")
                if scope == "shared"
                else str(PROJECT_RULE_ROOT / _safe_project(project) / f"mr-{signature}.md")
            )
            content = _render_rule(
                scope=scope,
                project=project,
                kind=kind,
                pattern=pattern,
                records=selected,
            )
            proposal = {
                "scope": scope,
                "project": project or None,
                "kind": kind,
                "pattern": dict(pattern),
                "source_occurrences": sorted(
                    str(record.get("occurrence_id")) for record in selected
                ),
                "source_projects": projects if scope == "shared" else [project],
                "evidence_classes": evidence_classes,
                "trusted_support": trusted_support,
                "trusted_projects": trusted_projects,
                "min_shared_projects": min_shared_projects,
            }
            candidate = {
                "schema_version": SCHEMA_VERSION,
                "rule_id": f"mr-{signature}",
                "status": "proposal_only",
                "proposal": proposal,
                "target": target,
                "content": content,
                "content_sha256": _text_hash(content),
                "training_data_hash": data_hash(selected),
                "mutation": "candidate_only",
            }
            candidate["candidate_id"] = _candidate_id(candidate)
            candidates.append(candidate)
    return sorted(
        candidates,
        key=lambda item: (
            item["proposal"]["scope"],
            item["rule_id"],
            item["candidate_id"],
        ),
    )


def save_mining_repair_candidates(
    candidates: Iterable[Mapping[str, Any]],
    output: str | Path,
) -> dict[str, Any]:
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for raw in candidates:
        candidate = dict(raw)
        path = destination / f"{candidate['candidate_id']}.json"
        _write_json(path, candidate)
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "rule_id": candidate["rule_id"],
            "scope": candidate["proposal"]["scope"],
            "project": candidate["proposal"].get("project"),
            "kind": candidate["proposal"]["kind"],
            "path": str(path),
            "trusted_support": candidate["proposal"]["trusted_support"],
        })
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "candidates": rows,
        "count": len(rows),
        "mutation": "candidate_only",
    }
    _write_json(destination / "index.json", report)
    return report


def _semantic_map(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(record["semantic_id"]): dict(record)
        for record in deduplicate_semantics(records)
    }


def _rates(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    selected = list(records)
    positives = sum(_verdict(record) in POSITIVE_VERDICTS for record in selected)
    false_positives = sum(_verdict(record) in FALSE_POSITIVE_VERDICTS for record in selected)
    duplicates = sum(_verdict(record) == "duplicate" for record in selected)
    known = positives + false_positives + duplicates
    return {
        "semantics": len(selected),
        "known": known,
        "positives": positives,
        "false_positives": false_positives,
        "duplicates": duplicates,
        "false_positive_rate": round(false_positives / known, 6) if known else None,
        "duplicate_rate": round(duplicates / known, 6) if known else None,
    }


def evaluate_mining_repair(
    candidate: Mapping[str, Any],
    baseline_records: Iterable[Mapping[str, Any]],
    candidate_records: Iterable[Mapping[str, Any]],
    *,
    holdout_projects: Sequence[str] = (),
) -> dict[str, Any]:
    if candidate.get("candidate_id") != _candidate_id(candidate):
        raise ValueError("candidate identity does not match its content")
    proposal = _mapping(candidate.get("proposal"))
    scope = str(proposal.get("scope") or "")
    project = str(proposal.get("project") or "")
    source_projects = {str(item) for item in proposal.get("source_projects", [])}
    if scope == "project":
        if holdout_projects and project not in holdout_projects:
            projects: list[str] = []
        else:
            projects = [project]
    elif scope == "shared":
        projects = sorted(set(holdout_projects) - source_projects)
    else:
        raise ValueError("candidate scope must be shared or project")

    baseline_all = list(baseline_records)
    candidate_all = list(candidate_records)
    baseline = [record for record in baseline_all if str(record.get("project")) in projects]
    candidate_rows = [record for record in candidate_all if str(record.get("project")) in projects]
    before = _semantic_map(baseline)
    after = _semantic_map(candidate_rows)

    baseline_positives = {
        key for key, record in before.items() if _verdict(record) in POSITIVE_VERDICTS
    }
    baseline_fps = {
        key for key, record in before.items() if _verdict(record) in FALSE_POSITIVE_VERDICTS
    }
    after_positives = {
        key for key, record in after.items() if _verdict(record) in POSITIVE_VERDICTS
    }
    after_fps = {
        key for key, record in after.items() if _verdict(record) in FALSE_POSITIVE_VERDICTS
    }
    true_positives_lost = sorted(
        key for key in baseline_positives
        if key not in after or _verdict(after[key]) in FALSE_POSITIVE_VERDICTS
    )
    false_positives_suppressed = sorted(key for key in baseline_fps if key not in after)
    new_false_positives = sorted(after_fps - baseline_fps)
    new_true_positives = sorted(after_positives - baseline_positives)
    before_rates = _rates(before.values())
    after_rates = _rates(candidate_rows)

    reasons = []
    insufficient = False
    if int(proposal.get("trusted_support", 0) or 0) < 1:
        reasons.append("no_trusted_source_evidence")
        insufficient = True
    if scope == "shared":
        trusted_project_count = len(set(proposal.get("trusted_projects", [])))
        required_projects = int(proposal.get("min_shared_projects", 2) or 2)
        if trusted_project_count < required_projects:
            reasons.append("insufficient_trusted_source_projects")
            insufficient = True
        if not holdout_projects:
            reasons.append("shared_holdout_required")
            insufficient = True
    if not projects:
        reasons.append("no_applicable_holdout_project")
        insufficient = True
    if not before or not after:
        reasons.append("paired_real_runs_required")
        insufficient = True
    if not baseline_positives:
        reasons.append("no_baseline_true_positive_control")
        insufficient = True

    kind = str(proposal.get("kind") or "")
    if kind == "false_positive":
        if not baseline_fps:
            reasons.append("no_baseline_false_positive_target")
            insufficient = True
        if not false_positives_suppressed:
            reasons.append("no_false_positive_suppressed")
            insufficient = True
        before_rate = before_rates["false_positive_rate"]
        after_rate = after_rates["false_positive_rate"]
        if before_rate is None or after_rate is None or after_rate >= before_rate:
            reasons.append("false_positive_rate_not_reduced")
    elif kind == "confirmed_pattern":
        if not new_true_positives:
            reasons.append("no_new_true_positive")
            insufficient = True
    else:
        raise ValueError("unsupported mining repair kind")

    if true_positives_lost:
        reasons.append("true_positive_regression")
    if new_false_positives:
        reasons.append("new_false_positive_regression")
    status = "insufficient" if insufficient else "rejected" if reasons else "accepted"
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate["candidate_id"],
        "rule_id": candidate["rule_id"],
        "scope": scope,
        "project": project or None,
        "evaluation_projects": projects,
        "source_projects": sorted(source_projects),
        "status": status,
        "accepted": status == "accepted",
        "reasons": reasons,
        "counts": {
            "baseline_true_positives": len(baseline_positives),
            "baseline_false_positives": len(baseline_fps),
            "false_positives_suppressed": len(false_positives_suppressed),
            "true_positives_lost": len(true_positives_lost),
            "new_false_positives": len(new_false_positives),
            "new_true_positives": len(new_true_positives),
        },
        "false_positives_suppressed": false_positives_suppressed,
        "true_positives_lost": true_positives_lost,
        "new_false_positives": new_false_positives,
        "new_true_positives": new_true_positives,
        "baseline": before_rates,
        "candidate": after_rates,
        "baseline_data_hash": data_hash(baseline),
        "candidate_data_hash": data_hash(candidate_rows),
        "evaluation": "paired real mining outcomes; unknown is not treated as false positive",
    }


class MiningRepairStore:
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.state_root = self.repo_root / REPAIR_STATE_DIR

    def _target(self, candidate: Mapping[str, Any]) -> Path:
        proposal = _mapping(candidate.get("proposal"))
        rule_id = str(candidate.get("rule_id") or "")
        if not re.fullmatch(r"mr-[a-f0-9]{20}", rule_id):
            raise ValueError("invalid mining repair rule identity")
        if proposal.get("scope") == "shared":
            return self.repo_root / SHARED_SKILL_DIR / "rules" / f"{rule_id}.md"
        if proposal.get("scope") == "project":
            project_root = PROJECT_RULE_ROOT / _safe_project(proposal.get("project"))
            return self.repo_root / project_root / f"{rule_id}.md"
        raise ValueError("candidate scope must be shared or project")

    def _manifest_path(self, target: Path) -> Path:
        return target.parent / "index.json"

    def _empty_manifest(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        proposal = _mapping(candidate.get("proposal"))
        return {
            "schema_version": SCHEMA_VERSION,
            "scope": proposal.get("scope"),
            "project": proposal.get("project"),
            "rules": {},
        }

    def apply(self, candidate: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
        if candidate.get("candidate_id") != _candidate_id(candidate):
            raise ValueError("candidate identity does not match its content")
        if evaluation.get("candidate_id") != candidate.get("candidate_id"):
            raise ValueError("evaluation belongs to a different candidate")
        if not evaluation.get("accepted") or evaluation.get("status") != "accepted":
            raise ValueError("mining repair requires an accepted real-run evaluation")
        if candidate.get("content_sha256") != _text_hash(str(candidate.get("content") or "")):
            raise ValueError("candidate content hash mismatch")

        target = self._target(candidate)
        manifest_path = self._manifest_path(target)
        previous_content = target.read_text(encoding="utf-8") if target.exists() else None
        previous_manifest = _read_json(manifest_path, None)
        if previous_manifest is None:
            previous_manifest = self._empty_manifest(candidate)
        if not isinstance(previous_manifest.get("rules"), dict):
            raise ValueError("active mining repair manifest is invalid")
        rule_id = str(candidate["rule_id"])
        existing_rule = previous_manifest["rules"].get(rule_id)
        if previous_content is not None:
            if existing_rule is None:
                raise ValueError("refusing to overwrite an unmanaged mining repair")
            if _text_hash(previous_content) != existing_rule.get("sha256"):
                raise ValueError("active mining repair changed after evaluation")

        applied_manifest = json.loads(json.dumps(previous_manifest))
        version_identity = _digest({
            "candidate_id": candidate["candidate_id"],
            "evaluation": evaluation,
            "previous_content": previous_content,
            "previous_manifest": previous_manifest,
            "created_at": _now(),
        })
        version_id = f"mrv_{version_identity[:20]}"
        relative_target = target.relative_to(self.repo_root)
        relative_manifest = manifest_path.relative_to(self.repo_root)
        applied_manifest["rules"][rule_id] = {
            "candidate_id": candidate["candidate_id"],
            "version_id": version_id,
            "file": target.name,
            "sha256": candidate["content_sha256"],
            "scope": candidate["proposal"]["scope"],
            "project": candidate["proposal"].get("project"),
            "kind": candidate["proposal"]["kind"],
            "pattern": candidate["proposal"]["pattern"],
            "source_occurrences": candidate["proposal"]["source_occurrences"],
            "source_projects": candidate["proposal"]["source_projects"],
            "evaluation": {
                "status": evaluation["status"],
                "evaluation_projects": evaluation.get("evaluation_projects", []),
                "counts": evaluation.get("counts", {}),
                "candidate_data_hash": evaluation.get("candidate_data_hash"),
            },
            "updated_at": _now(),
        }
        version = {
            "schema_version": SCHEMA_VERSION,
            "version_id": version_id,
            "status": "prepared",
            "created_at": _now(),
            "candidate_id": candidate["candidate_id"],
            "rule_id": rule_id,
            "target": str(relative_target),
            "manifest": str(relative_manifest),
            "content": candidate["content"],
            "previous_content": previous_content,
            "previous_manifest": previous_manifest,
            "applied_manifest": applied_manifest,
            "evaluation": dict(evaluation),
        }
        version_dir = self.state_root / "versions" / version_id
        if version_dir.exists():
            raise FileExistsError(f"mining repair version already exists: {version_id}")
        _write_json(version_dir / "version.json", version)
        try:
            _atomic_write(target, str(candidate["content"]))
            _write_json(manifest_path, applied_manifest)
            version["status"] = "active"
            _write_json(version_dir / "version.json", version)
        except BaseException:
            if previous_content is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_write(target, previous_content)
            if manifest_path.exists():
                _write_json(manifest_path, previous_manifest)
            version["status"] = "failed"
            _write_json(version_dir / "version.json", version)
            raise
        current_path = self.state_root / "current.json"
        current = _read_json(current_path, {"schema_version": SCHEMA_VERSION, "versions": []})
        current["versions"] = [
            item
            for item in current.get("versions", [])
            if item.get("version_id") != version_id
        ]
        current["versions"].append({
            "version_id": version_id,
            "candidate_id": candidate["candidate_id"],
            "rule_id": rule_id,
            "target": str(relative_target),
            "status": "active",
            "created_at": version["created_at"],
        })
        _write_json(current_path, current)
        return version

    def rollback(self, version_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"mrv_[a-f0-9]{20}", version_id):
            raise ValueError("invalid mining repair version identity")
        version_path = self.state_root / "versions" / version_id / "version.json"
        version = _read_json(version_path, None)
        if not isinstance(version, dict):
            raise FileNotFoundError(version_path)
        if version.get("status") != "active":
            raise ValueError("only an active mining repair version can be rolled back")
        target = self.repo_root / str(version["target"])
        manifest_path = self.repo_root / str(version["manifest"])
        target_is_safe = target.is_relative_to(self.repo_root)
        manifest_is_safe = manifest_path.is_relative_to(self.repo_root)
        if not target_is_safe or not manifest_is_safe:
            raise ValueError("mining repair version escapes repository root")
        current_hash = (
            _text_hash(target.read_text(encoding="utf-8")) if target.exists() else None
        )
        if current_hash != _text_hash(str(version["content"])):
            raise ValueError("active mining repair no longer matches the version")
        current_manifest = _read_json(manifest_path, None)
        if current_manifest != version["applied_manifest"]:
            raise ValueError("a later mining repair change must be rolled back first")
        previous_content = version.get("previous_content")
        if previous_content is None:
            target.unlink()
        else:
            _atomic_write(target, str(previous_content))
        previous_manifest = version["previous_manifest"]
        if previous_manifest.get("rules"):
            _write_json(manifest_path, previous_manifest)
        else:
            manifest_path.unlink(missing_ok=True)
        version["status"] = "rolled_back"
        version["rolled_back_at"] = _now()
        _write_json(version_path, version)
        current_path = self.state_root / "current.json"
        current = _read_json(current_path, {"schema_version": SCHEMA_VERSION, "versions": []})
        for item in current.get("versions", []):
            if item.get("version_id") == version_id:
                item["status"] = "rolled_back"
                item["rolled_back_at"] = version["rolled_back_at"]
        _write_json(current_path, current)
        return version


def load_active_mining_repairs(
    repo_root: str | Path,
    project: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    root = Path(repo_root).resolve()
    safe_project = _safe_project(project)
    manifests = [
        root / SHARED_SKILL_DIR / "rules" / "index.json",
        root / PROJECT_RULE_ROOT / safe_project / "index.json",
    ]
    rules = []
    errors = []
    for manifest_path in manifests:
        manifest = _read_json(manifest_path, None)
        if manifest is None:
            continue
        if manifest.get("scope") == "project" and manifest.get("project") != safe_project:
            errors.append(f"project scope mismatch: {manifest_path}")
            continue
        for rule_id, metadata in sorted(_mapping(manifest.get("rules")).items()):
            if not isinstance(metadata, Mapping):
                errors.append(f"invalid rule metadata: {manifest_path}:{rule_id}")
                continue
            target = manifest_path.parent / str(metadata.get("file") or "")
            if target.parent != manifest_path.parent or target.name != f"{rule_id}.md":
                errors.append(f"invalid rule path: {rule_id}")
                continue
            try:
                content = target.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"unreadable rule {rule_id}: {exc}")
                continue
            if _text_hash(content) != metadata.get("sha256"):
                errors.append(f"rule hash mismatch: {rule_id}")
                continue
            rules.append({
                **dict(metadata),
                "rule_id": rule_id,
                "content": content,
                "path": str(target),
            })
    return rules, errors


def render_mining_repair_context(
    repo_root: str | Path,
    project: str,
    *,
    max_bytes: int = 65536,
) -> str:
    if max_bytes < 1024:
        raise ValueError("repair context budget must be at least 1024 bytes")
    rules, errors = load_active_mining_repairs(repo_root, project)
    if not rules and not errors:
        return ""
    lines = [
        "## 已发布挖掘修复",
        "",
        "以下规则来自此前真实运行的红蓝验证。项目规则只适用于当前项目；共享规则也必须在根因和防护条件一致时使用。",
        "先读规则，再读代码；不得只凭规则名称直接确认或排除候选问题。",
        "",
    ]
    for error in errors:
        lines.append(f"- 规则加载失败，已忽略：{error}")
    for rule in rules:
        lines.extend([
            f"### {rule['rule_id']}（{rule['scope']} / {rule['kind']}）",
            f"来源文件：{rule['path']}",
            "",
            str(rule["content"]).strip(),
            "",
        ])
    rendered = "\n".join(lines).strip() + "\n"
    if len(rendered.encode("utf-8")) <= max_bytes:
        return rendered
    compact = lines[:5]
    compact.append("规则内容超过本次提示词预算；按当前类别和根因读取以下来源文件，不得忽略项目专属规则：")
    for rule in rules:
        compact.append(f"- {rule['rule_id']}：`{rule['path']}`（{rule['kind']}）")
    return "\n".join(compact).strip() + "\n"


def run_mining_repair_cycle(
    train_records: Iterable[Mapping[str, Any]],
    baseline_records: Iterable[Mapping[str, Any]],
    candidate_records: Iterable[Mapping[str, Any]],
    *,
    repo_root: str | Path,
    ledger: Mapping[str, Mapping[str, Any]] | None = None,
    holdout_projects: Sequence[str] = (),
    apply_accepted: bool = True,
) -> dict[str, Any]:
    train = list(train_records)
    baseline = list(baseline_records)
    candidate_rows = list(candidate_records)
    proposals = propose_mining_repairs(train, ledger=ledger)
    store = MiningRepairStore(repo_root)
    results = []
    for proposal in proposals:
        evaluation = evaluate_mining_repair(
            proposal,
            baseline,
            candidate_rows,
            holdout_projects=holdout_projects,
        )
        result: dict[str, Any] = {
            "candidate": proposal,
            "evaluation": evaluation,
            "publication": {"status": "not_requested" if apply_accepted else "candidate_only"},
        }
        if apply_accepted and evaluation["accepted"]:
            version = store.apply(proposal, evaluation)
            result["publication"] = {
                "status": "published",
                "version_id": version["version_id"],
                "target": version["target"],
            }
        results.append(result)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "status": "ok" if results else "insufficient",
        "candidates": len(results),
        "accepted": sum(item["evaluation"]["accepted"] for item in results),
        "published": sum(item["publication"]["status"] == "published" for item in results),
        "results": results,
        "train_data_hash": data_hash(train),
        "baseline_data_hash": data_hash(baseline),
        "candidate_data_hash": data_hash(candidate_rows),
    }
