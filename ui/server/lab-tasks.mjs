import fs from 'node:fs';
import path from 'node:path';
import {nodeAttempts} from './node-retries.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const safe=id=>typeof id==='string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(id);
function batch(run) {
 const attempt=nodeAttempts(run.runDir,'redteam-lab').at(-1);
 return {attempt,root:attempt?path.join(attempt.workspace,'redteam'):path.join(run.runDir,'redteam/batch/construction'),active:attempt?attempt.status==='running':run.isLive};
}
export function labTasks(run) {
 const {attempt,root,active}=batch(run), summary=read(path.join(root,'summary.json')) || {};
 const selection=read(path.join(root,'selection.json'));
 let candidates=selection?.candidates || [];
 if(!candidates.length && !attempt)candidates=read(path.join(run.runDir,'redteam/candidates.json'))?.candidates || [];
 const gate=selection || (!attempt ? read(path.join(run.runDir,'redteam/selection.json')) : null);
 const report=read(path.join(attempt?.workspace || run.runDir,'audit-report.json'));
 const originals=new Map((report?.findings || report?.vulnerabilities || []).filter(item=>item && typeof item==='object').map(item=>[item.id || item.finding_id,item]));
 const fallback=attempt?summary:read(path.join(run.runDir,'redteam/summary.json')) || summary;
 if(!attempt)for(const result of fallback.results || [])if(!candidates.some(task=>task.id===result.id))candidates=[...candidates,{id:result.id}];
 const tasks=candidates.filter(task=>safe(task.id) && (!task.project || task.project===run.project)).map((candidate,index)=>{
  const saved=read(path.join(root,'tasks',`${attempt?'':run.project+'--'}${candidate.id}.json`));
  const result=(fallback.results || []).find(item=>item.id===candidate.id);
  let state=saved?.state || (result?'completed':fallback.current===candidate.id?'running':active?'queued':'interrupted');
  if(!active && ['running','queued'].includes(state))state='interrupted';
  const lab=attempt?path.join(root,'labs',candidate.id):path.join(root,'labs',run.project,candidate.id);
  const status=saved?.status || result?.status;
  const deliveryStatus=saved?.delivery_status || result?.delivery_status;
  const label=deliveryStatus==='missing'?'缺少交付':state==='queued'?'排队':state==='running'?'构建中':state==='interrupted'?'已中断':status==='built' || (result?.scenario && !['build_failed','blocked_no_finding','blocked_no_lab'].includes(status))?'可用':'受阻';
  return {deliveryStatus,id:candidate.id,title:candidate.title || originals.get(candidate.id)?.title || candidate.id,state,status,label,reason:saved?.error || result?.error || (deliveryStatus==='missing'?'未取得有效交付回执；其他成员继续执行':''),
   hasReport:['scenario.json','BLOCKED.md','lab-report.md'].some(name=>fs.existsSync(path.join(lab,name))),
   traceId:attempt?`${attempt.id}-redteam-lab-${candidate.id}-agent`:saved?`lab-${candidate.id}`:result?`${candidate.id}-${String((fallback.results || []).indexOf(result)+1).padStart(2,'0')}`:`lab-${candidate.id}`,sourceIndex:index};
 });
 return {tasks,excluded:gate?.excluded || [],blueAttemptId:gate?.blue_attempt_id || '',blueHandoffCount:candidates.filter(item=>item.blue_handoff).length,attemptId:attempt?.id || '',concurrency:summary.concurrency || 1,legacy:!summary.concurrency,
  selectedCount:tasks.length,processedCount:tasks.filter(task=>!['running','queued'].includes(task.state)).length,
  running:tasks.filter(task=>task.state==='running').length,ready:tasks.filter(task=>task.label==='可用').length,blocked:tasks.filter(task=>['受阻','缺少交付'].includes(task.label)).length,deliveryMissing:tasks.filter(task=>task.deliveryStatus==='missing').length};
}
function text(file) {try{return fs.statSync(file).size>256000?'文件较大，请查看执行轨迹':fs.readFileSync(file,'utf8');}catch{return '';}}
export function labTaskReport(run,id,attemptId='') {
 const current=batch(run);
 if(!safe(id) || (current.attempt?.id || '')!==attemptId || !labTasks(run).tasks.some(task=>task.id===id))return null;
 const root=current.attempt?path.join(current.root,'labs',id):path.join(current.root,'labs',run.project,id);
 const report=text(path.join(root,'lab-report.md')), blocked=text(path.join(root,'BLOCKED.md')),scenario=read(path.join(root,'scenario.json'));
 return report || blocked || scenario ? {id,report,blocked,scenario}:null;
}
