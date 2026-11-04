import fs from 'node:fs';
import path from 'node:path';
import {nodeAttempts} from './node-retries.mjs';
const read = file => {try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const validId = id => /^[A-Za-z0-9._-]{1,100}$/.test(id) && !['.','..'].includes(id);
function batch(run) {
 const attempt=nodeAttempts(run.runDir,'verify').at(-1);
 return {root:path.join(attempt?.workspace || run.runDir,'verify/agent'),attempt,
  active:attempt?attempt.status==='running':run.isLive};
}
export function verifyTasks(run) {
 const {root,attempt,active}=batch(run);
 const summary=read(path.join(root,'summary.json'));
 const directory=path.join(root,'tasks');
 let tasks=fs.existsSync(directory)?fs.readdirSync(directory).filter(name=>name.endsWith('.json')).map(name=>read(path.join(directory,name))).filter(Boolean):[];
 const legacy=!tasks.length;
 if(legacy) {
  tasks=Array.isArray(summary?.findings)?summary.findings:[];
  if(!tasks.length && fs.existsSync(path.join(root,'inputs'))) tasks=fs.readdirSync(path.join(root,'inputs')).filter(validId).map(id=>{
   const input=read(path.join(root,'inputs',id,'finding.json')) || {};
   const report=read(path.join(root,id,'verify-report.json'));
   return {finding_id:id,title:input.title || id,severity:input.severity,source_index:input.selection_index,verdict:report?.verdict,reason:report?.reason,
    state:report?'completed':active?'running':'interrupted'};
  });
 }
 const labels={confirmed:'已确认',rejected:'已排除',inconclusive:'待定',blocked:'受阻',queued:'排队',running:'运行中',cancelled:'已中断',interrupted:'已中断',failed:'失败',completed:'已结束'};
 tasks=tasks.filter(item=>validId(item.finding_id || item.id || '')).map(item=>{
  const id=item.finding_id || item.id;
  let state=item.state || 'completed';
  if(!active && ['running','queued'].includes(state))state='interrupted';
  const report=read(path.join(root,id,'verify-report.json'));
  const verdict=item.verdict || report?.verdict || '';
  return {id,title:item.title || item.entry?.title || id,severity:item.severity || item.entry?.severity || '',state,verdict,label:labels[state==='completed'?verdict || state:state] || '已结束',
   reason:item.reason || report?.reason || '',sourceIndex:item.entry?.index ?? item.source_index ?? 0,
   hasReport:Boolean(report),traceId:attempt?`${attempt.id}-verify-${id}-agent`:id};
 }).sort((a,b)=>a.sourceIndex-b.sourceIndex || a.id.localeCompare(b.id));
 const number=(value,fallback=0)=>Number.isInteger(Number(value)) && Number(value)>=0 ? Number(value) : fallback;
 const finished=tasks.filter(task=>!['running','queued'].includes(task.state));
 const verdicts=['confirmed','rejected','inconclusive','blocked'];
 const counts=Object.fromEntries(verdicts.map(verdict=>[verdict,number(summary?.counts?.[verdict],finished.filter(task=>task.verdict===verdict).length)]));
 const report=read(path.join(attempt?.workspace || run.runDir,'audit-report.json'));
 const processedCount=number(summary?.processed,Math.max(finished.length,summary?Object.values(counts).reduce((sum,count)=>sum+count,0):0));
 return {selectedCount:number(summary?.selected,Math.max(tasks.length,processedCount)),processedCount,counts,
  reportTotal:Array.isArray(report?.findings)?report.findings.length:null,
  concurrency:Number(summary?.concurrency || (!legacy && read(path.join(directory,`${tasks[0]?.id}.json`))?.concurrency) || 1),
  legacy,attemptId:attempt?.id || '',tasks};
}
export function verifyTaskReport(run,id,attemptId='') {
 if(!validId(id))return null;
 const current=batch(run);
 if((current.attempt?.id || '')!==attemptId)return null;
 if(!verifyTasks(run).tasks.some(task=>task.id===id))return null;
 return read(path.join(current.root,id,'verify-report.json'));
}
