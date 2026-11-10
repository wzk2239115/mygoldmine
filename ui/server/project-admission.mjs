import {fileURLToPath} from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import {spawn,spawnSync} from 'node:child_process';

function update(repo,action,id,project,file) {
 const args=Object.entries({repo,action,id,project,file,pid:String(process.pid)}).flatMap(([k,v])=>['--'+k,v]);
 const result=spawnSync(process.env.PYTHON || (fs.existsSync(path.join(path.dirname(process.execPath),'python3'))?path.join(path.dirname(process.execPath),'python3'):'python3'),[fileURLToPath(new URL('../../scripts/workflow/project_admission.py',import.meta.url)),...args],{encoding:'utf8',timeout:15000});
 if(result.error || result.status!==0)throw Error(result.error?.message || result.stderr || '项目队列不可用');
 return JSON.parse(result.stdout);
}
export async function awaitProjectSlot(repo,id,project,file,{cancelled=()=>false,onStatus=()=>{}}={}) {
 while(!cancelled()) {
  const status=update(repo,'acquire',id,project,file);onStatus(status);
  if(status.status==='active')return;
  await new Promise(resolve=>setTimeout(resolve,2000));
 }
 throw Error('排队任务已停止');
}
export function releaseProjectSlot(repo,id,project,file){return update(repo,'release',id,project,file);}


export function recoverProjectQueue(repo) {
 let data;try{data=JSON.parse(fs.readFileSync(path.join(repo,'.runtime/state/project-admission/queue.json'),'utf8'));}catch{return;}
 for(const ticket of data.tickets || []) {
  let token;try{const parts=fs.readFileSync('/proc/'+ticket.pid+'/stat','utf8').split(') ')[1].split(' ');token=parts[0]==='Z'?null:parts[19];}catch{}
  if(token && token===ticket.token)continue;
  if(ticket.status!=='queued' || !path.resolve(ticket.file).startsWith(path.join(repo,'runs')+path.sep))continue;
  let state;try{state=JSON.parse(fs.readFileSync(ticket.file,'utf8'));}catch{continue;}
  const workflow=state.engine==='claude-workflow';
  if(state.repoRoot!==repo || state.status!=='running')continue;
  const fd=fs.openSync(path.join(path.dirname(ticket.file),'queue-recovery.log'),'a');
  const child=spawn(process.execPath,[path.join(repo,'ui/server',workflow?'claude-workflows.mjs':'node-retries.mjs'),workflow?'--coordinate':'--worker',ticket.file],{cwd:repo,detached:true,stdio:['ignore',fd,fd]});
  fs.closeSync(fd);child.on('error',()=>{});child.unref();
 }
}
