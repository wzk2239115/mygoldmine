#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 基础设施确定性扫描器。

模式：
  rpc            HTTP/gRPC/WebSocket/ZMQ/CLI 入口、绑定地址、认证中间件
  config         Dockerfile/compose/k8s/MCP/agent 配置信任与危险默认值
  serialization  pickle/torch.load/yaml.load/msgpack/bincode/exec 等
  sandbox        agent 审批、沙箱、容器逃逸、路径约束

输出 canonical finding 结构，供 report normalize/dedup/lint 与 verify-agent 使用。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

CODE_EXTS = {
    ".py", ".rs", ".go", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".cu", ".cuh",
    ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".php", ".rb", ".scala", ".cs",
    ".sh", ".bash", ".zsh", ".sol", ".move", ".vy",
}
CONFIG_NAMES = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    ".mcp.json", ".codex/config.toml", ".claude/settings.json", "settings.json",
    "Chart.yaml", "values.yaml", "deployment.yaml", "daemonset.yaml", "statefulset.yaml",
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "requirements.txt", "CMakeLists.txt",
}
SKIP_DIRS = {".git", ".claude", ".workspace", ".agent", ".opencode", "node_modules", "vendor",
             "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode",
             "third_party", "3rdparty", "tests", "test", "examples", "example",
             "docs", "benchmarks", "benchmark", "e2e_test"}

PREFIX = {"rpc": "RPC", "config": "CFG", "serialization": "SER", "sandbox": "SBX"}


def iter_files(root: Path, max_files: int = 6000) -> Iterable[Path]:
    seen = 0
    for p in root.rglob("*"):
        if seen >= max_files:
            break
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() in CODE_EXTS or p.name in CONFIG_NAMES:
            seen += 1
            yield p


def read_text(path: Path, limit: int = 1_500_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def mk_finding(prefix: str, idx: int, title: str, severity: str, confidence: str,
               cwe: str, rel: str, line: int, snippet: str, remediation: str,
               reachability: str = "unknown", source: str = "static") -> Dict:
    return {
        "id": f"{prefix}-{idx:03d}",
        "title": title,
        "type": prefix.lower(),
        "cwe": cwe,
        "severity": severity,
        "confidence": confidence,
        "reachability": reachability,
        "source": source,
        "files": [{"path": rel, "line_start": line, "line_end": line}],
        "evidence": [{"type": "code", "path": rel, "line": line, "snippet": snippet[:240]}],
        "verification": {"status": "unverified", "method": "static", "report": ""},
        "remediation": remediation,
    }


def add(findings: List[Dict], seen: set, prefix: str, rel: str, line: int,
        title: str, severity: str, confidence: str, cwe: str, snippet: str,
        remediation: str, reachability: str = "unknown") -> None:
    key = (prefix, rel, line, title)
    if key in seen:
        return
    seen.add(key)
    findings.append(mk_finding(prefix, len(findings) + 1, title, severity, confidence,
                               cwe, rel, line, snippet, remediation, reachability))


def scan_rpc(root: Path) -> Tuple[List[Dict], List[Dict]]:
    findings: List[Dict] = []
    surface: List[Dict] = []
    seen: set = set()
    route_re = re.compile(r'(?:@\w+\.(?:get|post|put|delete|patch|route)|\.route\(|add_api_route|add_service\(|@(?:Get|Post|Put|Delete|Patch|RequestMapping))')
    sensitive_re = re.compile(r'(server_info|get_server_info|update_weights|workers|invocations|tokenize|debug|metrics|admin|config|reload|shutdown|health)', re.I)
    auth_re = re.compile(r'(api[_-]?key|authorization|auth[_-]?middleware|interceptor|tower::layer|Depends\(|AuthenticationMiddleware|require_auth|verify_token)', re.I)
    bind_all_re = re.compile(r'0\.0\.0\.0|--host\s+0\.0\.0\.0|host\s*=\s*["\']0\.0\.0\.0')
    zmq_re = re.compile(r'(zmq|ZMQ|ROUTER|PUB|SUB|tcp://\*)', re.I)
    grpc_re = re.compile(r'(grpc\.server|tonic::transport|add_service\(|grpc\.NewServer)', re.I)
    ws_re = re.compile(r'(websocket|WebSocket|ws://|wss://)', re.I)

    for p in iter_files(root):
        text = read_text(p)
        if not text:
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        lines = text.splitlines()
        has_auth = bool(auth_re.search(text))
        for lineno, line in enumerate(lines, 1):
            if route_re.search(line):
                surface.append({"kind": "http-route", "file": rel, "line": lineno, "auth_seen": has_auth})
                if sensitive_re.search(line):
                    add(findings, seen, "RPC", rel, lineno,
                        "敏感/管理端点暴露（需确认认证）", "high", "medium", "CWE-306",
                        line.strip(), "为管理/敏感端点增加独立认证与网络访问控制。",
                        "default" if not has_auth else "opt-in")
            if bind_all_re.search(line):
                add(findings, seen, "RPC", rel, lineno,
                    "服务绑定所有网卡", "medium", "medium", "CWE-668",
                    line.strip(), "默认绑定 127.0.0.1，或在文档/启动脚本中强制认证。",
                    "default" if not has_auth else "opt-in")
            if zmq_re.search(line):
                surface.append({"kind": "ipc-zmq", "file": rel, "line": lineno, "auth_seen": has_auth})
                if "tcp://*" in line or bind_all_re.search(line):
                    add(findings, seen, "RPC", rel, lineno,
                        "ZMQ/IPC 监听所有网卡", "high", "medium", "CWE-306",
                        line.strip(), "限制 ZMQ 绑定到回环/受信网络，并增加消息认证。", "default")
            if grpc_re.search(line):
                surface.append({"kind": "grpc", "file": rel, "line": lineno, "auth_seen": has_auth})
                if not has_auth and ("Server::builder" in line or "grpc.NewServer" in line or "add_service" in line):
                    add(findings, seen, "RPC", rel, lineno,
                        "gRPC 服务未发现认证拦截器", "high", "medium", "CWE-306",
                        line.strip(), "为 gRPC 服务添加认证 interceptor / middleware。", "default")
            if ws_re.search(line):
                surface.append({"kind": "websocket", "file": rel, "line": lineno, "auth_seen": has_auth})
                if not has_auth:
                    add(findings, seen, "RPC", rel, lineno,
                        "WebSocket 入口未发现认证", "medium", "low", "CWE-306",
                        line.strip(), "在 WebSocket 握手阶段增加身份校验与来源限制。", "unknown")
    return findings, surface


def scan_config(root: Path) -> Tuple[List[Dict], List[Dict]]:
    findings: List[Dict] = []
    positive: List[Dict] = []
    seen: set = set()
    rules = [
        (re.compile(r'^\s*USER\s+root\b', re.I), "容器以 root 运行", "medium", "CWE-250",
         "改为非 root 用户运行。", "default"),
        (re.compile(r'--privileged\b|privileged:\s*true', re.I), "容器启用 privileged", "high", "CWE-250",
         "移除 privileged，按需添加最小 capability。", "default"),
        (re.compile(r'/var/run/docker\.sock', re.I), "挂载 Docker socket", "high", "CWE-250",
         "不要让不可信代码访问 docker.sock；使用独立 runner。", "default"),
        (re.compile(r'network_mode:\s*host|--network\s+host|hostNetwork:\s*true', re.I),
         "容器使用 host 网络", "medium", "CWE-668", "使用 bridge/受限网络并显式放行依赖。", "default"),
        (re.compile(r'hostPath:', re.I), "K8s 使用 hostPath", "medium", "CWE-668",
         "改用 PVC/只读挂载并限制路径。", "default"),
        (re.compile(r'runAsUser:\s*0|allowPrivilegeEscalation:\s*true', re.I),
         "K8s 允许 root / 提权", "high", "CWE-250", "设置 runAsNonRoot 并关闭提权。", "default"),
        (re.compile(r'(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[A-Za-z0-9_\-\.]{12,}', re.I),
         "配置文件疑似明文凭据", "high", "CWE-798", "改用环境变量/密钥管理，轮换已泄露密钥。", "default"),
        (re.compile(r'allow_origins\s*=\s*\[\s*["\']\*', re.I), "CORS 允许任意来源", "medium", "CWE-942",
         "改为显式来源白名单。", "default"),
        (re.compile(r'verify\s*=\s*False|rejectUnauthorized\s*:\s*false', re.I), "关闭 TLS 校验", "medium", "CWE-295",
         "启用证书校验或显式受信 CA。", "default"),
        (re.compile(r'DEBUG\s*[:=]\s*(True|true|1)', re.I), "调试模式默认开启", "medium", "CWE-489",
         "生产默认关闭 DEBUG。", "default"),
    ]
    agent_rules = [
        (re.compile(r'bypassPermissions|dangerously-skip-permissions|--no-sandbox', re.I),
         "Agent 关闭权限/沙箱确认", "high", "CWE-693", "默认开启审批与沙箱，仅显式 opt-in 关闭。", "default"),
        (re.compile(r'approval_policy\s*[:=]\s*["\']?(never|off|none)', re.I),
         "Agent 审批策略为 never", "high", "CWE-693", "默认要求审批，危险命令逐条确认。", "default"),
        (re.compile(r'sandbox\s*[:=]\s*(false|off|none)', re.I), "Agent 沙箱关闭", "high", "CWE-693",
         "默认启用沙箱；关闭需显式风险提示。", "default"),
        (re.compile(r'auto[_-]?approve|allow_prefix|allowed_tools', re.I), "Agent 自动批准/工具白名单过宽",
         "medium", "CWE-693", "收窄工具白名单，危险工具单独审批。", "unknown"),
        (re.compile(r'"command"\s*:\s*"[^"]+"\s*,\s*"args"', re.I), "MCP 配置包含可执行命令",
         "medium", "CWE-78", "校验 MCP server 来源，固定版本/命令白名单。", "default"),
    ]
    for p in iter_files(root):
        text = read_text(p)
        if not text:
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        is_agent_cfg = p.name in (".mcp.json", "settings.json") or ".codex" in str(p) or ".claude" in str(p)
        for lineno, line in enumerate(text.splitlines(), 1):
            for rx, title, sev, cwe, fix, reach in rules:
                if rx.search(line):
                    add(findings, seen, "CFG", rel, lineno, title, sev, "medium", cwe,
                        line.strip(), fix, reach)
            if is_agent_cfg:
                for rx, title, sev, cwe, fix, reach in agent_rules:
                    if rx.search(line):
                        add(findings, seen, "CFG", rel, lineno, title, sev, "medium", cwe,
                            line.strip(), fix, reach)
            if re.search(r'USER\s+(?!root)\w+|runAsNonRoot:\s*true|readOnlyRootFilesystem:\s*true', line, re.I):
                positive.append({"kind": "hardening", "file": rel, "line": lineno, "evidence": line.strip()[:160]})
    return findings, positive


def scan_serialization(root: Path) -> Tuple[List[Dict], List[Dict]]:
    findings: List[Dict] = []
    surface: List[Dict] = []
    seen: set = set()
    rules = [
        (re.compile(r'pickle\.loads?\s*\('), "pickle 反序列化", "high", "CWE-502",
         "改用 JSON/安全格式；必须使用时加签名与 allowlist。"),
        (re.compile(r'torch\.load\s*\('), "torch.load 反序列化", "high", "CWE-502",
         "使用 weights_only=True；不要加载不可信 checkpoint。"),
        (re.compile(r'dill\.loads?\s*\('), "dill 反序列化", "high", "CWE-502",
         "避免加载不可信 dill 数据。"),
        (re.compile(r'joblib\.load\s*\('), "joblib 反序列化", "high", "CWE-502",
         "只加载受信模型文件并校验哈希。"),
        (re.compile(r'yaml\.load\s*\((?![^)]*SafeLoader)'), "yaml.load 未使用 SafeLoader", "medium", "CWE-502",
         "改用 yaml.safe_load。"),
        (re.compile(r'msgpack\.unpackb|rmp_serde::from_slice|postcard::from_bytes|bincode::deserialize'),
         "二进制反序列化入口", "medium", "CWE-502", "校验长度/类型并限制消息来源。"),
        (re.compile(r'\bexec\s*\(|\beval\s*\('), "动态代码执行", "high", "CWE-95",
         "移除 eval/exec；必须使用时加沙箱与输入白名单。"),
        (re.compile(r'os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True', re.I),
         "shell 命令执行", "high", "CWE-78", "使用参数列表并避免 shell=True。"),
        (re.compile(r'trust_remote_code\s*=\s*True'), "transformers 信任远程代码", "high", "CWE-502",
         "默认 False；只对受信模型显式开启。"),
        (re.compile(r'from_pretrained\s*\('), "模型加载入口", "medium", "CWE-502",
         "限制模型来源并锁定 revision。"),
        (re.compile(r'from_pretrained\s*\([^)]*trust_remote_code\s*=\s*True', re.S),
         "from_pretrained + trust_remote_code=True", "high", "CWE-502",
         "锁定 revision，校验模型文件，默认关闭远程代码。"),
        (re.compile(r'zmq|ray\.init|nccl|shared_memory|multiprocessing\.Queue', re.I),
         "IPC/分布式消息入口", "medium", "CWE-502", "校验消息来源与序列化格式。"),
        (re.compile(r'load_format|model_path|update_weights', re.I),
         "权重/模型路径入口", "medium", "CWE-22", "限制路径到受信根目录并校验来源。"),
    ]
    for p in iter_files(root):
        text = read_text(p)
        if not text:
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for rx, title, sev, cwe, fix in rules:
                if not rx.search(line):
                    continue
                if "torch.load" in line and "weights_only=True" in line:
                    continue
                if "yaml.load" in line and "SafeLoader" in line:
                    continue
                add(findings, seen, "SER", rel, lineno, title, sev, "medium", cwe,
                    line.strip(), fix, "unknown")
                if "from_pretrained" in line or "torch.load" in line or "pickle" in line:
                    surface.append({"kind": "model-load", "file": rel, "line": lineno})
    return findings, surface


def scan_sandbox(root: Path) -> Tuple[List[Dict], List[Dict]]:
    findings: List[Dict] = []
    positive: List[Dict] = []
    seen: set = set()
    rules = [
        (re.compile(r'bypassPermissions|dangerously-skip-permissions|--no-sandbox', re.I),
         "关闭 agent 权限/沙箱", "high", "CWE-693", "默认开启审批与沙箱。"),
        (re.compile(r'approval_policy\s*[:=]\s*["\']?(never|off|none)', re.I),
         "审批策略 never", "high", "CWE-693", "危险命令逐条审批。"),
        (re.compile(r'sandbox\s*[:=]\s*(false|off|none)', re.I), "沙箱关闭", "high", "CWE-693",
         "默认启用沙箱。"),
        (re.compile(r'--privileged\b|privileged:\s*true|CAP_SYS_ADMIN|seccomp\s*=\s*unconfined|apparmor\s*=\s*unconfined', re.I),
         "容器隔离被削弱", "high", "CWE-250", "移除 privileged/CAP_SYS_ADMIN，启用 seccomp/apparmor。"),
        (re.compile(r'/var/run/docker\.sock', re.I), "Docker socket 暴露", "high", "CWE-250",
         "不要向不可信代码暴露 docker.sock。"),
        (re.compile(r'hostPath:|hostNetwork:\s*true|runAsUser:\s*0', re.I), "宿主路径/网络/root 风险",
         "medium", "CWE-250", "使用最小权限与只读挂载。"),
        (re.compile(r'os\.path\.join|Path\([^)]*\)|resolve\(\)', re.I), "路径拼接/解析点（需检查边界）",
         "low", "CWE-22", "realpath 后校验必须位于受信根目录。"),
    ]
    for p in iter_files(root):
        text = read_text(p)
        if not text:
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for rx, title, sev, cwe, fix in rules:
                if rx.search(line):
                    add(findings, seen, "SBX", rel, lineno, title, sev, "low", cwe,
                        line.strip(), fix, "unknown")
            if re.search(r'seccomp|landlock|runAsNonRoot:\s*true|readOnlyRootFilesystem:\s*true', line, re.I):
                positive.append({"kind": "sandbox-hardening", "file": rel, "line": lineno,
                                 "evidence": line.strip()[:160]})
    return findings, positive


def render_md(mode: str, root: Path, findings: List[Dict], extras: List[Dict]) -> str:
    names = {
        "rpc": "RPC / 入口面",
        "config": "配置信任",
        "serialization": "反序列化 / 代码执行",
        "sandbox": "沙箱 / 容器边界",
    }
    lines = [f"# {names.get(mode, mode)}扫描结果", "", f"- 源码: `{root}`",
             f"- 生成时间: {datetime.now(timezone.utc).isoformat()}",
             f"- Findings: {len(findings)}", ""]
    if not findings:
        lines.append("未发现匹配项（不代表安全，需结合 LLM 分析）。")
    for f in findings:
        loc = f["files"][0]
        lines += [f"## {f['id']} · {f['title']}", "",
                  f"- 严重度: **{f['severity']}**  置信度: {f['confidence']}  "
                  f"可达性: {f['reachability']}  {f['cwe']}",
                  f"- 位置: `{loc['path']}:{loc['line_start']}`",
                  f"- 证据: `{f['evidence'][0]['snippet']}`",
                  f"- 修复: {f['remediation']}", ""]
    if extras:
        lines += ["## Surface / Positive controls", ""]
        for e in extras[:50]:
            lines.append(f"- {e}")
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 基础设施确定性扫描器")
    parser.add_argument("mode", choices=["rpc", "config", "serialization", "sandbox", "all"])
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--output", "-o", default="", help="输出 .md；同名 .json 会一起写")
    parser.add_argument("--task-id", default="", help="任务 ID，用于默认输出路径")
    parser.add_argument("--json", action="store_true", help="只打印 JSON")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"路径不存在: {root}", file=sys.stderr)
        return 2

    modes = ["rpc", "config", "serialization", "sandbox"] if args.mode == "all" else [args.mode]
    all_findings: List[Dict] = []
    extras: List[Dict] = []
    stats = {}
    for mode in modes:
        if mode == "rpc":
            finds, extra = scan_rpc(root)
        elif mode == "config":
            finds, extra = scan_config(root)
        elif mode == "serialization":
            finds, extra = scan_serialization(root)
        else:
            finds, extra = scan_sandbox(root)
        all_findings.extend(finds)
        extras.extend(extra)
        stats[mode] = len(finds)

    payload = {
        "scanner": f"{args.mode}-scanner",
        "mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(root),
        "stats": {"findings": len(all_findings), "by_mode": stats},
        "surface": [e for e in extras if e.get("kind") not in ("hardening", "sandbox-hardening")],
        "positive_controls": [e for e in extras if e.get("kind") in ("hardening", "sandbox-hardening")],
        "findings": all_findings,
    }

    if not args.output and args.task_id:
        args.output = f".workspace/tasks/{args.task_id}/{args.mode}.md"

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    md = render_md(args.mode, root, all_findings, extras)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md + "\n", encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
