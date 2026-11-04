import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'scripts/verify/phase4_verify_agent.sh'
FAKE = '''#!/usr/bin/env python3
import fcntl,json,os,time
from pathlib import Path
state=Path(os.environ['PARALLEL_STATE'])
def update(delta):
 with state.open('a+') as file:
  fcntl.flock(file,fcntl.LOCK_EX);file.seek(0)
  data=json.loads(file.read() or '{"active":0,"peak":0,"ids":[]}')
  data['active']+=delta;data['peak']=max(data['peak'],data['active'])
  if delta>0:data['ids'].append(os.environ['PHASE4_SAFE_ID'])
  file.seek(0);file.truncate();file.write(json.dumps(data));file.flush()
update(1)
time.sleep(float(os.environ.get('PARALLEL_DELAY', '.4')))
update(-1)
'''


def run_fixture(tmp_path, jobs=None):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'audit-report.json').write_text(json.dumps({'findings':[
        {'id': identifier, 'title': identifier, 'severity': 'high'}
        for identifier in ['F-1', 'F/2', 'F 2', 'F-4']]}))
    fake = tmp_path / 'fake-claude'
    fake.write_text(FAKE)
    fake.chmod(0o755)
    output = tmp_path / 'verify'
    env = {**os.environ, 'PARALLEL_STATE': str(tmp_path / 'state.json')}
    args = ['bash', str(WRAPPER), '--project', 'demo', '--run-dir', str(run),
            '--image', 'fixture:demo', '--source', str(tmp_path), '--claude-bin', str(fake), '--output', str(output)]
    if jobs is not None:
        args += ['--jobs', str(jobs)]
    return args, env, output


@pytest.mark.parametrize('jobs,peak', [(None,4),(2,2),(1,1)])
def test_parallel_limit_and_isolated_results(tmp_path, jobs, peak):
    args, env, output = run_fixture(tmp_path, jobs)
    completed = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    observed = json.loads((tmp_path / 'state.json').read_text())
    assert observed['peak'] == peak
    assert observed['active'] == 0
    assert len(set(observed['ids'])) == 4
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['concurrency'] == (jobs or 10)
    assert summary['processed'] == 4
    assert [item['source_index'] for item in summary['findings']] == list(range(4))
    for item in summary['findings']:
        identifier = item['finding_id']
        assert json.loads((output / identifier / 'result.json').read_text())['finding_id'] == identifier
        assert json.loads((output / identifier / 'verify-report.json').read_text())['finding_id'] == identifier
        assert json.loads((output / 'tasks' / f'{identifier}.json').read_text())['state'] == 'completed'


def test_cancel_terminates_worker_group_and_marks_queued_tasks(tmp_path):
    output = tmp_path / 'out'
    output.mkdir()
    jobs = [{'id': str(i), 'entry': {'index': i, 'title': str(i)}} for i in range(3)]
    for job in jobs:
        (output / job['id']).mkdir()
    job_file = tmp_path / 'jobs.ndjson'
    job_file.write_text('\n'.join(json.dumps(job) for job in jobs))
    marker = tmp_path / 'child.pid'
    env = {**os.environ, 'PID_MARKER': str(marker),
           'BASH_FUNC_verify_one%%': "() { bash -c 'trap \"\" TERM; echo $$ > \"$PID_MARKER\"; sleep 30' & wait; }"}
    process = subprocess.Popen(['python3', str(ROOT / 'scripts/verify/parallel.py'), '--jobs', '1',
                                '--input', str(job_file), '--output', str(output)], env=env)
    try:
        for _ in range(100):
            if marker.exists():
                break
            time.sleep(.03)
        assert marker.exists()
        child = int(marker.read_text())
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=10) == 130
        for job in jobs:
            assert json.loads((output / 'tasks' / f'{job["id"]}.json').read_text())['state'] == 'cancelled'
        state = Path(f'/proc/{child}/stat')
        assert not state.exists() or state.read_text().split()[2] == 'Z'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_rejects_more_than_ten_workers(tmp_path):
    args, env, _ = run_fixture(tmp_path, 11)
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 3


def test_default_runs_ten_candidates_at_once(tmp_path):
    args, env, output = run_fixture(tmp_path)
    (tmp_path / 'run/audit-report.json').write_text(json.dumps({'findings': [
        {'id': f'F-{i}', 'title': f'候选 {i}', 'severity': 'high'} for i in range(12)]}))
    env['PARALLEL_DELAY'] = '1.5'
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    state = json.loads((tmp_path / 'state.json').read_text())
    assert state['peak'] == 10
    assert len(state['ids']) == 10
    assert json.loads((output / 'summary.json').read_text())['processed'] == 10


def test_running_batch_keeps_startup_script_snapshot(tmp_path):
    args, env, output = run_fixture(tmp_path)
    copy = tmp_path / 'phase4.sh'
    copy.write_text(WRAPPER.read_text())
    args[1] = str(copy)
    env['PHASE4_REPO_ROOT'] = str(ROOT)
    env['PARALLEL_DELAY'] = '1'
    process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            if (tmp_path / 'state.json').exists():
                break
            time.sleep(.03)
        assert (tmp_path / 'state.json').exists()
        copy.write_text('exit 99\n')
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        assert json.loads((output / 'summary.json').read_text())['processed'] == 4
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
