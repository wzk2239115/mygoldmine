import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/stages'))
sys.path.insert(0, str(ROOT / 'scripts/redteam'))
import batch


def report(tmp_path, findings=None):
    finding = {'id': 'F-1', 'title': '未认证接口允许远程关闭服务',
               'root_cause': '缺少认证', 'impact': '拒绝服务',
               'reproduction': '启动服务并调用接口', 'remediation': '增加认证',
               'evidence': ['app.py:10']}
    path = tmp_path / 'run-current/audit-report.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'project': 'demo', 'findings': findings if findings is not None else [finding]}))
    return path


def test_current_report_resolves_while_global_ledger_has_no_completed_run(tmp_path):
    path = report(tmp_path)
    snapshot = batch.report_snapshot(path)
    candidate = {'project': 'demo', 'run_id': 'run-current', 'id': 'F-1'}
    assert batch.resolve_candidate(candidate, {}, snapshot)['raw']['id'] == 'F-1'
    assert snapshot['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    for override in ({'run_id': 'old'}, {'project': 'other'}, {'id': 'missing'}):
        assert batch.resolve_candidate({**candidate, **override}, {}, snapshot) is None


@pytest.mark.parametrize('kind', ['incomplete', 'duplicate'])
def test_current_report_rejects_invalid_deliverables(tmp_path, kind):
    path = report(tmp_path)
    value = json.loads(path.read_text())
    if kind == 'incomplete':
        value['findings'][0].pop('reproduction')
    else:
        value['findings'].append(value['findings'][0].copy())
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        batch.report_snapshot(path)


def test_ledger_fallback_keeps_selected_historical_occurrence(monkeypatch):
    occurrence = {'raw': {'id': 'F-1', 'title': 'historical'}}
    ledger = {'occurrences': {'old-key': occurrence}}
    monkeypatch.setattr(batch.base.finding_ledger, 'resolve_reference', lambda *a, **kw: ['old-key'])
    assert batch.resolve_candidate({'project': 'demo', 'id': 'F-1', 'run_id': 'old'}, ledger) is occurrence


def test_connection_launcher_binds_model_and_excludes_personal_settings(tmp_path):
    config = tmp_path / 'opencode.json'
    config.write_text(json.dumps({'provider': {'360-proxy': {'options': {'apiKey': 'fixture-token'}}}}))
    executable = tmp_path / 'fake-claude'
    executable.write_text('#!/usr/bin/env python3\nimport json,os,sys\nprint(json.dumps({"args":sys.argv[1:], "base":os.getenv("ANTHROPIC_BASE_URL"), "model":os.getenv("ANTHROPIC_MODEL"), "auth":os.getenv("ANTHROPIC_AUTH_TOKEN")}))\n')
    executable.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if not key.startswith(('ANTHROPIC_', 'GLM_'))}
    env['OPENCODE_CONFIG'] = str(config)
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/stages/claude_connection.py'),
                             '360-proxy/test-model', str(executable), '--model', 'wrong'],
                            env=env, capture_output=True, text=True, check=True)
    value = json.loads(result.stdout)
    assert value == {'args': ['--setting-sources', 'project,local', '--model', 'test-model'],
                     'base': 'https://api.360.cn', 'model': 'test-model', 'auth': 'fixture-token'}


def test_blue_all_blocked_is_not_completed(tmp_path):
    path = report(tmp_path)
    value = json.loads(path.read_text())
    value['findings'][0]['severity'] = 'high'
    path.write_text(json.dumps(value))
    fake = tmp_path / 'claude'
    fake.write_text('#!/bin/sh\nexit 1\n')
    fake.chmod(0o755)
    output = tmp_path / 'verify'
    result = subprocess.run(['bash', str(ROOT / 'scripts/verify/phase4_verify_agent.sh'),
                             '--project', 'demo', '--run-dir', str(path.parent), '--image', 'fixture:test', '--source', str(tmp_path),
                             '--claude-bin', str(fake), '--output', str(output), '--max', '1'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['status'] == 'blocked'
    assert summary['counts']['blocked'] == 1


def test_standalone_connection_uses_available_default_model():
    from claude_connection import claude_connection
    model, env = claude_connection('', {})
    assert model == 'deepseek/deepseek-v4.1-flash'
    assert env['ANTHROPIC_MODEL'] == model
