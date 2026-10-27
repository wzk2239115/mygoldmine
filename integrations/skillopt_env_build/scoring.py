from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STATUS_RANK = {
    "unknown": 0,
    "blocked": 0,
    "planned": 1,
    "partial": 2,
    "ready": 3,
}

BASE_SOFT = {
    "ready": 1.0,
    "partial": 0.65,
    "planned": 0.3,
    "blocked": 0.0,
    "unknown": 0.0,
}


@dataclass(frozen=True)
class EnvBuildScore:
    hard: int
    soft: float
    detail: dict[str, Any] = field(default_factory=dict)


def score_manifest(
    manifest: dict[str, Any] | None,
    expected: dict[str, Any] | None = None,
    *,
    error: str = "",
    timed_out: bool = False,
) -> EnvBuildScore:
    manifest = manifest or {}
    expected = expected or {}
    status = str(manifest.get("env_status", "unknown")).lower()
    rank = STATUS_RANK.get(status, 0)
    expected_status = str(expected.get("env_status", "ready")).lower()
    expected_rank = STATUS_RANK.get(expected_status, 3)
    exit_code = manifest.get("build_exit_code")
    image_id = bool(manifest.get("image_id"))
    require_image = bool(expected.get("require_image", True))
    require_exit = expected.get("require_build_exit_code", 0)
    if require_exit is None:
        require_exit = 0

    hard = int(
        rank >= expected_rank
        and exit_code == require_exit
        and (image_id or not require_image)
        and not error
        and not timed_out
    )

    soft = BASE_SOFT.get(status, 0.0)
    if image_id:
        soft += 0.05
    if require_image and not image_id:
        soft = min(soft, 0.75)
    if exit_code not in (require_exit, None):
        soft = min(soft, 0.3)
    if error:
        soft = min(soft, 0.1)
    if timed_out:
        soft = min(soft, 0.05)
    partial_reasons = manifest.get("partial_reasons", []) or []
    limitations = manifest.get("limitations", []) or []
    penalty = min(
        0.15,
        0.02 * len(partial_reasons) + 0.01 * len(limitations),
    )
    soft = max(0.0, min(1.0, soft - penalty))

    return EnvBuildScore(
        hard=hard,
        soft=soft,
        detail={
            "env_status": status,
            "expected_status": expected_status,
            "status_rank": rank,
            "expected_rank": expected_rank,
            "build_exit_code": exit_code,
            "has_image_id": image_id,
            "require_image": require_image,
            "partial_reasons": len(partial_reasons),
            "limitations": len(limitations),
            "error": error,
            "timed_out": timed_out,
        },
    )
