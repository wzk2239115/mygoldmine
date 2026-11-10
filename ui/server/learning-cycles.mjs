import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';

const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});const temp=file+'.tmp';fs.writeFileSync(temp,JSON.stringify(value,null,2));fs.renameSync(temp,file);};
const fail=message=>{throw Object.assign(new Error(message),{status:409});};
const valid=id=>typeof id==='string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(id);
function paths(repo,project) {
  if(!valid(project))fail('项目编号无效');
  return {lock:path.join(repo,'runs',`.learning-cycle-${project}.lock`),guard:path.join(repo,'runs',`.node-retry-${project}.lock`),root:path.join(repo,'rsi/stage-skills/cycles')};
}
function completedRounds(repo,project) {
 const root=path.join(repo,'runs',project);if(!fs.existsSync(root))return 0;
 const full=['environment','orchestrator','visual','verify','redteam-lab','redteam-agent','judge','learner'];
 return fs.readdirSync(root).filter(name=>name.endsWith('.meta')).filter(name=>{
  const folder=path.join(root,name,'workflows');if(!fs.existsSync(folder))return false;
  return fs.readdirSync(folder).some(id=>{
   const row=read(path.join(folder,id,'state.json'));
   return row?.project===project && path.resolve(row.runDir || '')===path.join(root,name.slice(0,-5)) && row.engine==='claude-workflow' && row.status==='completed'
    && full.every((node,index)=>row.steps?.[index]===node && row.receipts?.[index]?.node===node) && row.receipts.length===8;
  });
 }).length;
}
export function cycleStatus(repo,project) {
  const {lock,root}=paths(repo,project);
  const claim=read(path.join(lock,'claim.json'));
  const rows=fs.existsSync(root)?fs.readdirSync(root).filter(valid).map(id=>read(path.join(root,id,'status.json'))).filter(row=>row?.project===project).sort((a,b)=>String(b.started_at).localeCompare(String(a.started_at))):[];
  const state=(claim && read(path.join(root,claim.id,'status.json'))) || rows[0];
  const completed_rounds=completedRounds(repo,project);
  if(!state)return {active:false,status:'not_started',completed_rounds};
  const active=Boolean(claim?.id===state.id && ['queued','running','stopping'].includes(state.status));
  return {...state,active,completed_rounds,stopRequested:fs.existsSync(path.join(root,state.id,'stop'))};
}
export function startCycle({repoRoot,run,liveRuns=[],rounds=8,patience=2,continuous=false,cooldown=300,launch=spawn}) {
  if(!Number.isInteger(rounds)||rounds<1||rounds>100 || !Number.isInteger(patience)||patience<1||patience>100)fail('循环轮数与停止阈值必须在 1 到 100 之间');
  if(typeof continuous!=='boolean' || !Number.isInteger(cooldown) || cooldown<1 || cooldown>86400)fail('循环模式或间隔无效');
  const {lock,guard,root}=paths(repoRoot,run.project);
  fs.mkdirSync(path.dirname(lock),{recursive:true});
  try{fs.mkdirSync(guard);}catch{fail('该项目正在执行节点任务，请等待结束');}
  let claimed=false;
  const id=randomUUID();
  try {
    if(run.isLive || liveRuns.some(item=>item.project===run.project && item.isLive))fail('该项目正在审计，请等待本轮结束');
    const meta=read(`${run.runDir}.meta/status.json`);
    const source=meta?.target;
    if(!source || !fs.existsSync(source) || !fs.statSync(source).isDirectory() || path.basename(source)!==run.project)fail('缺少有效项目源码目录');
    try{fs.mkdirSync(lock);}catch{fail('该项目已有学习循环或遗留锁，请先检查状态');}
    claimed=true;
    const folder=path.join(root,id);
    const state={id,project:run.project,status:'queued',started_at:new Date().toISOString(),rounds:[],max_rounds:rounds,patience,continuous,cooldown_seconds:cooldown};
    write(path.join(folder,'status.json'),state);write(path.join(lock,'claim.json'),{id});
    const python=process.env.RSI_PYTHON || path.join(path.dirname(process.execPath),'python3');
    const fd=fs.openSync(path.join(folder,'controller.log'),'a');
    let child;
    try{child=launch(python,['scripts/stages/learning_cycle.py','--source',source,'--project',run.project,'--rounds',String(rounds),'--patience',String(patience),'--cycle-id',id,'--claim-token',id,...(continuous?['--continuous']:[]),'--cooldown',String(cooldown)],{cwd:repoRoot,detached:true,stdio:['ignore',fd,fd]});}finally{fs.closeSync(fd);}
    child.on('error',error=>{write(path.join(folder,'status.json'),{...state,status:'failed',error:error.message});if(read(path.join(lock,'claim.json'))?.id===id)fs.rmSync(lock,{recursive:true,force:true});});
    child.on('exit',code=>{
      const file=path.join(folder,'status.json');const latest=read(file);
      if(latest && ['queued','running','stopping'].includes(latest.status)){write(file,{...latest,status:'failed',error:`循环进程提前结束：${code}`});if(read(path.join(lock,'claim.json'))?.id===id)fs.rmSync(lock,{recursive:true,force:true});}
    });
    child.unref();
    return {...state,active:true};
  }catch(error){if(claimed && (!read(path.join(lock,'claim.json')) || read(path.join(lock,'claim.json'))?.id===id))fs.rmSync(lock,{recursive:true,force:true});throw error;}
  finally{fs.rmSync(guard,{recursive:true,force:true});}
}
export function stopCycle(repo,project) {
  const state=cycleStatus(repo,project);
  if(!state.active)fail('没有正在运行的学习循环');
  const {root}=paths(repo,project);
  fs.writeFileSync(path.join(root,state.id,'stop'),'stop after current round\n');
  return {...state,stopRequested:true};
}

// A successful repair ending in learning resumes only its own failed cycle.
export function resumeAfterLearning(repo,workflow,launch=spawn) {
 if(workflow.status!=='completed' || !workflow.receipts?.some(r=>r.node==='learner'))return null;
 const match=path.basename(workflow.runDir).match(/^learning-(.+)-(\d+)$/);
 if(!match || !valid(match[1]))return null;
 const {lock,guard,root}=paths(repo,workflow.project);
 const folder=path.join(root,match[1]),file=path.join(folder,'status.json'),state=read(file);
 if(!state || state.project!==workflow.project || state.status!=='failed' ||
    fs.existsSync(path.join(folder,'stop')) || fs.existsSync(lock) || fs.existsSync(guard))return null;
 const index=Number(match[2]),rows=state.rounds || [];
 if(index!==state.current_round || rows.length!==index-1 || index>state.max_rounds)return null;
 const meta=read(workflow.runDir+'.meta/status.json'),source=meta?.target;
 if(!source || path.basename(source)!==workflow.project || !fs.existsSync(source))return null;
 try {fs.mkdirSync(guard);}catch{return null;}
 let claimed=false;
 try {
  fs.mkdirSync(lock);claimed=true;write(path.join(lock,'claim.json'),{id:state.id});
  state.recovery_history=[...(state.recovery_history || []),{error:state.error,ended_at:state.ended_at,workflow:workflow.id}];
  state.rounds=[...rows,{index,run_dir:workflow.runDir,state:'partial',recovered_by:workflow.id,evaluations:[],published:[]}];
  delete state.error;delete state.ended_at;
  if(index===state.max_rounds){state.status='completed';state.ended_at=new Date().toISOString();write(file,state);fs.rmSync(lock,{recursive:true,force:true});return state;}
  state.status='queued';state.resumed_at=new Date().toISOString();write(file,state);
  const python=process.env.RSI_PYTHON || path.join(path.dirname(process.execPath),'python3');
  const fd=fs.openSync(path.join(folder,'controller.log'),'a');
  let child;
  try {child=launch(python,['scripts/stages/learning_cycle.py','--resume','--source',source,'--project',workflow.project,'--cycle-id',state.id,'--claim-token',state.id],{cwd:repo,detached:true,stdio:['ignore',fd,fd]});}
  finally {fs.closeSync(fd);}
  child.on('error',error=>{
   write(file,{...state,status:'failed',error:error.message});
   if(read(path.join(lock,'claim.json'))?.id===state.id)fs.rmSync(lock,{recursive:true,force:true});
  });
  child.unref();return state;
 } catch(error) {
  if(claimed && read(path.join(lock,'claim.json'))?.id===state.id)fs.rmSync(lock,{recursive:true,force:true});
  throw error;
 } finally {fs.rmSync(guard,{recursive:true,force:true});}
}
