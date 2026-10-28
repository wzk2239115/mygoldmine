#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "via",
    "using", "from", "by", "is", "are", "when", "that", "this", "as", "at", "into",
    "allows", "allow", "potential", "possible", "can", "could", "may", "be", "not",
    "no", "without", "through", "across", "after", "before", "during", "all", "any",
    "its", "it", "their", "they", "has", "have", "had", "was", "were", "will",
}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}


def now():
    return datetime.now(timezone.utc).isoformat()


def norm_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def tokens(value):
    return {token for token in norm_text(value).split() if len(token) > 2 and token not in STOPWORDS}


def jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def severity(value):
    raw = str(value or "unknown").lower().split()[0]
    return raw if raw in SEVERITY_ORDER else "unknown"


def cwe_set(finding):
    raw = finding.get("cwe") or finding.get("cwe_id") or []
    if isinstance(raw, str):
        raw = re.split(r"[,; ]+", raw)
    return {str(item).strip().upper() for item in raw if str(item).strip()}


def path_keys(finding):
    values = []
    for key in ("evidence", "files", "location"):
        value = finding.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    keys = set()
    for item in values:
        if isinstance(item, dict):
            item = item.get("path") or item.get("file") or item.get("location") or ""
        text = str(item).split(":")[0].replace("\\", "/").lower().strip("/")
        if not text:
            continue
        parts = [part for part in text.split("/") if part]
        if parts:
            keys.add("/".join(parts[-3:]))
    return keys


def finding_record(finding, run_id, run_dir):
    title = str(finding.get("title") or finding.get("description") or finding.get("type") or finding.get("category") or "").strip()
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "id": str(finding.get("id") or ""),
        "title": title,
        "severity": severity(finding.get("severity") or finding.get("severity_raw")),
        "category": str(finding.get("category") or finding.get("type") or "").strip(),
        "cwe": sorted(cwe_set(finding)),
        "paths": sorted(path_keys(finding)),
        "root_cause": str(finding.get("root_cause") or finding.get("description") or "").strip(),
        "tokens": tokens(f"{title} {finding.get('root_cause', '')}"),
        "file_keys": path_keys(finding),
    }


def similarity(left, right):
    title_score = jaccard(left["tokens"], right["tokens"])
    paths = left["file_keys"] & right["file_keys"]
    path_score = 1.0 if paths else 0.0
    if not path_score:
        left_names = {path.rsplit("/", 1)[-1] for path in left["file_keys"]}
        right_names = {path.rsplit("/", 1)[-1] for path in right["file_keys"]}
        path_score = 0.85 if left_names & right_names else 0.0
    cwe_score = jaccard(set(left["cwe"]), set(right["cwe"]))
    cat_score = 1.0 if left["category"] and left["category"].lower() == right["category"].lower() else 0.0
    score = 0.55 * title_score + 0.30 * path_score + 0.10 * cwe_score + 0.05 * cat_score
    if path_score >= 0.85 and title_score >= 0.10:
        score = max(score, 0.46)
    if path_score == 1.0 and title_score >= 0.25:
        score = max(score, 0.56)
    if title_score >= 0.70:
        score = max(score, 0.62)
    return score


def load_runs(runs_root, project, include_incomplete=False):
    runs = []
    project_dir = Path(runs_root) / project
    if not project_dir.is_dir():
        return runs
    for run_dir in sorted(project_dir.iterdir()):
        report_path = run_dir / "audit-report.json"
        if not report_path.exists():
            continue
        meta_path = run_dir / "run-meta.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        if not include_incomplete and meta:
            if meta.get("timed_out") or meta.get("interrupted"):
                continue
            if meta.get("exit_code") not in (0, None):
                continue
            if meta.get("reports_complete") is False:
                continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        findings = report.get("findings") or report.get("vulnerabilities") or []
        run_id = f"{project}/{run_dir.name}"
        records = [finding_record(finding, run_id, run_dir) for finding in findings]
        runs.append({"run_id": run_id, "run_dir": str(run_dir), "findings": records})
    return runs


def cluster_project(project, runs, min_rounds):
    clusters = []
    for run in runs:
        for finding in run["findings"]:
            best = None
            best_score = 0.0
            for cluster in clusters:
                score = max((similarity(finding, existing) for existing in cluster["variants"]), default=0.0)
                if score > best_score:
                    best = cluster
                    best_score = score
            if best is not None and best_score >= 0.46:
                best["variants"].append(finding)
                best["runs"].add(finding["run_id"])
            else:
                clusters.append({"variants": [finding], "runs": {finding["run_id"]}})
    results = []
    for cluster in clusters:
        variants = cluster["variants"]
        best = max(variants, key=lambda item: (len(item["title"]), -SEVERITY_ORDER.get(item["severity"], 9)))
        sev = min((item["severity"] for item in variants), key=lambda item: SEVERITY_ORDER.get(item, 9))
        rounds_seen = len(cluster["runs"])
        results.append(
            {
                "title": best["title"],
                "severity": sev,
                "rounds_seen": rounds_seen,
                "rounds_total": len(runs),
                "stable": rounds_seen >= min_rounds,
                "paths": sorted({path for item in variants for path in item["paths"]}),
                "cwe": sorted({cwe for item in variants for cwe in item["cwe"]}),
                "variants": [
                    {
                        "run_id": item["run_id"],
                        "id": item["id"],
                        "title": item["title"],
                        "severity": item["severity"],
                    }
                    for item in variants
                ],
            }
        )
    results.sort(key=lambda item: (not item["stable"], SEVERITY_ORDER.get(item["severity"], 9), -item["rounds_seen"], item["title"]))
    return results


def parse_projects(text, runs_root):
    if text:
        return [item.strip() for item in text.split(",") if item.strip()]
    return sorted(
        item.name
        for item in Path(runs_root).iterdir()
        if item.is_dir() and not item.name.startswith(".") and (item / "").exists()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--projects", default="")
    parser.add_argument("--min-rounds", type=int, default=2)
    parser.add_argument("--out", default="rsi/consensus")
    parser.add_argument("--markdown", default="docs/rsi-consensus.md")
    parser.add_argument("--include-incomplete", action="store_true")
    args = parser.parse_args()

    projects = parse_projects(args.projects, args.runs_root)
    payload = {"generated_at": now(), "min_rounds": args.min_rounds, "projects": {}}
    lines = [
        "# RSI 多轮一致性结果",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 最少轮次：{args.min_rounds}",
        "- 只列出在多个独立 run 中重复出现的高/严重 finding；单轮 finding 不进入人工研判优先队列。",
        "",
    ]
    for project in projects:
        runs = load_runs(args.runs_root, project, args.include_incomplete)
        if not runs:
            continue
        clusters = cluster_project(project, runs, args.min_rounds)
        stable = [item for item in clusters if item["stable"]]
        high_stable = [item for item in stable if item["severity"] in ("critical", "high")]
        payload["projects"][project] = {
            "runs": [run["run_id"] for run in runs],
            "findings_total": sum(len(run["findings"]) for run in runs),
            "clusters_total": len(clusters),
            "stable_total": len(stable),
            "high_stable_total": len(high_stable),
            "clusters": clusters,
        }
        lines.append(f"## {project}")
        lines.append("")
        lines.append(f"- runs: {len(runs)}")
        lines.append(f"- findings: {sum(len(run['findings']) for run in runs)}")
        lines.append(f"- 稳定簇：{len(stable)}（High/Critical {len(high_stable)}）")
        lines.append("")
        if not high_stable:
            lines.append("- 暂无多轮重复的 High/Critical。")
            lines.append("")
            continue
        for index, item in enumerate(high_stable, 1):
            lines.append(f"{index}. **{item['severity'].upper()} · {item['rounds_seen']}/{item['rounds_total']} 轮** — {item['title']}")
            if item["cwe"]:
                lines.append(f"   - CWE: `{', '.join(item['cwe'])}`")
            if item["paths"]:
                lines.append(f"   - Evidence: `{'; '.join(item['paths'][:3])}`")
            lines.append(f"   - IDs: {', '.join(variant['id'] for variant in item['variants'])}")
        lines.append("")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "consensus.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"projects": len(payload["projects"]), "out": str(out / "consensus.json"), "markdown": args.markdown}, ensure_ascii=False))


if __name__ == "__main__":
    main()
