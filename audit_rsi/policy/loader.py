from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import Any

from .base import BasePolicy

BLOCKED_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)

SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "range",
        "reversed",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    )
}
SAFE_BUILTINS["__build_class__"] = builtins.__build_class__


class PolicyRejected(ValueError):
    pass


def _validate(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise PolicyRejected("imports are not allowed")
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.While)):
            raise PolicyRejected(
                f"{type(node).__name__} is not allowed in a replay policy"
            )
        if isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith)):
            raise PolicyRejected("async syntax is not allowed")
        if isinstance(node, (ast.Yield, ast.YieldFrom, ast.Await)):
            raise PolicyRejected("generators and await are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise PolicyRejected("dunder attribute access is not allowed")
        if isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES or node.id.startswith("__"):
                raise PolicyRejected(f"name is not allowed: {node.id}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_NAMES:
                raise PolicyRejected(f"call is not allowed: {node.func.id}")


def load_policy_source(source: str, filename: str = "<policy>") -> type[BasePolicy]:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise PolicyRejected(f"syntax error: {exc}") from exc
    _validate(tree)
    namespace: dict[str, Any] = {
        "__builtins__": dict(SAFE_BUILTINS),
        "__name__": "audit_rsi_policy",
        "BasePolicy": BasePolicy,
    }
    try:
        exec(compile(tree, filename, "exec"), namespace)
    except Exception as exc:
        raise PolicyRejected(f"policy failed to load: {exc}") from exc
    policy = namespace.get("Policy")
    if not isinstance(policy, type) or not issubclass(policy, BasePolicy):
        raise PolicyRejected("policy must define class Policy(BasePolicy)")
    return policy


def load_policy_file(path: str | Path) -> type[BasePolicy]:
    target = Path(path)
    return load_policy_source(target.read_text(encoding="utf-8"), str(target))
