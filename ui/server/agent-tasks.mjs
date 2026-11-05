import fs from 'node:fs';
import path from 'node:path';
import {nodeAttempts} from './node-retries.mjs';
import {listAgenticTraces} from './agentic-traces.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
export function agentTasks(run) {
 const attempt=nodeAttempts(run.runDir,'redteam-agent').at(-1);
 const root=path.join(attempt?.workspace || run.runDir,'redteam');
 const summary=read(path.join(root,'summary.json')) || {};
 const selection=read(path.join(root,attempt?'agent-selection.json':'candidates.json'));
 const report=read(path.join(run.runDir,'audit-report.json')) || {};
 const titles=new Map((report.findings || report.vulnerabilities || []).map(item=>[item.id || item.finding_id,item.title]));
 const results=new Map((summary.results || []).map(item=>[item.id,item]));
 const selected=selection?.candidates || summary.results || [];
 const active=attempt?attempt.status==='running':Boolean(run.isLive);
 const traces=listAgenticTraces(run,'redteam-agent');
 const tasks=selected.map(value=>{
  const candidate=typeof value==='string'?{id:value}:value;
  const saved=attempt?read(path.join(root,'tasks',`${candidate.id}.json`)):null;
  const result=results.get(candidate.id);
  let runDir=saved?.run_dir || result?.run_dir;
  if(attempt && !runDir) {
   const ready=selected.filter(item=>item.status==='ready');
   const position=ready.findIndex(item=>item.id===candidate.id);
   if(position>=0)runDir=path.join(root,'agent-runs',run.project,`agent-retry-${String(attempt.id).slice(0,8)}-${String(position+1).padStart(2,'0')}`);
  }
  const trace=runDir?traces.find(item=>item.path===path.join(runDir,'agent.jsonl')):null;
  const repair=attempt?read(path.join(root,'runner-repairs',candidate.id,'runner-repair.json')):null;
  const status=result?.status || saved?.status || '';
  const failed=/error|timeout|unhealthy|invalid/.test(status);
  let state=status.startsWith('blocked')?'blocked':failed?'failed':result?'completed':saved?.state || (trace?'running':'queued');
  if(!active && ['running','queued'].includes(state))state='interrupted';
  const captured=Boolean(result?.captured || status==='flag_captured' || status==='judge_approved');
  return {id:candidate.id,title:candidate.title || titles.get(candidate.id) || candidate.id,state,
   label:repair?.status==='repairing'?'正在修复运行依赖':captured?'已捕获随机标记':status.startsWith('blocked')?'受阻':state==='completed'?'未捕获随机标记':'',
   reason:result?.error || saved?.error || candidate.reason || '',traceId:trace?.id || '',captured};
 });
 return {attemptId:attempt?.id || 'original',tasks,concurrency:summary.concurrency || null,
  processedCount:tasks.filter(task=>!['running','queued'].includes(task.state)).length,selectedCount:tasks.length};
}
