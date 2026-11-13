#!/usr/bin/env python3
"""Export a redacted, reproducible snapshot of observed experiment metadata."""
import argparse
import csv
import hashlib
import json
import subprocess
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def read(path, root):
    try:
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            return None
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None


def api(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def basename(path):
    return Path(path).name if isinstance(path, str) else ''


def intervals(rows):
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get('confidence') not in (None, 'exact'):
            continue
        a, b = row.get('start'), row.get('end')
        if type(a) is int and type(b) is int and 0 < a <= b:
            if result and a <= result[-1][1] + 1:
                result[-1][1] = max(result[-1][1], b)
            else:
                result.append([a, b])
    return result


def merged(pairs):
    out = []
    for a, b in sorted(pairs):
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def count(pairs):
    return sum(b-a+1 for a,b in merged(pairs))


def write_csv(path, rows, fields):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)
    return {'rows':len(rows),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data'))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    board = api('http://127.0.0.1:8787/api/board?view=summary')
    reports = api('http://127.0.0.1:8787/api/verified-reports')
    cohort = {p['id']:p for p in board['projects'] if isinstance(p,dict) and p.get('id')}
    target = read(root/'targets/manifest.json', root) or {}
    targets = target.get('projects', {})
    rows = {}
    rows['projects.csv'] = [dict(project=k, repository_url=str(targets.get(k,{}).get('url','')).replace('git@github.com:','https://github.com/').removesuffix('.git'), source_commit=p.get('commit'), latest_run_id=p.get('latestRunId'), board_state=p.get('state'), board_candidates=p.get('findingsCount'), is_live=p.get('isLive')) for k,p in sorted(cohort.items())]
    metas = {}
    runs = []
    for file in sorted((root/'runs').glob('*/*/run-meta.json')):
        project, run_id = file.parent.parent.name, file.parent.name
        if project not in cohort or file.parent.is_symlink(): continue
        d = read(file,root)
        if not isinstance(d,dict): continue
        metas[project,run_id] = d
        report = read(file.parent/'audit-report.json',root)
        findings = report.get('findings') if isinstance(report,dict) else None
        runs.append(dict(project=project,run_id=run_id,started_at=d.get('started_at'),ended_at=d.get('ended_at'),status=d.get('status'),exit_code=d.get('exit_code'),duration_seconds=d.get('duration_seconds'),source_commit=d.get('commit'),reports_complete=d.get('reports_complete'),candidate_count=len(findings) if isinstance(findings,list) else None,recovered_from=basename(d.get('recovered_from'))))
    rows['runs.csv'] = runs
    workflows=[]; latest={}
    stages=('environment','orchestrator','visual','verify','redteam-lab','redteam-agent','judge','learner')
    for file in sorted((root/'runs').glob('*/*.meta/workflows/*/state.json')):
        project=file.parent.parent.parent.parent.name
        run_id=file.parent.parent.parent.name.removesuffix('.meta')
        if project not in cohort: continue
        d=read(file,root)
        if not isinstance(d,dict): continue
        key=(project,run_id)
        if key not in latest or str(d.get('startedAt',''))>=str(latest[key].get('startedAt','')): latest[key]=d
        receipts={r.get('node'):r for r in d.get('receipts',[]) if isinstance(r,dict)}
        for stage in d.get('steps',stages):
            receipt=receipts.get(stage,{})
            workflows.append(dict(project=project,run_id=run_id,workflow_id=d.get('id'),workflow_status=d.get('status'),stage=stage,stage_status=receipt.get('status') or ('running' if d.get('current')==stage else 'pending'),started_at=receipt.get('startedAt'),ended_at=receipt.get('endedAt')))
    rows['workflow_stages.csv']=workflows
    cycles=[]; rounds=[]
    for file in sorted((root/'rsi/stage-skills/cycles').glob('*/status.json')):
        d=read(file,root)
        if not isinstance(d,dict) or d.get('project') not in cohort: continue
        project=d['project']; rr=d.get('rounds') or []
        cycles.append(dict(project=project,cycle_id=d.get('id'),status=d.get('status'),started_at=d.get('started_at'),ended_at=d.get('ended_at'),max_rounds=d.get('max_rounds'),current_round=d.get('current_round'),round_records_count=len(rr)))
        for item in rr:
            if not isinstance(item,dict):continue
            run_id=basename(item.get('run_dir')); state=latest.get((project,run_id),{})
            rounds.append(dict(project=project,cycle_id=d.get('id'),round_index=item.get('index'),run_id=run_id,recorded_state=item.get('state'),latest_workflow_status=state.get('status'),latest_workflow_id=state.get('id')))
    rows['cycles.csv']=cycles;rows['cycle_rounds.csv']=rounds
    coverage=[]; seen=defaultdict(list)
    coverage_items=[]
    for file in sorted((root/'runs').glob('*/*/task-artifacts/read-coverage/summary.json')):
        project,run_id=file.parents[3].name,file.parents[2].name
        if project not in cohort:continue
        d=read(file,root)
        if not isinstance(d,dict):continue
        start=metas.get((project,run_id),{}).get('started_at')
        coverage_items.append((start or '9999',project,run_id,d))
    for start,project,run_id,d in sorted(coverage_items):
        version=d.get('source_version') or ''
        local=defaultdict(list);paths=set()
        for item in d.get('files',[]):
            if not isinstance(item,dict) or item.get('kind')!='read' or not isinstance(item.get('file'),str):continue
            path=Path(item['file'])
            if path.is_absolute() or '..' in path.parts:continue
            key=(project,version,str(path),item.get('file_sha256') or '')
            local[key].extend(intervals(item.get('ranges') or []));paths.add(str(path))
        unique=sum(count(pairs) for pairs in local.values())
        novel=0
        for key,pairs in local.items():
            before=count(seen[key]);seen[key]=merged(seen[key]+pairs);novel+=count(seen[key])-before
        cumulative=sum(count(v) for k,v in seen.items() if k[0]==project and k[1]==version)
        coverage.append(dict(project=project,run_id=run_id,source_commit=version,status=d.get('status'),observations=d.get('observations'),unattributed_observations=d.get('unattributed'),intent_count=len(d.get('intents') or []),read_files=len(paths),unique_exact_lines=unique,new_unique_exact_lines=novel,cumulative_unique_exact_lines=cumulative,order_basis='run_started_at' if start!='9999' else 'run_id_fallback'))
    rows['stage_coverage.csv']=coverage
    rewards=[]
    for file in sorted((root/'runs').glob('*/*/rsi/reward.json')):
        project,run_id=file.parents[2].name,file.parents[1].name
        if project not in cohort:continue
        d=read(file,root)
        if not isinstance(d,dict):continue
        rewards.append(dict(project=project,run_id=run_id,formula_version=d.get('formula_version'),status=d.get('status'),source_commit=d.get('source_version'),new_lines=d.get('new_lines'),delta_risk_coverage=d.get('delta_risk_coverage'),new_verified=d.get('new_verified'),coverage_reward=d.get('coverage_reward'),vulnerability_reward=d.get('vulnerability_reward'),total=d.get('total'),attribution=d.get('attribution')))
    rows['rsi_rewards.csv']=rewards
    usage=read(root/'.runtime/state/token-usage/summary.json',root) or {}
    tokens=[]
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    for item in usage.get('groups',[]):
        if item.get('project') not in cohort:continue
        row={k:item.get(k) for k in ('project','run_id','stage','model','provider_convention','records','unknown_usage')}
        for field in fields:
            missing=(item.get('missing_fields') or {}).get(field,0)
            row['missing_'+field]=missing
            row[field]=None if missing==item.get('records') else (item.get('totals') or {}).get(field)
        tokens.append(row)
    rows['token_usage.csv']=tokens
    verified=[]
    for item in reports.get('items',[]):
        if item.get('project') not in cohort:continue
        key=item.get('key') or ''
        verified.append(dict(project=item.get('project'),run_id=item.get('runId'),report_key_hash=hashlib.sha256(key.encode()).hexdigest()[:24],severity=item.get('severity'),ready_at=item.get('readyAt'),time_basis=item.get('timeBasis')))
    rows['verified_reports.csv']=verified
    schemas={
      'projects.csv':'project repository_url source_commit latest_run_id board_state board_candidates is_live',
      'runs.csv':'project run_id started_at ended_at status exit_code duration_seconds source_commit reports_complete candidate_count recovered_from',
      'workflow_stages.csv':'project run_id workflow_id workflow_status stage stage_status started_at ended_at',
      'cycles.csv':'project cycle_id status started_at ended_at max_rounds current_round round_records_count',
      'cycle_rounds.csv':'project cycle_id round_index run_id recorded_state latest_workflow_status latest_workflow_id',
      'stage_coverage.csv':'project run_id source_commit status observations unattributed_observations intent_count read_files unique_exact_lines new_unique_exact_lines cumulative_unique_exact_lines order_basis',
      'rsi_rewards.csv':'project run_id formula_version status source_commit new_lines delta_risk_coverage new_verified coverage_reward vulnerability_reward total attribution',
      'token_usage.csv':'project run_id stage model provider_convention records unknown_usage input_tokens output_tokens cache_creation_input_tokens cache_read_input_tokens missing_input_tokens missing_output_tokens missing_cache_creation_input_tokens missing_cache_read_input_tokens',
      'verified_reports.csv':'project run_id report_key_hash severity ready_at time_basis'}
    files={name:write_csv(output/name,rows[name],schema.split()) for name,schema in schemas.items()}
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    manifest={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'source_revision':revision,'project_cohort':'GET /api/board?view=summary projects','projects':len(cohort),'strict_verified_reports':len(verified),'source_generated_at':{'board':board.get('generatedAt'),'token_usage':usage.get('generated_at')},'files':files,'limitations':['Source records may change while active projects run.','Read lines have no whole-repository denominator.','Strict verified reports require an AI image; they are a subset of reviewed findings.','Token usage is partial and provider conventions differ.']}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'projects':len(cohort),'reports':len(verified),'files':{k:v['rows'] for k,v in files.items()}},ensure_ascii=False))

if __name__=='__main__':main()
