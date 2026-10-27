#!/usr/bin/env python3
"""Register the env-build adapter with SkillOpt and delegate to train.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLOPT_ROOT = Path(
    os.environ.get("SKILLOPT_ROOT", REPO_ROOT.parent / "SkillOpt")
).expanduser().resolve()
if not (SKILLOPT_ROOT / "scripts" / "train.py").exists():
    raise SystemExit(
        f"SkillOpt not found at {SKILLOPT_ROOT}; set SKILLOPT_ROOT to the checkout"
    )
if str(SKILLOPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLOPT_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import train
from integrations.skillopt_env_build.adapter import EnvBuildAdapter

train._ENV_REGISTRY["mygoldmine_env_build"] = EnvBuildAdapter

if __name__ == "__main__":
    train.main()
