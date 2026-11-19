#!/usr/bin/env python3
import os, sys, json, traceback
from pathlib import Path
from types import SimpleNamespace
SCAN = Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/results/codex-security/sol')
PLUGIN = Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/tools/codex-cli/node_modules/@openai/codex-security/_bundled_plugin')
sys.path.insert(0, str(PLUGIN / 'scripts'))
os.environ['CODEX_SECURITY_STATE_DIR'] = str(SCAN / '.wbstate')
import workbench_db as wb
def patched(p, writable_output=False):
    return Path(p).absolute()
wb.require_canonical_scan_directory = patched
wb._WORKBENCH_DB_CONTEXT.require_canonical_scan_directory = patched
scan_id='e2734f35-14d6-4012-968e-66758e9463d2'
conn=wb.connect(deferred=True)
args=SimpleNamespace(scan_id=scan_id, claim_token=None, cost_json=None, command='complete-scan', thread_id=None, turn_id=None, model_thread_id=None)
try:
    res=wb.complete_scan(conn,args,prepare_only=False)
    print('COMPLETE_OK', json.dumps({k:res.get(k) for k in ('scanId','status','phase')}, sort_keys=True))
except BaseException as exc:
    print('COMPLETE_FAILED:',type(exc).__name__,exc); traceback.print_exc(); sys.exit(1)
