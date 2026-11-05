import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const self=fileURLToPath(import.meta.url);
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
function write(file,value){const temp=`${file}.${process.pid}.tmp`;fs.writeFileSync(temp,JSON.stringify(value,null,2));fs.renameSync(temp,file);}
function identity(pid){try{const stat=fs.readFileSync(`/proc/${pid}/stat`,'utf8').split(') ')[1].split(' ');return stat[0]==='Z'?null:stat[19];}catch{return null;}}
export function signalProcessTree(pid,signal,owned=null){
  if(!owned){
    owned=new Map();
    const visit=current=>{
      const start=identity(current);if(!start)return;
      owned.set(current,start);
      try{for(const child of fs.readFileSync('/proc/'+current+'/task/'+current+'/children','utf8').trim().split(/\s+/).filter(Boolean))visit(Number(child));}catch{}
    };visit(pid);
  }
  for(const [current,start] of [...owned].reverse())if(identity(current)===start){try{process.kill(current,signal);}catch{}}
  return owned;
}
export function taskLive(task){return Boolean(task?.pid && task.processStart && identity(task.pid)===task.processStart);}
export function taskStatus(file){
  const task=read(file);if(!task)throw Error('缺少任务登记文件');
  if(task.status==='running'&&!taskLive(task)){task.status='failed';task.error='任务进程已中断，未重复启动';task.endedAt=new Date().toISOString();write(file,task);}
  if(task.status==='queued'&&Date.now()-Date.parse(task.startedAt)>10000){task.status='failed';task.error='任务进程未能启动';write(file,task);}
  return task;
}
export function launchTask(directory,spec){
  const fingerprint=createHash('sha256').update(JSON.stringify(spec)).digest('hex');
  const file=path.join(directory,'task.json');
  try{fs.mkdirSync(directory,{recursive:false});}catch(error){
    if(error.code!=='EEXIST')throw error;
    const task=read(file);
    if(!task)throw Error('任务正在登记，请稍后查询');
    if(task.fingerprint!==fingerprint)throw Error('已有任务输入不匹配，拒绝重复执行');
    return {file,...taskStatus(file)};
  }
  const task={...spec,fingerprint,status:'queued',startedAt:new Date().toISOString()};write(file,task);
  const fd=fs.openSync(path.join(directory,'supervisor.log'),'a');
  const child=spawn(process.execPath,[self,'--worker',file],{cwd:spec.cwd,detached:true,stdio:['ignore',fd,fd]});fs.closeSync(fd);
  task.pid=child.pid;task.processStart=identity(child.pid);write(file,task);
  child.on('error',error=>write(file,{...task,status:'failed',error:error.message}));child.unref();
  return {file,...task};
}
export async function waitTask(file,{pollMs=1000,cancelled=()=>false}={}){
  for(;;){
    const task=taskStatus(file);
    if(!['queued','running'].includes(task.status))return task;
    if(cancelled())throw Error('等待已取消');
    await new Promise(resolve=>setTimeout(resolve,pollMs));
  }
}
export function stopTask(file){const task=read(file);if(taskLive(task))process.kill(task.pid,'SIGTERM');}
async function run(file){
  let task=read(file),child,stopping=false,killTimer,cleanup;
  for(let n=0;task?.pid!==process.pid&&n<200;n++){await new Promise(r=>setTimeout(r,10));task=read(file);}
  if(task?.pid!==process.pid)throw Error('任务启动凭据未登记');
  task={...task,status:'running',pid:process.pid,processStart:identity(process.pid),heartbeatAt:new Date().toISOString()};write(file,task);
  const stop=()=>{
    if(stopping)return;stopping=true;
    const owned=child?.pid?signalProcessTree(child.pid,'SIGTERM'):new Map();
    cleanup=new Promise(resolve=>{killTimer=setTimeout(()=>{signalProcessTree(child?.pid,'SIGKILL',owned);resolve();},1000);});
  };
  process.on('SIGTERM',stop);process.on('SIGINT',stop);
  const heartbeat=setInterval(()=>{task.heartbeatAt=new Date().toISOString();write(file,task);},1000);
  const deadline=setTimeout(()=>{task.error='任务超过登记时限';stop();},task.timeoutMs);
  try{
    const fd=fs.openSync(path.join(path.dirname(file),'output.log'),'a');
    const code=await new Promise((resolve,reject)=>{
      child=spawn(task.program,task.args,{cwd:task.cwd,detached:true,env:{...process.env,...task.envFlags,GOLDMINE_DURABLE_TASK:file},stdio:['ignore',fd,fd]});fs.closeSync(fd);
      task.childPid=child.pid;write(file,task);child.on('error',reject);child.on('close',value=>resolve(value??1));
    });
    task.exitCode=code;task.status=!stopping&&(task.successCodes || [0]).includes(code)?'completed':'failed';
    if(stopping&&!task.error)task.error='任务已停止';
  }catch(error){task.status='failed';task.error=error.message;}
  finally{clearInterval(heartbeat);if(cleanup)await cleanup;clearTimeout(deadline);clearTimeout(killTimer);task.endedAt=new Date().toISOString();write(file,task);process.off('SIGTERM',stop);process.off('SIGINT',stop);}
}
async function cli(){
  if(process.argv[2]==='--worker')return run(process.argv[3]);
  if(process.argv[2]==='--start-spec'){
    const directory=path.resolve(process.argv[3]);fs.mkdirSync(path.dirname(directory),{recursive:true});
    console.log(JSON.stringify(launchTask(directory,JSON.parse(process.argv[4]))));return;
  }
  if(process.argv[2]==='--wait-task'){
    const task=await waitTask(process.argv[3]);console.log(JSON.stringify(task));process.exitCode=task.status==='completed'?0:1;return;
  }

  if(process.argv[2]==='--start-build'){
    const [root,out,...args]=process.argv.slice(3);
    if(process.env.ENV_BUILD_VERIFY_ONLY==='1')throw Error('当前仅做验收，不允许重新构建');
    const base=path.join(out,'.build-tasks');fs.mkdirSync(base,{recursive:true});
    const existing=read(path.join(base,'current.json'));
    if(existing){const active=taskStatus(existing.file);if(['queued','running'].includes(active.status)){console.log(JSON.stringify({status:active.status,taskFile:existing.file,reused:true}));return;}}
    const dockerfile=fs.existsSync(path.join(out,'Dockerfile'))?fs.readFileSync(path.join(out,'Dockerfile'),'utf8'):'';
    const id=createHash('sha256').update(JSON.stringify({args,dockerfile,owner:process.env.ENV_BUILD_TASK_OWNER || ''})).digest('hex').slice(0,24);
    const task=launchTask(path.join(base,id),{program:'bash',args:[path.join(root,'scripts/env/build_env.sh'),...args],cwd:root,timeoutMs:(Number(process.env.ENV_BUILD_TIMEOUT)||3600)*1000+60000,successCodes:[0,10,20],owner:process.env.ENV_BUILD_TASK_OWNER || '',envFlags:{ENV_BUILD_TASK_WORKER:'1'}});
    write(path.join(base,'current.json'),{file:task.file});console.log(JSON.stringify({status:task.status,taskFile:task.file,output:path.join(path.dirname(task.file),'output.log')}));return;
  }
  if(process.argv[2]==='--stop-build'){
    const pointer=read(path.join(process.argv[3],'.build-tasks/current.json'));
    if(!pointer)throw Error('没有已登记构建');
    const task=read(pointer.file);
    if(!process.env.ENV_BUILD_TASK_OWNER || task?.owner!==process.env.ENV_BUILD_TASK_OWNER)throw Error('不能停止其他任务的构建');
    stopTask(pointer.file);console.log(JSON.stringify({status:'stopping',taskFile:pointer.file}));return;
  }
  if(['--build-status','--wait-build'].includes(process.argv[2])){
    const current=read(path.join(process.argv[3],'.build-tasks/current.json'));
    if(!current){process.exitCode=3;return;}
    const task=process.argv[2]==='--wait-build'?await waitTask(current.file):taskStatus(current.file);
    console.log(JSON.stringify(task));process.exitCode=task.status==='completed'?(task.exitCode || 0):['queued','running'].includes(task.status)?0:1;return;
  }
  throw Error('缺少任务操作');
}
if(process.argv[1]&&path.resolve(process.argv[1])===self)cli().catch(error=>{console.error(error.message);process.exitCode=1;});
