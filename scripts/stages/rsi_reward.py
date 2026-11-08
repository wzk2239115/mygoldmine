"""宿主机计算并持久化两项 RSI 奖励；不改变漏洞验收。"""

import math
from pathlib import PurePosixPath

VERSION = "rsi-two-signal-v1"
ALPHA = 0.01
BETA = 10.0


def merge(ranges):
    result = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1] + 1:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def subtract(ranges, seen):
    result = []
    for start, end in merge(ranges):
        cursor = start
        for left, right in seen:
            if right < cursor:
                continue
            if left > end:
                break
            if left > cursor:
                result.append([cursor, left - 1])
            cursor = max(cursor, right + 1)
        if cursor <= end:
            result.append([cursor, end])
    return result


def source_path(value):
    if not isinstance(value, str):
        return None
    value = value.removeprefix("./")
    path = PurePosixPath(value)
    return str(path) if value and not path.is_absolute() and ".." not in path.parts else None


def valid_range(start, end):
    return type(start) is int and type(end) is int and 0 < start <= end


def calculate(summary, jev, seen, report_ids, report_available=True, prior=None):
    """seen is host-owned state; repeated calls only credit previously unseen ranges."""
    source_version = summary.get("source_version")
    priorities = {}
    for unit in jev.get("units", []):
        path = source_path(unit.get("path"))
        start, end, p = unit.get("line_start"), unit.get("line_end"), unit.get("priority")
        if path and valid_range(start, end) and type(p) in (int, float) and math.isfinite(p):
            priorities.setdefault(path, []).append((start, end, max(0, min(1, p))))
    observed = {}
    for item in summary.get("files", []):
        path = source_path(item.get("file"))
        if item.get("kind") != "read" or not path:
            continue
        key = str(source_version) + "/" + path + "/" + str(item.get("file_sha256") or "")
        entry = observed.setdefault(key, {"path": path, "ranges": []})
        for row in item.get("ranges", []):
            if valid_range(row.get("start"), row.get("end")):
                entry["ranges"].append([row["start"], row["end"]])
    details = []
    weighted = 0.0
    if source_version:
        for key, item in observed.items():
            novel = subtract(item["ranges"], seen.get(key, []))
            score = 0.0
            for start, end in novel:
                boundaries = {start, end + 1}
                for left, right, _ in priorities.get(item["path"], []):
                    if left <= end and right >= start:
                        boundaries.update((max(start, left), min(end, right) + 1))
                points = sorted(boundaries)
                for left, right in zip(points, points[1:]):
                    priority = max(
                        (p for a, b, p in priorities.get(item["path"], []) if a <= left <= b),
                        default=0,
                    )
                    score += (right - left) * (1 + priority)
            if novel:
                details.append(
                    {
                        "file": item["path"],
                        "ranges": novel,
                        "new_lines": sum(b - a + 1 for a, b in novel),
                        "weighted_lines": round(score, 6),
                    }
                )
            weighted += score
            seen[key] = merge(seen.get(key, []) + item["ranges"])
    previous = prior if prior and prior.get("formula_version") == VERSION else {}
    all_details = previous.get("coverage_details", []) + details
    coverage = round(previous.get("delta_risk_coverage", 0) + weighted, 6)
    reports = sorted(set(previous.get("verified_ids", [])) | set(report_ids))
    notes = []
    if not source_version:
        notes.append("缺少源码版本，新增覆盖暂不计分。")
    if not summary:
        notes.append("读取观测尚未生成。")
    if summary.get("collection_errors"):
        notes.append("读取采集存在异常，覆盖记录不完整。")
    if not priorities:
        notes.append("没有可用的 JEV 行级优先分数，覆盖使用基础权重 1。")
    if not report_available:
        notes.append("验证成果接口暂不可用，漏洞项等待补算。")
    complete = bool(
        summary and source_version and not summary.get("collection_errors") and report_available
    )
    c = round(ALPHA * coverage, 6)
    v = round(BETA * len(reports), 6)
    return {
        "formula_version": VERSION,
        "formula": "R = alpha * delta_risk_coverage + beta * new_verified",
        "alpha": ALPHA,
        "beta": BETA,
        "coverage_unit": "risk_weighted_source_lines",
        "risk_weight": "1 + max(JEV priority); missing priority = 0",
        "status": "complete" if complete else "partial",
        "source_version": source_version,
        "delta_risk_coverage": coverage,
        "new_lines": sum(x["new_lines"] for x in all_details),
        "new_verified": len(reports),
        "coverage_reward": c,
        "vulnerability_reward": v,
        "total": round(c + v, 6),
        "verified_ids": reports,
        "coverage_details": all_details,
        "notes": notes,
        "attribution": "association_only",
    }
