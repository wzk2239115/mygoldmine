#!/usr/bin/env python3
"""独立提炼八阶段技能；完整运行失败也可调用。"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from skill_bank import SkillBank, ROOT, digest, read, write, now, instruction
from submission import config
from owned_process import run_session

SKILLOPT_ADAPTER = Path(__file__).resolve().parent / 'skillopt_adapter.py'


def _request_hashes(run):
    directory = Path(run) / 'rsi/skillopt-requests'
    if not directory.exists():
        return []
    return [
        {'name': path.name, 'sha256': digest(path.read_text(encoding='utf-8'))}
        for path in sorted(directory.glob('*.json'))
    ]


def _run_skillopt(run, project, repo, model, timeout):
    requests = sorted((Path(run) / 'rsi/skillopt-requests').glob('*.json')) if (Path(run) / 'rsi/skillopt-requests').exists() else []
    if not requests:
        return {'status': 'no_request', 'requests': 0, 'results': []}
    results = []
    for request in requests[:2]:
        env = dict(os.environ)
        env['PYTHONPATH'] = str(repo) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        try:
            child = run_session(
                [sys.executable, str(SKILLOPT_ADAPTER), '--request', str(request), '--root', str(repo), '--project', project, '--model', model or ''],
                cwd=repo, env=env, capture_output=True, text=True,
                timeout=max(30, int(timeout)),
            )
            payload = {}
            try:
                payload = json.loads(child.stdout)
            except ValueError:
                payload = {'status': 'error', 'error': (child.stderr or child.stdout or '')[-2000:]}
            if child.returncode and payload.get('status') != 'failed':
                payload = {'status': 'error', 'error': (child.stderr or child.stdout or '')[-2000:]}
            results.append({'request': request.name, **payload})
        except (subprocess.TimeoutExpired, OSError) as exc:
            results.append({'request': request.name, 'status': 'error', 'error': f'{type(exc).__name__}: {exc}'})
    candidates = [row.get('candidate_id') for row in results if row.get('status') == 'candidate']
    return {
        'status': 'candidate' if candidates else 'no_candidate',
        'requests': len(requests),
        'results': results,
        'candidates': candidates,
    }


def learn(run, project, repo=ROOT, timeout=180, skillopt_timeout=300):
    repo = Path(repo)
    run = Path(run).resolve()
    if os.environ.get('STAGE_SKILL_EVALUATING') or os.environ.get('SKILLOPT_RUN'):
        return {'status': 'skipped', 'reason': 'evaluation_or_optimization_in_progress'}
    bank = SkillBank(repo)
    records = bank.feedback(run, project)
    request_hashes = _request_hashes(run)
    fingerprint = digest({'feedback': [{k: v for k, v in record.items() if k != 'generated_at'} for record in records], 'requests': request_hashes, 'skills': bank.render('learner', project, override=os.environ.get('STAGE_SKILL_OVERRIDE'))['versions']})
    file = run / 'rsi/stage-learning-run.json'
    prior = read(file, {})
    prior_skillopt = prior.get('skillopt', {}) if isinstance(prior.get('skillopt'), dict) else {}
    prior_results = prior_skillopt.get('results', []) if isinstance(prior_skillopt.get('results'), list) else []
    skillopt_failed = prior_skillopt.get('status') in ('error', 'failed') or any(
        isinstance(row, dict) and row.get('status') in ('error', 'failed') for row in prior_results
    )
    if prior.get('input_hash') == fingerprint and prior.get('exit_code') == 0 and not skillopt_failed:
        return prior
    settings = read(repo / 'config/stage-models.json', {})
    model = os.environ.get('RSI_LEARNER_MODEL') or settings.get('audit') or '360-proxy/deepseek/deepseek-v4.1-flash'
    spec = importlib.util.spec_from_file_location('scene_connection', repo / '.claude/skills/project-cartographer/scripts/render_attack_scenes_agentic.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model, env = module.claude_connection(model)
    prompt = (
        f'项目：{project}。读取 {run}/rsi/stage-feedback/index.json，使用 stage-skill-learning 技能综合各阶段反馈。'
        '仅按反馈索引中的实际证据路径读取文件；缺失文件明确记录，不猜测路径或搜索其他批次。'
        '先读阶段摘要，每份大日志只读相关片段；不要全量重读轨迹。'
        '最多补读六个证据文件后收敛，选择证据充分的目标立即提交请求；若不充分则明确无候选并结束。'
        '只需七阶段综合归因，不需要逐条复核每个漏洞，不重新搜集验证报告已包含的执行证据。'
        '先归因并选择最多两个证据最充分的目标阶段。对选定目标默认调用 request_skillopt_optimization，'
        '提交问题归因、修改建议、证据、预期改善、可能退化和适用条件；只有明确只需一条短规则、'
        '不需要重写时才用 propose_skill_update。'
        '项目标识使用调用方提供的项目目录标识，报告中的品牌名称不是项目标识。'
        '不要进行新审计，不要声称候选已经评估或发布。'
    )
    before = set((run / '.stage-skill-proposals').glob('*.json'))
    attempt = run / 'rsi/stage-learning-attempts' / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    context = instruction('learner', run, project)
    result = {'log': str(attempt / 'stream.jsonl'), 'project': project, 'input_hash': fingerprint, 'model': model, 'started_at': now()}
    try:
        with (attempt / 'stream.jsonl').open('w') as output, (attempt / 'stderr.log').open('w') as error:
            child = run_session([os.environ.get('CLAUDE_BIN', 'claude'), '--setting-sources', 'project,local', '--model', model, '--agent', 'stage-skill-learner', '--append-system-prompt', context, '--mcp-config', json.dumps(config('learner', run)), '--permission-mode', 'bypassPermissions', '--output-format', 'stream-json', '--verbose', '-p', prompt], cwd=repo, env=env, stdout=output, stderr=error, timeout=timeout)
        result['exit_code'] = child.returncode
    except (subprocess.TimeoutExpired, OSError) as exc:
        result.update(exit_code=124 if isinstance(exc, subprocess.TimeoutExpired) else 1, error=type(exc).__name__)
    result['proposals'] = len(set((run / '.stage-skill-proposals').glob('*.json')) - before)
    result['skillopt'] = _run_skillopt(run, project, repo, model, skillopt_timeout) if result['exit_code']==0 else {'status':'skipped_failed_learning','results':[],'candidates':[]}
    result['skillopt_candidates'] = len(result['skillopt'].get('candidates', []))
    result['ended_at'] = now()
    write(attempt / 'result.json', result)
    write(file, result)
    bank.feedback(run, project)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    print(json.dumps(learn(args.root, args.project), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
