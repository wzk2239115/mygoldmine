import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_model_flags_reach_supervisor_after_cli_parsing(tmp_path):
    engine = tmp_path / 'engine'
    engine.mkdir()
    shutil.copy2(ROOT / 'run.sh', engine / 'run.sh')
    source = tmp_path / 'source'
    source.mkdir()
    binary = tmp_path / 'bin'
    binary.mkdir()
    capture = tmp_path / 'args.json'
    for name, content in {
        'docker': '#!/bin/sh\nexit 0\n',
        'setsid': '#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ["MODEL_ARGS_CAPTURE"],"w").write(json.dumps(sys.argv[1:]))\n',
    }.items():
        script = binary / name
        script.write_text(content)
        script.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if key not in ['MODEL', 'VERIFY_MODEL', 'VISUAL_MODEL', 'ENV_MODEL', 'JUDGE_MODEL', 'REDTEAM_MODEL', 'TIMEOUT']}
    env.update(PATH=f'{binary}:{os.environ["PATH"]}', MODEL_ARGS_CAPTURE=str(capture))
    result = subprocess.run(['bash', str(engine / 'run.sh'), str(source), '--run-dir', str(tmp_path / 'run'), '--model', 'audit-new', '--verify-model', 'blue-new', '--env-model', 'env-new', '--visual-model', '360-proxy/scene-new', '--judge-model', '360-proxy/judge-new', '--redteam-model', 'red-new'], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1  # The fake supervisor exits without launching an audit.
    args = json.loads(capture.read_text())
    assert args[args.index("--timeout") + 1] == "86400"
    for flag, value in {'--model':'audit-new','--verify-model':'blue-new','--env-model':'env-new','--visual-model':'scene-new','--judge-model':'judge-new','--redteam-model':'red-new'}.items():
        assert args[args.index(flag)+1] == value
