"""从真实请求与读取事件还原阶段二阶梯曲线；无法定位用量保持缺失。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stages"))
from rsi_reward import calculate


def read(file):
    try:
        return json.loads(file.read_text())
    except (OSError, ValueError):
        return {}


def records(file):
    try:
        with file.open(errors="replace") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        yield row
                except ValueError:
                    pass
    except OSError:
        pass


def timeline(repo, project):
    from datetime import datetime

    def timestamp(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError, AttributeError):
            return None

    root = repo / "runs" / project
    runs = []
    for folder in root.iterdir() if root.exists() else []:
        if folder.is_symlink() or not folder.is_dir() or folder.name.endswith(".meta"):
            continue
        summary = read(folder / "task-artifacts/read-coverage/summary.json")
        if summary.get("source_version"):
            events = list(records(folder / "task-artifacts/read-coverage/events.jsonl"))
            valid = [
                e
                for e in events
                if e.get("kind") == "read"
                and e.get("ranges")
                and timestamp(e.get("timestamp")) is not None
            ]
            if valid:
                runs.append(
                    (min(timestamp(e["timestamp"]) for e in valid), folder, summary, events)
                )
    versions = {}
    for _, folder, summary, events in sorted(runs, key=lambda r: (r[0], r[1].name)):
        version = summary["source_version"]
        series = versions.setdefault(
            version,
            {
                "source_version": version,
                "time_points": [],
                "token_points": [],
                "runs": [],
                "seen": {},
                "tokens": 0,
                "lines": 0,
                "weighted_lines": 0,
                "seconds": 0,
                "missing_requests": 0,
                "seen_requests": set(),
            },
        )
        times = {
            e.get("tool_use_id"): timestamp(e.get("timestamp"))
            for e in events
            if timestamp(e.get("timestamp")) is not None and e.get("tool_use_id")
        }
        messages = {}
        # 只读取阶段二主会话，不纳入验证、绘图和审核阶段日志。
        for row in records(folder / "raw.jsonl"):
            msg = row.get("message") or {}
            if row.get("type") != "assistant" or not isinstance(msg, dict) or not msg.get("id"):
                continue
            key = (row.get("session_id"), msg["id"])
            usage = msg.get("usage") or row.get("usage")
            if not isinstance(usage, dict):
                continue
            entry = messages.setdefault(key, {"usage": {}, "time": None})
            entry["usage"].update(usage)
            t = timestamp(row.get("timestamp"))
            ids = [
                x.get("id")
                for x in msg.get("content", [])
                if isinstance(x, dict) and x.get("type") == "tool_use"
            ]
            linked = [times[i] for i in ids if i in times]
            if t is not None:
                entry["time"] = t
            elif linked:
                entry["time"] = min(linked)
        stream = []
        for request_key, message in messages.items():
            if request_key in series["seen_requests"]:
                continue
            series["seen_requests"].add(request_key)
            if message["time"] is None:
                series["missing_requests"] += 1
                continue
            u = message["usage"]
            fields = (
                ["prompt_tokens", "completion_tokens"]
                if "prompt_tokens" in u
                else [
                    "input_tokens",
                    "output_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                ]
            )
            amount = sum(u[k] for k in fields if type(u.get(k)) is int and u[k] >= 0)
            stream.append((message["time"], 0, amount))
        for event in events:
            if (
                event.get("kind") == "read"
                and event.get("file")
                and event.get("ranges")
                and timestamp(event.get("timestamp")) is not None
            ):
                stream.append((timestamp(event["timestamp"]), 1, event))
        if not stream:
            continue
        stream.sort(key=lambda row: (row[0], row[1]))
        start, end = stream[0][0], stream[-1][0]
        jev = read(folder / "triage/jev-infra.json")
        by_path = {}
        for unit in jev.get("units", []):
            by_path.setdefault(unit.get("path"), []).append(unit)
        for t, kind, item in stream:
            if kind == 0:
                series["tokens"] += item
            else:
                result = calculate(
                    {"source_version": version, "files": [item]},
                    {"units": by_path.get(item.get("file"), [])},
                    series["seen"],
                    [],
                )
                if result["new_lines"] == 0:
                    continue
                series["lines"] += result["new_lines"]
                series["weighted_lines"] += result["delta_risk_coverage"]
            point = {
                "seconds": round(series["seconds"] + t - start, 3),
                "tokens": series["tokens"],
                "lines": series["lines"],
                "weighted_lines": round(series["weighted_lines"], 2),
                "run_id": folder.name,
            }
            series["time_points"].append(point)
            series["token_points"].append(point)
        series["seconds"] += max(0, end - start)
        series["runs"].append(
            {"run_id": folder.name, "seconds": series["seconds"], "tokens": series["tokens"]}
        )
    for series in versions.values():
        del series["seen"]
        del series["seen_requests"]
        # 只移除横纵坐标均重复的点，不做平滑或插值。
        for field, axis in [("time_points", "seconds"), ("token_points", "tokens")]:
            out = []
            for p in series[field]:
                if not out or any(p[k] != out[-1][k] for k in [axis, "lines", "weighted_lines"]):
                    out.append(p)
            series[field] = out
    return {
        "series": list(versions.values()),
        "token_basis": "timestamp_or_tool_call_link",
        "time_basis": "recorded_read_events",
    }


if __name__ == "__main__":
    project = sys.argv[2]
    if (
        not project
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for c in project
        )
        or project in {".", ".."}
    ):
        raise ValueError("invalid project")
    print(json.dumps(timeline(Path(sys.argv[1]), project)))
