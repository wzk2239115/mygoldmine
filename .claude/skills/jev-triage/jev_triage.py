#!/usr/bin/env python3
"""Fast file/block triage with a SystemOne decision model."""

from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_ENDPOINT = "https://api.360.cn/v1/systemone"
DEFAULT_MODEL = "typesafe/jev-latest"
DEFAULT_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala", ".rb", ".php",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs", ".swift",
    ".sh", ".bash", ".zsh", ".ps1", ".lua", ".pl", ".r",
    ".sol", ".move", ".vy", ".sql", ".proto", ".graphql", ".gql",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".json",
    ".md", ".txt", ".rst", ".tf", ".hcl", ".dockerfile",
}

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "target", "out", "coverage", "vendor",
    ".venv", "venv", "env", ".tox", ".next", ".nuxt", ".cache",
    "runs", "logs", ".workspace",
}

SENSITIVE_GLOBS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks",
    "*.keystore", "id_rsa*", "id_ed25519*", "id_ecdsa*",
    "credentials*", "secrets*", ".npmrc", ".pypirc", ".netrc",
    "auth.json", "*.sqlite", "*.sqlite3", "*.db",
)

SAFE_ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template"}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]{16,}"),
    re.compile(
        r"(?i)((?:password|passwd|secret|token|api[_-]?key|authorization)"
        r"\s*[:=]\s*['\"])([^'\"]{8,})(['\"])"
    ),
)

RETRY_CODES = {429, 500, 502, 503, 504}

PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "infra": {
        "control_plane": {
            "type": "noul",
            "instructions": "This code registers or handles an HTTP or gRPC control-plane endpoint such as worker registration, model management, admin, health, or status.",
        },
        "auth_boundary": {
            "type": "noul",
            "instructions": "This code implements or wires authentication or authorization for an HTTP or gRPC endpoint.",
        },
        "untrusted_model_input": {
            "type": "noul",
            "instructions": "This code loads a model, adapter, checkpoint, or configuration path from client input, request data, or repository-controlled files.",
        },
        "path_allowlist": {
            "type": "noul",
            "positive": False,
            "instructions": "This code enforces a directory or path allowlist before loading a local model, adapter, or file path.",
        },
        "subprocess_exec": {
            "type": "noul",
            "instructions": "This code executes a subprocess, shell command, or external binary.",
        },
        "deserialization": {
            "type": "noul",
            "instructions": "This code deserializes untrusted data, such as pickle, torch.load without weights_only, or unsafe YAML load.",
        },
        "outbound_url": {
            "type": "noul",
            "instructions": "This code makes an outbound HTTP or gRPC request to a URL or host that comes from client or repository input.",
        },
        "default_exposure": {
            "type": "noul",
            "instructions": "This code makes a security-relevant endpoint or feature reachable by default, for example no authentication, bind to all interfaces, or fail-open behavior.",
        },
    },
    "auth": {
        "auth_check": {
            "type": "noul",
            "instructions": "This code implements or wires authentication or authorization checks such as API keys, tokens, cookies, roles, or permissions.",
        },
        "unauthenticated_route": {
            "type": "noul",
            "instructions": "This code registers an HTTP route that can be reached without authentication.",
        },
        "client_identity": {
            "type": "noul",
            "instructions": "This code trusts a client-supplied identity, role, tenant, or permission value.",
        },
        "fail_open": {
            "type": "noul",
            "instructions": "This code has fail-open behavior or a security-relevant default that weakens authentication.",
        },
        "inference_capability": {
            "type": "noul",
            "instructions": "This code exposes model inference, tokenization, scoring, or embedding capability over HTTP.",
        },
    },
    "input-sink": {
        "attacker_input": {
            "type": "noul",
            "instructions": "This code reads input controlled by a remote client, repository content, environment variables, or command-line users.",
        },
        "dangerous_sink": {
            "type": "noul",
            "instructions": "This code reaches a dangerous sink such as shell execution, eval, unsafe deserialization, SQL, file write, or server-side HTTP request.",
        },
        "validation": {
            "type": "noul",
            "positive": False,
            "instructions": "This code applies an allowlist, canonicalization, or strict validation before the dangerous sink.",
        },
        "reachable": {
            "type": "noul",
            "instructions": "This code is reachable from an external request handler rather than only tests or admin scripts.",
        },
        "risk": {
            "type": "score",
            "instructions": "How security-sensitive is the data flow in this code?",
            "criteria": ["Low", "Medium", "High", "Critical"],
        },
    },
    "config-trust": {
        "repo_config": {
            "type": "noul",
            "instructions": "This code loads project-local configuration such as .env, .git/config, .mcp.json, AGENTS.md, or .claude/settings.json.",
        },
        "auto_load": {
            "type": "noul",
            "instructions": "This code loads project-local configuration automatically when a repository is opened.",
        },
        "subprocess": {
            "type": "noul",
            "instructions": "This code executes a subprocess, shell command, hook, filter, or Git command.",
        },
        "no_confirmation": {
            "type": "noul",
            "instructions": "This code applies repository-controlled configuration without an explicit user confirmation.",
        },
    },
    "lora-model": {
        "client_controlled_path": {
            "type": "noul",
            "instructions": "This code resolves a model, adapter, checkpoint, or LoRA path from client or request input.",
        },
        "path_allowlist": {
            "type": "noul",
            "positive": False,
            "instructions": "This code enforces a directory or path allowlist before loading a local model or adapter.",
        },
        "weight_deserialization": {
            "type": "noul",
            "instructions": "This code loads weights with a risky deserializer such as torch.load without weights_only or pickle.",
        },
        "adapter_resolver": {
            "type": "noul",
            "instructions": "This code resolves adapter names into filesystem paths or downloads them from a model hub.",
        },
    },
    "secrets": {
        "hardcoded_secret": {
            "type": "noul",
            "instructions": "This code contains a hardcoded credential, API key, token, or private key.",
        },
        "secret_logging": {
            "type": "noul",
            "instructions": "This code logs, returns, or serializes a credential or other sensitive value.",
        },
        "secret_in_url": {
            "type": "noul",
            "instructions": "This code places a credential in a URL, query string, or command line.",
        },
    },
}


@dataclass(frozen=True)
class Unit:
    id: str
    path: str
    line_start: int
    line_end: int
    text: str


def redact(text: str) -> str:
    text = SECRET_PATTERNS[0].sub("sk-***", text)
    text = SECRET_PATTERNS[1].sub("AKIA***", text)
    text = SECRET_PATTERNS[2].sub(r"\1***", text)
    text = SECRET_PATTERNS[3].sub(r"\1***\3", text)
    return text


def is_sensitive(rel: str) -> bool:
    name = Path(rel).name.lower()
    if name in SAFE_ENV_EXAMPLES:
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in SENSITIVE_GLOBS)


def is_test(rel: str) -> bool:
    lower = rel.lower()
    return (
        "/test/" in lower
        or "/tests/" in lower
        or "__tests__" in lower
        or lower.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    )


def resolve_api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    for env in (
        "JEV_API_KEY",
        "THREE60_API_KEY",
        "OPENCODE_360_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "GLM_API_KEY",
    ):
        if os.environ.get(env):
            return os.environ[env]
    config = Path(os.environ.get("OPENCODE_CONFIG", DEFAULT_CONFIG))
    if config.exists():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            key = (
                data.get("provider", {})
                .get("360-proxy", {})
                .get("options", {})
                .get("apiKey")
            )
            if key:
                return str(key)
        except (OSError, json.JSONDecodeError):
            pass
    raise SystemExit(
        "missing 360 API key: set JEV_API_KEY or configure opencode 360-proxy"
    )


def split_blocks(
    rel: str, text: str, block_lines: int, max_chars: int
) -> Iterable[Unit]:
    if not text.strip():
        return
    if block_lines > 0:
        lines = text.splitlines()
        for start in range(0, len(lines), block_lines):
            end = min(start + block_lines, len(lines))
            chunk = "\n".join(lines[start:end])[:max_chars]
            if not chunk.strip():
                continue
            yield Unit(f"{rel}#L{start + 1}-{end}", rel, start + 1, end, chunk)
        return
    if len(text) <= max_chars:
        yield Unit(rel, rel, 1, text.count("\n") + 1, text)
        return
    lines = text.splitlines(keepends=True)
    chunk: list[str] = []
    chunk_start = 1
    chunk_size = 0
    for number, line in enumerate(lines, 1):
        if chunk and chunk_size + len(line) > max_chars:
            yield Unit(
                f"{rel}#L{chunk_start}-{number - 1}",
                rel,
                chunk_start,
                number - 1,
                "".join(chunk),
            )
            chunk = []
            chunk_start = number
            chunk_size = 0
        chunk.append(line)
        chunk_size += len(line)
    if chunk:
        yield Unit(
            f"{rel}#L{chunk_start}-{len(lines)}",
            rel,
            chunk_start,
            len(lines),
            "".join(chunk),
        )


def allowed_path(path: Path, root: Path, args: argparse.Namespace) -> bool:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return False
    if any(part in SKIP_DIRS for part in Path(rel).parts):
        return False
    if args.exclude and any(
        fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(path.name, pat)
        for pat in args.exclude
    ):
        return False
    if args.exclude_tests and is_test(rel):
        return False
    if not args.allow_sensitive and is_sensitive(rel):
        return False
    return True


def collect_paths(root: Path, args: argparse.Namespace) -> list[Path]:
    if args.paths_from:
        paths: list[Path] = []
        for line in Path(args.paths_from).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = Path(line)
            if not path.is_absolute():
                path = root / path
            try:
                path = path.resolve()
                path.relative_to(root)
            except (OSError, ValueError):
                continue
            paths.append(path)
        return paths
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in SKIP_DIRS and not name.startswith(".git")
        )
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if args.glob:
                if not any(
                    fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat)
                    for pat in args.glob
                ):
                    continue
            elif path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            paths.append(path)
    return paths


def iter_units(root: Path, args: argparse.Namespace) -> Iterable[Unit]:
    count = 0
    for path in collect_paths(root, args):
        if not allowed_path(path, root, args):
            continue
        try:
            stat = path.stat()
            if stat.st_size <= 0 or stat.st_size > args.max_file_bytes:
                continue
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for unit in split_blocks(rel, redact(raw), args.block_lines, args.max_chars):
            yield unit
            count += 1
            if count >= args.max_files:
                return


def resolve_profile(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    if args.profile != "custom":
        return {key: dict(value) for key, value in PROFILES[args.profile].items()}
    questions: dict[str, dict[str, Any]] = {}
    for spec in args.question:
        key, instruction = spec.split("=", 1)
        questions[key] = {"type": "noul", "instructions": instruction}
    for spec in args.choice:
        key, rest = spec.split("=", 1)
        instruction, options = rest.rsplit("=", 1)
        questions[key] = {
            "type": "choice",
            "instructions": instruction,
            "criteria": {option: option for option in options.split(",") if option},
        }
    for spec in args.score:
        key, rest = spec.split("=", 1)
        instruction, levels = rest.rsplit("=", 1)
        questions[key] = {
            "type": "score",
            "instructions": instruction,
            "criteria": [level for level in levels.split(",") if level],
        }
    if not questions:
        raise SystemExit("custom profile requires --question/--choice/--score")
    return questions


def build_requests(
    units: list[Unit],
    profile: dict[str, dict[str, Any]],
    batch_size: int,
) -> Iterable[tuple[list[Unit], str, dict[str, dict[str, Any]], bool]]:
    if batch_size <= 1:
        for unit in units:
            yield [unit], f"FILE: {unit.id}\n\n{unit.text}", profile, False
        return
    for index in range(0, len(units), batch_size):
        group = units[index : index + batch_size]
        state = "\n\n".join(
            f"### UNIT {i}: {unit.id}\n{unit.text}"
            for i, unit in enumerate(group, 1)
        )
        questions: dict[str, dict[str, Any]] = {}
        for i, unit in enumerate(group, 1):
            for key, question in profile.items():
                item = dict(question)
                item["instructions"] = (
                    f"For UNIT {i} ({unit.id}): {question['instructions']}"
                )
                questions[f"u{i}_{key}"] = item
        yield group, state, questions, True


class SystemOneClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        timeout: int,
        retries: int,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def ask(
        self, state: str, questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        body = json.dumps(
            {"model": self.model, "state": state, "questions": questions}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last = ""
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}"
                if exc.code in RETRY_CODES and attempt < self.retries:
                    time.sleep(min(20, 2 ** attempt))
                    continue
                raise RuntimeError(last) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = repr(exc)
                if attempt < self.retries:
                    time.sleep(min(20, 2 ** attempt))
                    continue
                raise RuntimeError(last) from exc
        raise RuntimeError(last or "request failed")


class Cache:
    def __init__(self, path: Path, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {}
        if enabled and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.data = {}

    def key(
        self, model: str, profile: str, group: list[Unit]
    ) -> str:
        digest = hashlib.sha256()
        digest.update(model.encode())
        digest.update(b"\0")
        digest.update(profile.encode())
        for unit in group:
            digest.update(b"\0")
            digest.update(unit.id.encode())
            digest.update(b"\0")
            digest.update(unit.text.encode())
        return digest.hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        with self.lock:
            return self.data.get(key)

    def put(self, key: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        with self.lock:
            self.data[key] = value

    def flush(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with self.lock:
            temporary.write_text(
                json.dumps(self.data, ensure_ascii=False), encoding="utf-8"
            )
        temporary.replace(self.path)


def score_answers(
    answers: dict[str, Any],
    profile: dict[str, dict[str, Any]],
    threshold: float,
) -> tuple[float, dict[str, float], dict[str, float]]:
    positive_values: list[float] = []
    mitigation_values: list[float] = []
    flags: dict[str, float] = {}
    mitigations: dict[str, float] = {}
    for key, meta in profile.items():
        answer = answers.get(key)
        if not answer:
            continue
        positive = bool(meta.get("positive", True))
        value: float | None = None
        if "noul" in answer:
            value = float(answer["noul"])
        elif "score" in answer:
            criteria = meta.get("criteria", [])
            denominator = max(1, len(criteria) - 1)
            value = max(0.0, min(1.0, float(answer.get("score", 0)) / denominator))
        elif "choice" in answer:
            value = float(answer.get("confidence", 0.0))
        if value is None:
            continue
        if positive:
            positive_values.append(value)
            if value >= threshold:
                flags[key] = round(value, 3)
        else:
            mitigation_values.append(value)
            if value >= threshold:
                mitigations[key] = round(value, 3)
    base = max(positive_values, default=0.0)
    mitigation = max(mitigation_values, default=0.0)
    return max(0.0, base - 0.5 * mitigation), flags, mitigations


def parse_group(
    data: dict[str, Any],
    group: list[Unit],
    profile: dict[str, dict[str, Any]],
    batched: bool,
) -> dict[str, dict[str, Any]]:
    raw = data.get("answers", {}) or {}
    parsed: dict[str, dict[str, Any]] = {}
    for index, unit in enumerate(group, 1):
        answers = {}
        for key in profile:
            name = f"u{index}_{key}" if batched else key
            if name in raw:
                answers[key] = raw[name]
        parsed[unit.id] = answers
    return parsed


def process_request(
    client: SystemOneClient,
    cache: Cache,
    group: list[Unit],
    state: str,
    questions: dict[str, dict[str, Any]],
    profile: dict[str, dict[str, Any]],
    profile_name: str,
    batched: bool,
    threshold: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], str, bool]:
    key = cache.key(client.model, profile_name, group)
    cached = cache.get(key)
    if cached is not None:
        data = cached["data"]
        model = cached.get("model", data.get("model", ""))
        is_cached = True
    else:
        data = client.ask(state, questions)
        model = str(data.get("model", ""))
        cache.put(
            key,
            {
                "data": data,
                "model": model,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )
        is_cached = False
    parsed = parse_group(data, group, profile, batched)
    results = {}
    for unit in group:
        priority, flags, mitigations = score_answers(
            parsed.get(unit.id, {}), profile, threshold
        )
        results[unit.id] = {
            "answers": parsed.get(unit.id, {}),
            "priority": round(priority, 4),
            "flags": flags,
            "mitigations": mitigations,
        }
    return results, data.get("usage", {}) or {}, model, is_cached


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Jev triage",
        "",
        f"- model: `{payload['model_requested']}` (returned: `{payload.get('model_returned') or '-'}`)",
        f"- profile: `{payload['profile']}`",
        f"- units: {payload['stats']['units']}",
        f"- requests: {payload['stats']['requests']} (cached: {payload['stats']['cached']})",
        f"- errors: {payload['stats']['errors']}",
        f"- input tokens: {payload['stats']['input_tokens']}",
        f"- cost: ${payload['stats']['cost']:.6f}",
        f"- elapsed: {payload['stats']['elapsed_ms']} ms",
        "",
        "| priority | unit | flags | mitigations |",
        "|---|---|---|---|",
    ]
    for unit in payload["units"][: payload["top_k"]]:
        flags = ", ".join(f"{k}={v}" for k, v in unit["flags"].items()) or "-"
        mitigations = (
            ", ".join(f"{k}={v}" for k, v in unit["mitigations"].items()) or "-"
        )
        lines.append(
            f"| {unit['priority']:.3f} | `{unit['id']}` | {flags} | {mitigations} |"
        )
    lines.extend(
        [
            "",
            "## 读取建议",
            "",
            "- priority ≥ 0.70：优先用 Read/Grep 深读。",
            "- 0.40–0.70：人工/LLM 复核，尤其是 flags 命中但 mitigations 未命中的单元。",
            "- < 0.40：可跳过；若涉及已知 sink 关键词，仍以 ripgrep 结果为准。",
            "- Jev 只做召回初筛，不作为漏洞结论；最终必须读代码确认。",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"root not found: {root}")
    profile = resolve_profile(args)
    units = list(iter_units(root, args))
    if not units:
        raise SystemExit("no text units found (check --root/--glob/--paths-from)")
    requests = list(build_requests(units, profile, args.batch_size))

    if args.dry_run:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "profile": args.profile,
                    "model": args.model,
                    "units": len(units),
                    "requests": len(requests),
                    "batch_size": args.batch_size,
                    "sample": [
                        {
                            "units": [unit.id for unit in group],
                            "state_chars": len(state),
                            "questions": list(questions),
                        }
                        for group, state, questions, _ in requests[:3]
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    api_key = resolve_api_key(args.api_key)
    client = SystemOneClient(
        endpoint=args.endpoint,
        api_key=api_key,
        model=args.model,
        timeout=args.timeout,
        retries=args.retries,
    )
    cache_dir = Path(args.cache_dir)
    if not cache_dir.is_absolute():
        cache_dir = root / cache_dir
    cache = Cache(cache_dir, not args.no_cache)
    results: dict[str, dict[str, Any]] = {}
    stats = {
        "units": len(units),
        "requests": 0,
        "cached": 0,
        "errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0.0,
        "elapsed_ms": 0,
    }
    errors: list[dict[str, str]] = []
    model_returned = ""
    started = time.time()

    def apply(
        group: list[Unit],
        outcome: tuple[dict[str, dict[str, Any]], dict[str, Any], str, bool],
    ) -> None:
        nonlocal model_returned
        per_unit, usage, model, is_cached = outcome
        model_returned = model or model_returned
        stats["requests"] += 1
        stats["cached"] += 1 if is_cached else 0
        stats["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        stats["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        stats["cost"] += float(usage.get("cost", 0.0) or 0.0)
        for unit in group:
            item = per_unit.get(unit.id, {})
            results[unit.id] = {
                "id": unit.id,
                "path": unit.path,
                "line_start": unit.line_start,
                "line_end": unit.line_end,
                "priority": item.get("priority", 0.0),
                "flags": item.get("flags", {}),
                "mitigations": item.get("mitigations", {}),
                "answers": item.get("answers", {}),
                "cached": is_cached,
            }

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, min(args.workers, 32))
    ) as executor:
        futures = {}
        for group, state, questions, batched in requests:
            future = executor.submit(
                process_request,
                client,
                cache,
                group,
                state,
                questions,
                profile,
                args.profile,
                batched,
                args.threshold,
            )
            futures[future] = (group, state, questions, batched)
        for future in concurrent.futures.as_completed(futures):
            group, state, questions, batched = futures[future]
            try:
                apply(group, future.result())
            except Exception as exc:
                if len(group) > 1 and args.fallback_single:
                    for unit in group:
                        try:
                            outcome = process_request(
                                client,
                                cache,
                                [unit],
                                f"FILE: {unit.id}\n\n{unit.text}",
                                profile,
                                profile,
                                args.profile,
                                False,
                                args.threshold,
                            )
                            apply([unit], outcome)
                        except Exception as single_exc:
                            stats["errors"] += 1
                            errors.append(
                                {"unit": unit.id, "error": str(single_exc)[:300]}
                            )
                else:
                    stats["errors"] += 1
                    for unit in group:
                        errors.append(
                            {"unit": unit.id, "error": str(exc)[:300]}
                        )
    cache.flush()

    stats["elapsed_ms"] = int((time.time() - started) * 1000)
    ordered = sorted(
        results.values(), key=lambda item: item["priority"], reverse=True
    )
    payload = {
        "schema_version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": args.endpoint,
        "model_requested": args.model,
        "model_returned": model_returned,
        "profile": args.profile,
        "root": str(root),
        "top_k": args.top_k,
        "stats": {**stats, "cost": round(stats["cost"], 8)},
        "units": ordered,
        "errors": errors[:50],
    }

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = root / out
    else:
        run_dir = os.environ.get("RUN_DIR", "").strip()
        base = Path(run_dir) if run_dir else root / ".workspace"
        out = base / "triage" / f"jev-{args.profile}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path = out.with_suffix(".md")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.md:
        print(render_markdown(payload))
    else:
        print(
            f"units={stats['units']} requests={stats['requests']} "
            f"cached={stats['cached']} errors={stats['errors']} "
            f"cost=${stats['cost']:.6f} out={out}"
        )
        for unit in ordered[: args.top_k]:
            flags = ",".join(unit["flags"]) or "-"
            print(f"  {unit['priority']:.3f}  {unit['id']}  [{flags}]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jev_triage.py",
        description="Jev/SystemOne file-or-block triage for large repositories",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--profile", default="infra", choices=[*PROFILES, "custom"]
    )
    parser.add_argument("--glob", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--paths-from", default="")
    parser.add_argument("--exclude-tests", action="store_true")
    parser.add_argument("--allow-sensitive", action="store_true")
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--max-file-bytes", type=int, default=2_000_000)
    parser.add_argument("--max-chars", type=int, default=12_000)
    parser.add_argument("--block-lines", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--cache-dir", default=".workspace/triage/jev-cache")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--fallback-single", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--md", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--question", action="append", default=[])
    parser.add_argument("--choice", action="append", default=[])
    parser.add_argument("--score", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_profiles:
        for name, questions in PROFILES.items():
            print(f"{name}: {', '.join(questions)}")
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
