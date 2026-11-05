import fs from 'node:fs';
import path from 'node:path';
import {nodeAttempts} from './node-retries.mjs';
import {listAgenticTraces} from './agentic-traces.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
export function sceneTasks(run) {
 const attempt=nodeAttempts(run.runDir,'visual').at(-1);
 const workspace=attempt?.workspace || run.runDir;
 const root=path.join(workspace,'visual/agentic');
 const active=attempt?attempt.status==='running':Boolean(run.isLive);
 const report=read(path.join(workspace,'audit-report.json')) || {};
 const titles=new Map((report.findings || report.vulnerabilities || []).map(item=>[item.id || item.finding_id,item.title]));
 const traces=listAgenticTraces(run,'visual');
 const entries=fs.existsSync(root)?fs.readdirSync(root,{withFileTypes:true}).filter(entry=>entry.isDirectory()):[];
 const tasks=entries.map(entry=>{
  const task=read(path.join(root,entry.name,'task.json'));
  if(!task || task.finding_id!==entry.name)return null;
  const log=path.join(root,entry.name,'agent.log');
  const trace=traces.find(item=>item.path===log);
  const reused=!trace && task.image_out && task.director_out && fs.existsSync(task.image_out) && fs.existsSync(task.director_out);
  let state=trace || reused?'completed':active?'running':'interrupted';
  let label=reused?'复用已有场景':'';
  if(trace) {
   const prefix=fs.readFileSync(log,'utf8').slice(0,200);
   const code=prefix.match(/^# returncode\s+(-?\d+)/);
   if(code && Number(code[1])!==0){state='failed';label='执行失败';}
   else label='已结束';
  }
  return {id:entry.name,title:titles.get(entry.name) || task.attack?.title || entry.name,state,label,traceId:trace?.id || ''};
 }).filter(Boolean);
 return {attemptId:attempt?.id || 'original',tasks,concurrency:1,selectedCount:tasks.length,processedCount:tasks.filter(task=>!['queued','running'].includes(task.state)).length};
}
