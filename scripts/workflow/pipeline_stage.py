"""记录串行审计当前执行的阶段，不代表阶段成功。"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys


def record_stage(node, candidate=""):
    output = os.environ.get("PIPELINE_STAGE_FILE")
    if not output:
        return
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"node": node, "candidate": candidate,
                                    "updated_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    temporary.replace(target)


if __name__ == "__main__":
    record_stage(sys.argv[1])
