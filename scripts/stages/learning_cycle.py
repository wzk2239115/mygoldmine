#!/usr/bin/env python3
"""有停止条件的 01—08 迭代控制器；不假设每一轮必然改善。"""
import argparse
import json
import os
import subprocess
import signal
import time
import uuid
import itertools
from pathlib import Path
from skill_bank import SkillBank, ROOT, now, read, write, identifier
from learn_round import learn

def cycle(source,project,rounds=3,patience=2,wall=108000,repo=ROOT,poll=5,cycle_id=None,claim_token=None,continuous=False,cooldown=300):
    repo=Path(repo);bank=SkillBank(repo);identifier(project)
    source=Path(source).resolve()
    if source.name!=project:raise ValueError('项目名必须与现有运行入口的源码目录名一致')
    lock=repo/'runs'/f'.learning-cycle-{project}.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    if claim_token:
        if not cycle_id or read(lock/'claim.json',{}).get('id')!=claim_token or cycle_id!=claim_token:
            raise ValueError('循环锁凭据不匹配')
    else:
        if (repo/'runs'/f'.node-retry-{project}.lock').exists():
            raise ValueError('该项目正在执行节点重跑')
        try:lock.mkdir()
        except FileExistsError:raise ValueError('该项目已有学习循环，请检查循环状态或遗留锁')
    (lock/'pid').write_text(str(os.getpid()))
    root=repo/'rsi/stage-skills/cycles'/(cycle_id or uuid.uuid4().hex);root.mkdir(parents=True,exist_ok=True)
    write(lock/'claim.json',{'id':root.name})
    state={'id':root.name,'project':project,'status':'running','started_at':now(),'rounds':[],'max_rounds':rounds,'patience':patience,'continuous':continuous,'cooldown_seconds':cooldown};write(root/'status.json',state)
    stale=0
    try:
        for index in (itertools.count() if continuous else range(rounds)):
            if (root/'stop').exists():state['status']='stopped';break
            before_round=bank.active()
            state['current_round']=index+1;write(root/'status.json',state)
            run=repo/'runs'/project/f'learning-{root.name}-{index+1}'
            with (root/f'round-{index+1}.log').open('w') as log:
                models=read(repo/'config/stage-models.json',{})
                flags={'audit':'--model','environment':'--env-model','visual':'--visual-model','verify':'--verify-model','redteam':'--redteam-model','judge':'--judge-model'}
                model_args=[v for role,flag in flags.items() if models.get(role) for v in (flag,models[role])]
                native=repo/'ui/server/claude-workflows.mjs'
                use_native=native.exists() and os.environ.get('GOLDMINE_NATIVE_WORKFLOW','1')!='0'
                if continuous and not use_native:raise RuntimeError('持续循环要求原生工作流，不允许恢复为旧执行方式')
                if use_native:
                    options={'runDir':str(run),'source':str(source),'project':project,'models':models,'cycleId':root.name}
                    command=[os.environ.get('NODE_BIN','node'),str(native),'--run',json.dumps(options)]
                else:
                    command=['bash',str(repo/'run.sh'),str(source),'--run-dir',str(run),*model_args]
                if use_native:
                    child=subprocess.Popen(command,cwd=repo,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:
                        started=subprocess.CompletedProcess(command,child.wait(timeout=wall))
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGTERM)
                        try:child.wait(timeout=45)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid,signal.SIGKILL);child.wait()
                        raise TimeoutError('本轮原生工作流超过控制器时限，已停止')
                else:
                    started=subprocess.run(command,cwd=repo,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            if started.returncode:
                if run.exists():
                    from exploration import feedback
                    feedback(repo,run,run,project,reports=[])
                raise RuntimeError('本轮工作流失败，请查看轮次日志；未自动重复失败任务')
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
            if status.get('state') in ('stopped','timeout'):
                state['status']='stopped';break
            recovery=Path(str(run)+'-recovery')
            effective=recovery if Path(str(recovery)+'.meta/status.json').exists() else run
            bank.feedback(effective,project);published=[];evaluations=[]
            if not use_native and (repo/'.claude/agents/stage-skill-learner.md').exists():learn(effective,project,repo)
            if use_native:
                attempts=sorted(Path(str(run)+'.meta/node-retries/learner').glob('*/attempt.json'),key=lambda f:f.stat().st_mtime)
                latest=read(attempts[-1],{}) if attempts else {}
                advancement=read(Path(latest.get('workspace',str(run)))/'rsi/stage-learning-evaluation.json') or {'results':[]}
            else:
                advancement=read(effective/'rsi/stage-learning-evaluation.json') or bank.advance(project)
            evaluations=advancement['results']
            published=[cid for key,cid in bank.active().items() if before_round.get(key)!=cid]
            state['rounds'].append({'index':index+1,'run_dir':str(run),'feedback_run_dir':str(effective),'state':status.get('state'),'evaluations':evaluations,'published':published,'exploration':advancement.get('exploration')})
            write(root/'status.json',state)
            stale=0 if published or advancement.get('interesting') else stale+1
            if (root/'stop').exists():state['status']='stopped';break
            if not continuous and stale>=patience:state['status']='no_improvement';break
            if continuous:
                state['waiting_until']=time.time()+cooldown
                state['wait_reason']='本轮有探索进展或项目试用，继续观察；不代表稳定发布' if advancement.get('interesting') else '本轮没有稳定发布，保留当前技能版本继续探索' if not published else '等待下一轮'
                write(root/'status.json',state)
                while time.time()<state['waiting_until'] and not (root/'stop').exists():
                    time.sleep(min(5,max(0,state['waiting_until']-time.time())))
                state.pop('waiting_until',None)
                if (root/'stop').exists():state['status']='stopped';break
        else:state['status']='completed'
    except BaseException as exc:state.update(status='stopped' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc));raise
    finally:
        state['ended_at']=now();write(root/'status.json',state)
        (lock/'pid').unlink(missing_ok=True);(lock/'claim.json').unlink(missing_ok=True);lock.rmdir()
    return state

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--project',required=True);p.add_argument('--rounds',type=int,default=3);p.add_argument('--patience',type=int,default=2);p.add_argument('--cycle-id');p.add_argument('--claim-token');p.add_argument('--continuous',action='store_true');p.add_argument('--cooldown',type=int,default=300);a=p.parse_args()
    if not 1<=a.rounds<=100 or a.patience<1 or a.cooldown<1:p.error('轮数须为 1—100，停止阈值须为正数')
    print(json.dumps(cycle(a.source,a.project,a.rounds,a.patience,cycle_id=a.cycle_id,claim_token=a.claim_token,continuous=a.continuous,cooldown=a.cooldown),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
