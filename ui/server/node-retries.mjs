import {awaitProjectSlot,releaseProjectSlot} from './project-admission.mjs';
import {judgeCandidates,prepareJudgeRetry,runJudgeRetry} from './judge-retry.mjs';
import {labCandidates,prepareLabRetry,runLabRetry} from './redteam-lab-retry.mjs';
import {agentCandidates,prepareAgentRetry,runAgentRetry} from './redteam-agent-retry.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const read = file => { try { return JSON.parse(fs.readFileSync(file,'utf8')); } catch { return null; } };
const write = (file,data) => { const temp=`${file}.tmp`;fs.writeFileSync(temp,JSON.stringify(data,null,2));fs.renameSync(temp,file); };
const fail = message => { const error=new Error(message);error.status=409;throw error; };
export function nodeAttempts(runDir,node) {
  const root=path.join(`${runDir}.meta`,'node-retries',node);
  if(!fs.existsSync(root))return [];
  return fs.readdirSync(root).map(id=>read(path.join(root,id,'attempt.json'))).filter(Boolean).sort((a,b)=>a.startedAt.localeCompare(b.startedAt));
}
export const supportsNodeRetry = node => ['visual','verify','redteam-lab','redteam-agent','judge','learner'].includes(node);
export function retryEligibility(run,node) {
  if(!supportsNodeRetry(node))return '该节点暂不支持独立重跑，请使用项目重跑';
  if(fs.existsSync(path.join(path.resolve(run.runDir,'../../..'),'runs',`.learning-cycle-${run.project}.lock`)))return '该项目正在执行学习循环';
  if(run.isLive)return '项目正在运行，请等待本次流程结束';
  const status=read(`${run.runDir}.meta/status.json`) || {};
  const report=read(path.join(run.runDir,'audit-report.json'));
  if(!Array.isArray(report?.findings))return '缺少有效的审计报告';
  if(node==='verify' && (!status.env_image || !status.target))return '缺少环境镜像或源码信息';
  if(node==='redteam-lab') {
    if(!status.target || !fs.existsSync(status.target) || !fs.statSync(status.target).isDirectory())return '缺少可用的项目源码目录';
    try {if(!labCandidates(run).length)return '没有可重跑的红队候选';}catch(error){return error.message;}
  }
  if(node==='redteam-agent') {
    if(nodeAttempts(run.runDir,'redteam-lab').at(-1)?.status==='running')return '场景构建正在重跑，请等待结束';
    try {if(!agentCandidates(run).some(candidate=>candidate.status==='ready'))return '没有可用红队场景，请先重跑场景构建';}catch(error){return error.message;}
  }
  if(node==='judge') {
    try {if(!judgeCandidates(run).length)return '没有已捕获随机标记且证据完整的红队结果，请先完成红队执行';}catch(error){return error.message;}
  }
  return '';
}
export function startNodeRetry({repoRoot,run,node,models,cascade=false,inheritedLock=null}) {
  const reason=retryEligibility(run,node);if(reason)fail(reason);
  const lock=path.join(repoRoot,'runs',`.node-retry-${run.project}.lock`);
  if(inheritedLock!==lock) { try { fs.mkdirSync(lock); } catch { fail('该项目已有节点重跑任务，请稍后再试'); } }
  const id=randomUUID();const root=path.join(`${run.runDir}.meta`,'node-retries',node,id);
  try {
    fs.mkdirSync(root,{recursive:true});
    const workspace=path.join(root,'output');fs.mkdirSync(workspace);
    fs.copyFileSync(path.join(run.runDir,'audit-report.json'),path.join(workspace,'audit-report.json'));
    const status=read(`${run.runDir}.meta/status.json`) || {};
    if(node==='redteam-lab')prepareLabRetry(run,workspace);
    if(node==='redteam-agent')prepareAgentRetry(run,workspace);
    if(node==='judge')prepareJudgeRetry(run,workspace);
    const model=models[node==='redteam-lab'||node==='redteam-agent'?'redteam':node] || models.audit;
    const job={id,node,cascade,models,project:run.project,runId:run.runId,repoRoot,root,workspace,lock,model,status:'running',startedAt:new Date().toISOString(),source:status.target,image:status.env_image};
    write(path.join(root,'attempt.json'),job);
    const fd=fs.openSync(path.join(root,'worker.log'),'a');
    const native=path.join(repoRoot,'ui/server/claude-workflows.mjs');
    const useNative=cascade && node!=='visual' && process.env.GOLDMINE_NATIVE_WORKFLOW!=='0' && fs.existsSync(native);
    const child=spawn(process.execPath,[useNative?native:fileURLToPath(import.meta.url),useNative?'--chain':'--worker',path.join(root,'attempt.json')],{cwd:repoRoot,detached:true,stdio:['ignore',fd,fd]});
    child.on('error', error => {
      write(path.join(root,'attempt.json'), {...job,status:'failed',resultStatus:'failed',error:error.message,endedAt:new Date().toISOString()});
      fs.rmSync(lock,{recursive:true,force:true});
    });
    fs.closeSync(fd);child.unref();
    return {id,node,status:'running'};
  } catch(error) { fs.rmSync(lock,{recursive:true,force:true});throw error; }
}
export async function worker(file) {
  const job=read(file);let code=1;
  try {
    if(!job.workflowOwner)await awaitProjectSlot(job.repoRoot,job.id,job.project,file,{onStatus:admission=>{job.admission=admission;write(file,job);}});
    if(job.node==='learner') {
      const source=path.resolve(job.root,'../../..').replace(/\.meta$/,'');
      const bundledPython=path.join(path.dirname(process.execPath),'python3');
      const learnerPython=process.env.RSI_PYTHON || process.env.PYTHON || (fs.existsSync(bundledPython)?bundledPython:'python3');
      code=await new Promise((resolve,reject)=>{const child=spawn(learnerPython,['scripts/stages/retry_learning.py','--source',source,'--output',job.workspace,'--project',job.project],{cwd:job.repoRoot,env:{...process.env,RSI_LEARNER_MODEL:job.model},stdio:'inherit'});child.on('error',reject);child.on('close',value=>resolve(value ?? 1));});
      job.resultStatus=code===0?(read(path.join(job.workspace,'rsi/learning-retry.json'))?.status || 'completed'):'failed';return;
    }
    if(job.node==='judge') {job.resultStatus=await runJudgeRetry(job);code=0;return;}
    if(job.node==='redteam-lab') {job.resultStatus=await runLabRetry(job);code=0;return;}
    if(job.node==='redteam-agent') {job.resultStatus=await runAgentRetry(job,Number(process.env.REDTEAM_AGENT_JOBS)||10);code=0;return;}
    let args;
    if(job.node==='visual')args=['scripts/mine/visual_report.sh','--project',job.project,'--run-dir',job.workspace,'--model',job.model];
    else args=['scripts/verify/phase4_verify_agent.sh','--project',job.project,'--run-dir',job.workspace,'--source',job.source,'--image',job.image,'--model',job.model,'--drain','--severity','critical,high,medium,low,info','--output',path.join(job.workspace,'verify/agent')];
    code=await new Promise((resolve,reject)=>{const child=spawn('bash',args,{cwd:job.repoRoot,stdio:'inherit'});child.on('error',reject);child.on('close',c=>resolve(c ?? 1));});
    if(job.node==='visual') {
      const summary=read(path.join(job.workspace,'visual-rendered/visual-summary.json'));
      job.resultStatus=summary?.steps?.render_attack_scenes_agentic?.ok?'completed':summary?.scene_count?'degraded':'failed';
    } else {
      const summary=read(path.join(job.workspace,'verify/agent/summary.json'));
      job.resultStatus=code!==0 || !summary?'failed':summary.status==='blocked'?'blocked':summary.status==='partial'?'degraded':summary.status==='failed'?'failed':'completed';
    }
  } catch(error) { job.error=error.message; }
  finally { if(!job.workflowOwner)releaseProjectSlot(job.repoRoot,job.id,job.project,file);
    job.admission={...job.admission,status:'released'};
    job.status=code===0?'completed':'failed';job.exitCode=code;job.endedAt=new Date().toISOString();write(file,job);
    const originalRun=path.resolve(job.root,'../../..').replace(/\.meta$/,'');
    const collector=path.join(job.repoRoot,'scripts/stages/skill_bank.py');
    if(fs.existsSync(collector)) await new Promise(resolve=>{const child=spawn('python3',[collector,'collect','--project',job.project,'--root',originalRun],{cwd:job.repoRoot,stdio:'ignore'});child.on('error',resolve);child.on('close',resolve);});
    let chained=false;
    try {
      if(job.cascade && code===0 && ['verify','redteam-lab','redteam-agent','judge'].includes(job.node)) {
        const run={runDir:originalRun,project:job.project,runId:job.runId,isLive:false};
        let next='learner';
        if(job.node==='verify') {
          try{if(labCandidates(run).length)next='redteam-lab';}catch(error){job.downstreamNotice=error.message;}
        }
        if(job.node==='redteam-lab') {
          if(agentCandidates(run).some(candidate=>candidate.status==='ready'))next='redteam-agent';
          else job.downstreamNotice='无可用场景，保留受阻原因并进入08学习';
        }
        if(job.node==='redteam-agent') {
          if(judgeCandidates(run).length)next='judge';
          else job.downstreamNotice='没有已捕获且来源完整的证据，跳过07，继续08学习';
        }
        const child=startNodeRetry({repoRoot:job.repoRoot,run,node:next,models:job.models || {},cascade:true,inheritedLock:job.lock});
        job.next=child;write(file,job);chained=true;
      }
    } catch(error){job.downstreamError=error.message;write(file,job);}
    finally {if(!chained && !job.workflowOwner)fs.rmSync(job.lock,{recursive:true,force:true});}
  }
}
if(process.argv[2]==='--worker')await worker(process.argv[3]);

export async function followExistingRetry(file) {
  const initial=read(file);if(!initial || !['redteam-agent','judge'].includes(initial.node))throw Error('不支持接续此节点');
  const marker=path.join(initial.root,'continuation.json');
  try {const fd=fs.openSync(marker,'wx');fs.closeSync(fd);}catch{return;}
  write(marker,{status:'waiting',pid:process.pid});
  for(let i=0;i<18000;i++) {
    const job=read(file);
    if(job?.status==='running' || fs.existsSync(job?.lock || initial.lock)){await new Promise(resolve=>setTimeout(resolve,5000));continue;}
    if(job?.next){write(marker,{status:'already_chained',next:job.next});return;}
    if(job?.exitCode!==0){write(marker,{status:'blocked',reason:'上游任务未正常完成'});return;}
    try {
      const run={project:job.project,runId:job.runId,runDir:path.resolve(job.root,'../../..').replace(/\.meta$/,''),isLive:false};
      const next=job.node==='redteam-agent' && judgeCandidates(run).length?'judge':'learner';
      const models=read(path.join(job.repoRoot,'config/stage-models.json')) || {};
      const child=startNodeRetry({repoRoot:job.repoRoot,run,node:next,models,cascade:true});
      if(next==='learner' && job.node==='redteam-agent')job.downstreamNotice='没有已捕获且来源完整的证据，跳过07，继续08学习';
      job.next=child;write(file,job);write(marker,{status:'started',next:child});return;
    }catch(error){write(marker,{status:'blocked',reason:error.message});return;}
  }
  write(marker,{status:'blocked',reason:'等待接续超过时限，未启动后续任务'});
}
if(process.argv[2]==='--follow')await followExistingRetry(process.argv[3]);
