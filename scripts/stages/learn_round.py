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
from submission import config, INSTRUCTION, accepted_submissions
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
    if os.environ.get('RSI_SKILLOPT_ENABLED','0')!='1':
        return {'status':'optional_disabled','results':[],'candidates':[]}
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


def learning_delivery(run):
    result = accepted_submissions('learner', run)
    expected = str(Path(run).resolve() / 'rsi/learning-result.json')
    if not any(row['artifact'] == expected for row in result['deliveries']):
        raise ValueError('缺少学习智能体最终产物的有效交付回执')
    return result


def learn(run, project, repo=ROOT, timeout=180, skillopt_timeout=300):
    repo = Path(repo)
    run = Path(run).resolve()
    if os.environ.get('STAGE_SKILL_EVALUATING') or os.environ.get('SKILLOPT_RUN'):
        return {'status': 'skipped', 'reason': 'evaluation_or_optimization_in_progress'}
    bank = SkillBank(repo)
    records = bank.feedback(run, project)
    request_hashes = _request_hashes(run)
    fingerprint = digest({'learning_mode':'exploration_md_v1','feedback': [{k: v for k, v in record.items() if k != 'generated_at'} for record in records], 'requests': request_hashes, 'skills': bank.render('learner', project, override=os.environ.get('STAGE_SKILL_OVERRIDE'))['versions']})
    file = run / 'rsi/stage-learning-run.json'
    prior = read(file, {})
    prior_skillopt = prior.get('skillopt', {}) if isinstance(prior.get('skillopt'), dict) else {}
    prior_results = prior_skillopt.get('results', []) if isinstance(prior_skillopt.get('results'), list) else []
    skillopt_failed = prior_skillopt.get('status') in ('error', 'failed') or any(
        isinstance(row, dict) and row.get('status') in ('error', 'failed') for row in prior_results
    )
    if prior.get('input_hash') == fingerprint and prior.get('exit_code') == 0 and not skillopt_failed:
        try:
            prior['delivery'] = learning_delivery(run)
            return prior
        except (OSError, ValueError):
            pass
    settings = read(repo / 'config/stage-models.json', {})
    model = os.environ.get('RSI_LEARNER_MODEL') or settings.get('audit') or '360-proxy/deepseek/deepseek-v4.1-flash'
    spec = importlib.util.spec_from_file_location('scene_connection', repo / '.claude/skills/project-cartographer/scripts/render_attack_scenes_agentic.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model, env = module.claude_connection(model)
    prompt = (
        f'项目：{project}。使用 stage-skill-learning 技能，读取 {run}/rsi/stage-feedback/index.json。'
        '本轮核心任务是复盘第二阶段审计轨迹、读取覆盖、审计意图、未解假设和有趣线索，'
        '鼓励优化通用审计技能，鼓励增加项目专属技能，让下一轮审计探索未覆盖区域并深入已有线索。'
        '先用 get_audit_skills 读取已生效补充，按需读取第二阶段轨迹；长日志用 rank_learning_evidence'
        '与 read_learning_evidence 分段导航，避免全量阅读。其他阶段仅作为验证反馈，不逐候选复审。'
        '可用 WebSearch/WebFetch 检索同类项目漏洞披露、官方公告和修复提交，记录来源、版本条件和'
        '本项目待核对机制，不能把外部内容直接当作漏洞成立。'
        '通过 update_audit_skill 提交 scope=general 或 project、稳定 skill_name、完整该技能段内容'
        '和本次证据。相同名称用于优化旧技能，不同名称增加新技能。下一轮直接加载，不等待评估或试用。'
        '记录下一轮要查哪里、审计视角、追踪步骤和预期证据；通用方法不得混入仅适用本项目的约束。'
        '项目经验可进入项目技能，不必包装成通用方法缺口；框架故障另行归因，不用提示词假装修复。'
        '评分是运行反馈而非发布门槛，不改动隔离、工具权限、漏洞判定或证据标准。'
        '通过 submit_learning 提交本轮归因和 update_audit_skill 返回的 proposal_ids；'
        '收到修改意见就修正重交，accepted 后结束。应主动寻找下一轮深入方向，不为凑数编造改进。'
        '证据不足如实声明限制。最终产物由工具生成，不修改后续采用记录。'
    )
    before = set((run / '.stage-skill-proposals').glob('*.json'))
    attempt = run / 'rsi/stage-learning-attempts' / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    context = INSTRUCTION + '\n' + instruction('learner', run, project)
    result = {'log': str(attempt / 'stream.jsonl'), 'project': project, 'input_hash': fingerprint, 'model': model, 'started_at': now()}
    try:
        with (attempt / 'stream.jsonl').open('w') as output, (attempt / 'stderr.log').open('w') as error:
            child = run_session([os.environ.get('CLAUDE_BIN', 'claude'), '--setting-sources', 'project,local', '--model', model, '--agent', 'stage-skill-learner', '--append-system-prompt', context, '--mcp-config', json.dumps(config('learner', run)), '--permission-mode', 'bypassPermissions', '--output-format', 'stream-json', '--verbose', '-p', prompt], cwd=repo, env=env, stdout=output, stderr=error, timeout=timeout)
        result['exit_code'] = child.returncode
    except (subprocess.TimeoutExpired, OSError) as exc:
        result.update(exit_code=124 if isinstance(exc, subprocess.TimeoutExpired) else 1, error=type(exc).__name__)
    if result.get('exit_code') == 0:
        try:
            result['delivery'] = learning_delivery(run)
        except (OSError, ValueError) as exc:
            result.update(exit_code=1, error='学习产物未通过交付验收：' + str(exc))
    result['proposals'] = len(set((run / '.stage-skill-proposals').glob('*.json')) - before)
    result['skillopt'] = _run_skillopt(run, project, repo, model, skillopt_timeout) if result['exit_code']==0 else {'status':'skipped_failed_learning','results':[],'candidates':[]}
    result['skillopt_candidates'] = len(result['skillopt'].get('candidates', []))
    result['ended_at'] = now()
    write(attempt / 'result.json', result)
    write(file, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    print(json.dumps(learn(args.root, args.project), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
