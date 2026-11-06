#!/usr/bin/env python3
"""只在阶段二启动器提供采集目录时启用。"""

import os
import runpy
from pathlib import Path

if os.environ.get("MYGOLDMINE_READ_COVERAGE_ROOT"):
    home = Path(__file__).resolve().parents[2]
    import sys

    sys.argv = [str(home / "scripts/audit/read_coverage.py"), "hook"]
    runpy.run_path(sys.argv[0], run_name="__main__")
