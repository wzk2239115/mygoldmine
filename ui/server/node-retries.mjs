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
export function startNodeRetry({repoRoot,run,node,models}) {
  const reason=retryEligibility(run,node);if(reason)fail(reason);
  const lock=path.join(repoRoot,'runs',`.node-retry-${run.project}.lock`);
  try { fs.mkdirSync(lock); } catch { fail('该项目已有节点重跑任务，请稍后再试'); }
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
    const job={id,node,project:run.project,runId:run.runId,repoRoot,root,workspace,lock,model,status:'running',startedAt:new Date().toISOString(),source:status.target,image:status.env_image};
    write(path.join(root,'attempt.json'),job);
    const fd=fs.openSync(path.join(root,'worker.log'),'a');
    const child=spawn(process.execPath,[fileURLToPath(import.meta.url),'--worker',path.join(root,'attempt.json')],{cwd:repoRoot,detached:true,stdio:['ignore',fd,fd]});
    child.on('error', error => {
      write(path.join(root,'attempt.json'), {...job,status:'failed',resultStatus:'failed',error:error.message,endedAt:new Date().toISOString()});
      fs.rmSync(lock,{recursive:true,force:true});
    });
    fs.closeSync(fd);child.unref();
    return {id,node,status:'running'};
  } catch(error) { fs.rmSync(lock,{recursive:true,force:true});throw error; }
}
async function worker(file) {
  const job=read(file);let code=1;
  try {
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
    else args=['scripts/verify/phase4_verify_agent.sh','--project',job.project,'--run-dir',job.workspace,'--source',job.source,'--image',job.image,'--model',job.model,'--output',path.join(job.workspace,'verify/agent')];
    code=await new Promise((resolve,reject)=>{const child=spawn('bash',args,{cwd:job.repoRoot,stdio:'inherit'});child.on('error',reject);child.on('close',c=>resolve(c ?? 1));});
    if(job.node==='visual') {
      const summary=read(path.join(job.workspace,'visual-rendered/visual-summary.json'));
      job.resultStatus=summary?.steps?.render_attack_scenes_agentic?.ok?'completed':summary?.scene_count?'degraded':'failed';
    } else {
      const summary=read(path.join(job.workspace,'verify/agent/summary.json'));
      job.resultStatus=code!==0 || !summary?'failed':summary.status==='blocked'?'blocked':summary.status==='partial'?'degraded':summary.status==='failed'?'failed':'completed';
    }
  } catch(error) { job.error=error.message; }
  finally { job.status=code===0?'completed':'failed';job.exitCode=code;job.endedAt=new Date().toISOString();write(file,job);fs.rmSync(job.lock,{recursive:true,force:true});
    const originalRun=path.resolve(job.root,'../../..').replace(/\.meta$/,'');
    const collector=path.join(job.repoRoot,'scripts/stages/skill_bank.py');
    if(fs.existsSync(collector)) await new Promise(resolve=>{const child=spawn('python3',[collector,'collect','--project',job.project,'--root',originalRun],{cwd:job.repoRoot,stdio:'ignore'});child.on('error',resolve);child.on('close',resolve);}); }
}
if(process.argv[2]==='--worker')await worker(process.argv[3]);
