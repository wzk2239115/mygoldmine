#!/usr/bin/env python3
"""有停止条件的 01—08 迭代控制器；不假设每一轮必然改善。"""
import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from skill_bank import SkillBank, ROOT, now, read, write, identifier
from learn_round import learn

def cycle(source,project,rounds=3,patience=2,wall=108000,repo=ROOT,poll=5):
    repo=Path(repo);bank=SkillBank(repo);identifier(project)
    source=Path(source).resolve()
    if source.name!=project:raise ValueError('项目名必须与现有运行入口的源码目录名一致')
    lock=repo/'runs'/f'.learning-cycle-{project}.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    try:lock.mkdir()
    except FileExistsError:raise ValueError('该项目已有学习循环，请检查循环状态或遗留锁')
    (lock/'pid').write_text(str(os.getpid()))
    root=repo/'rsi/stage-skills/cycles'/uuid.uuid4().hex;root.mkdir(parents=True)
    state={'id':root.name,'project':project,'status':'running','started_at':now(),'rounds':[]};write(root/'status.json',state)
    stale=0
    try:
        for index in range(rounds):
            if (root/'stop').exists():state['status']='stopped';break
            before_round=bank.active()
            run=repo/'runs'/project/f'learning-{root.name}-{index+1}'
            with (root/f'round-{index+1}.log').open('w') as log:
                models=read(repo/'config/stage-models.json',{})
                flags={'audit':'--model','environment':'--env-model','visual':'--visual-model','verify':'--verify-model','redteam':'--redteam-model','judge':'--judge-model'}
                model_args=[v for role,flag in flags.items() if models.get(role) for v in (flag,models[role])]
                started=subprocess.run(['bash',str(repo/'run.sh'),str(source),'--run-dir',str(run),*model_args],cwd=repo,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            if started.returncode:raise RuntimeError('本轮启动失败，请查看轮次日志')
            begin=time.monotonic()
            while True:
                status=read(Path(str(run)+'.meta')/'status.json',{})
                pid_file=Path(str(run)+'.meta')/'supervisor.pid';alive=False
                if pid_file.exists():
                    try:
                        pid=int(pid_file.read_text().strip());os.kill(pid,0)
                        stat=Path(f'/proc/{pid}/stat');alive=not stat.exists() or stat.read_text().split()[2]!='Z'
                    except (ValueError,ProcessLookupError,FileNotFoundError):pass
                if status.get('state') in ('success','completed','partial','failed','timeout','stopped') and not alive:break
                if time.monotonic()-begin>wall:
                    subprocess.run(['bash',str(repo/'run.sh'),'--stop',str(run)],cwd=repo,timeout=60)
                    raise TimeoutError('本轮超过控制器时限，已请求停止')
                time.sleep(poll)
            recovery=Path(str(run)+'-recovery')
            effective=recovery if Path(str(recovery)+'.meta/status.json').exists() else run
            bank.feedback(effective,project);published=[];evaluations=[]
            if (repo/'.claude/agents/stage-skill-learner.md').exists():learn(effective,project,repo)
            advancement=read(effective/'rsi/stage-learning-evaluation.json') or bank.advance(project);evaluations=advancement['results']
            published=[cid for key,cid in bank.active().items() if before_round.get(key)!=cid]
            state['rounds'].append({'index':index+1,'run_dir':str(run),'feedback_run_dir':str(effective),'state':status.get('state'),'evaluations':evaluations,'published':published})
            write(root/'status.json',state)
            stale=0 if published else stale+1
            if stale>=patience:state['status']='no_improvement';break
        else:state['status']='completed'
    except BaseException as exc:state.update(status='stopped' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc));raise
    finally:
        state['ended_at']=now();write(root/'status.json',state)
        (lock/'pid').unlink(missing_ok=True);lock.rmdir()
    return state

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--project',required=True);p.add_argument('--rounds',type=int,default=3);p.add_argument('--patience',type=int,default=2);a=p.parse_args()
    if not 1<=a.rounds<=100 or a.patience<1:p.error('轮数须为 1—100，停止阈值须为正数')
    print(json.dumps(cycle(a.source,a.project,a.rounds,a.patience),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
