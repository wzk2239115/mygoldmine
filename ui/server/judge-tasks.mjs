import fs from 'node:fs';
import path from 'node:path';
import {nodeAttempts} from './node-retries.mjs';
import {listAgenticTraces} from './agentic-traces.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
export function judgeTasks(run) {
 const attempt=nodeAttempts(run.runDir,'judge').at(-1);
 const execution=attempt?null:nodeAttempts(run.runDir,'redteam-agent').at(-1);
 const workspace=attempt?.workspace || execution?.workspace || run.runDir;
 const summary=read(path.join(workspace,attempt?'judge/summary.json':'redteam/summary.json')) || {};
 const selection=attempt?read(path.join(workspace,'judge/selection.json')):null;
 const results=new Map((summary.results || []).map(item=>[item.id,item]));
 const candidates=selection?.candidates || summary.results || [];
 const traces=listAgenticTraces(run,'judge');
 const active=attempt?attempt.status==='running':Boolean(run.isLive);
 const stage=read(`${run.runDir}.meta/pipeline-stage.json`);
 const labels={approved:'通过',rejected:'未通过',needs_review:'需要复核'};
 const tasks=candidates.map(candidate=>{
  const result=results.get(candidate.id);
  const directory=candidate.run_dir;
  const trace=directory?traces.find(item=>item.path===path.join(directory,'judge.log')):null;
  const diagnostic=directory?traces.find(item=>item.path===path.join(directory,'judge-worker.log')):null;
  // A new execution batch cannot borrow verdicts from the original batch.
  const verdict=directory && !execution?read(path.join(directory,'judge.json')):null;
  const status=attempt || !execution?result?.status || '':'';
  const judged=!execution && (result?.judge_returncode!=null || verdict);
  const evidence=directory?read(path.join(directory,'result.json')):null;
  const captured=Boolean(evidence?.result?.captured);
  let state=judged?'completed':captured || attempt?'queued':'blocked';
  let label=labels[verdict?.verdict] || (status==='judge_approved'?'通过':status==='judge_rejected'?'未通过':status==='judge_needs_review'?'需要复核':'');
  if(status==='judge_error' || status==='judge_timeout'){state='failed';label='执行错误';}
  if(active && !judged && (attempt?summary.current===candidate.id:!execution && stage?.node==='judge' && stage?.candidate===candidate.id))state='running';
  if(!active && ['queued','running'].includes(state))state='interrupted';
  if(result?.delivery_status==='missing'){state='failed';label='交付未完成';}
  const reason=result?.delivery_status==='missing'?result.delivery_error || '缺少有效审核交付':state==='blocked'?'红队尚未交付已捕获随机标记的完整证据':state==='interrupted'?'本批次尚未完成此候选的审核':'';
  return {id:candidate.id,title:candidate.title || (directory?read(path.join(directory,'finding.json'))?.title:'') || candidate.id,state,label,reason,traceId:execution?'':trace?.id || diagnostic?.id || ''};
 });
 return {attemptId:attempt?.id || (execution?`execution-${execution.id}`:'original'),tasks,mode:attempt?'serial':'unspecified',selectedCount:tasks.length,processedCount:tasks.filter(task=>['completed','failed'].includes(task.state)).length};
}
