#!/usr/bin/env python3
"""Snapshot stage evidence and rerun only stage 08 using the existing optimizer and gates."""
import argparse
import os
import shutil
from pathlib import Path
from skill_bank import SkillBank, ROOT, read, write, now
from learn_round import learn


def retry_learning(source, output, project):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_relative_to(ROOT/'runs') or not output.is_relative_to(ROOT/'runs') or source == output:
        raise ValueError('学习输入与输出必须位于运行目录且相互独立')
    source_status = Path(str(source)+'.meta')/'status.json'
    if source_status.is_file():
        write(Path(str(output)+'.meta')/'status.json', read(source_status, {}))
    bank = SkillBank(ROOT)
    records = bank.feedback(source, project)
    snapshots = []
    for record in records:
        # Learning is not its own training evidence.
        if record['stage'] == 'learner':
            continue
        record = dict(record)
        refs = []
        for index, ref in enumerate(record.get('evidence', [])):
            original = (ROOT/ref['path']).resolve()
            if not original.is_relative_to(ROOT) or not original.is_file():
                raise ValueError('反馈证据文件无效')
            destination = output/'evidence'/record['stage']/f'{index}-{original.name}'
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
            refs.append({**ref, 'source_path': ref['path'], 'path': str(destination.relative_to(ROOT))})
        record['evidence'] = refs
        snapshots.append(record)
        write(output/'rsi/stage-feedback'/f"{record['stage']}.json", record)
    write(output/'rsi/stage-feedback/index.json', {'project': project, 'source_run': str(source), 'stages': snapshots})
    write(output/'rsi/feedback-snapshot.json', {'source_run': str(source), 'created_at': now()})
    before = {file.stem for file in (bank.root/'candidates').glob('*.json')}
    result = learn(output, project, timeout=int(os.environ.get('RSI_LEARNER_TIMEOUT', '360')), skillopt_timeout=int(os.environ.get('RSI_SKILLOPT_TIMEOUT', '300')))
    rows = result.get('skillopt', {}).get('results', [])
    failed = result.get('exit_code', 1) != 0 or any(row.get('status') in ('error', 'failed') for row in rows)
    after = {file.stem for file in (bank.root/'candidates').glob('*.json')}
    evaluation = bank.advance(project, candidate_ids=after-before) if not failed else {'status': 'learning_failed', 'published': [], 'results': []}
    write(output/'rsi/stage-learning-evaluation.json', evaluation)
    summary = {'status': 'failed' if failed else 'degraded' if any(row.get('status') == 'evaluation_error' for row in evaluation.get('results', [])) else 'completed', 'learning': result, 'evaluation': evaluation, 'ended_at': now()}
    write(output/'rsi/learning-retry.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    result = retry_learning(args.source, args.output, args.project)
    print(result['status'])
    raise SystemExit(0 if result['status'] in ('completed', 'degraded') else 1)
