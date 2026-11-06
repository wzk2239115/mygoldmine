import {launchTask,taskStatus,waitTask,stopTask,taskLive} from './durable-task.mjs';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createHash,randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {labCandidates,prepareLabRetry} from './redteam-lab-retry.mjs';
import {agentCandidates,prepareAgentRetry} from './redteam-agent-retry.mjs';
import {judgeCandidates,prepareJudgeRetry} from './judge-retry.mjs';
import {reportProject,runtimeEnvironment,verificationAttachments} from './delivery-contract.mjs';

const self=fileURLToPath(import.meta.url);
const repo=path.resolve(path.dirname(self),'../..');
export const stages=['environment','orchestrator','visual','verify','redteam-lab','redteam-agent','judge','learner'];
const titles=['01 环境构建','02 安全审计编排','03 攻击场景设计','04 蓝队验证','05 红队场景构建','06 红队执行','07 独立审核','08 经验学习'];
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});const tmp=`${file}.${process.pid}.tmp`;fs.writeFileSync(tmp,JSON.stringify(value,null,2));fs.renameSync(tmp,file);};
function save(file,state) {
  write(file,state);
  const mirror=path.join(state.runDir+'.meta','workflows',state.id,'state.json');
  if(path.resolve(mirror)!==path.resolve(file)) {
    write(mirror,state);
    if(state.coordinatorPid)fs.writeFileSync(state.runDir+'.meta/supervisor.pid',String(state.coordinatorPid));
    const raw=path.join(path.dirname(file),'raw.jsonl'),target=path.join(path.dirname(mirror),'raw.jsonl');
    if(fs.existsSync(raw)&&!fs.existsSync(target))fs.linkSync(raw,target);
  }
}
const quote=value=>"'"+String(value).replaceAll("'","'\\''")+"'";
const hash=file=>{const digest=createHash('sha256'),fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW),buffer=Buffer.alloc(65536);try{let n;while((n=fs.readSync(fd,buffer,0,buffer.length,null)))digest.update(buffer.subarray(0,n));return digest.digest('hex');}finally{fs.closeSync(fd);}};
const under=(file,root)=>file===root || file.startsWith(root+path.sep);

// File links are evidence metadata, not permission to follow arbitrary paths.
function artifactError(message,code='artifact_contract') {
  return Object.assign(new Error(message),{code});
}
function checkedLink(file,boundary) {
  const link=fs.readlinkSync(file);
  if(path.isAbsolute(link) || !under(path.resolve(path.dirname(file),link),boundary))throw artifactError('产物符号链接超出交付目录：'+file,'artifact_link_outside');
  let target;
  try {target=fs.realpathSync(file);}
  catch(error){throw artifactError('产物符号链接悬空或循环：'+file,error.code==='ELOOP'?'artifact_link_cycle':'artifact_link_missing');}
  if(!under(target,boundary) || fs.realpathSync(boundary)!==boundary)throw artifactError('产物符号链接目标超出交付目录：'+file,'artifact_link_outside');
  if(!fs.statSync(target).isFile())throw artifactError('产物目录链接不能作为文件证据交付：'+file,'artifact_link_directory');
  return {link,target};
}
// No display limits: all regular artifacts and safe file links are represented.
export function manifest(roots,{verification=false}={}) {
  const files=[],references=[];
  function visit(file,boundary) {
    let stat;try{stat=fs.lstatSync(file);}catch{throw artifactError('产物已缺失：'+file,'artifact_missing');}
    if(stat.isSymbolicLink()){
      const {link,target}=checkedLink(file,boundary);
      files.push({file,type:'symlink',boundary,link,target,size:fs.statSync(target).size,sha256:hash(target)});return;
    }
    if(stat.isDirectory()){
      const runtime=runtimeEnvironment(file);
      if(runtime){const config=path.join(file,'pyvenv.cfg');files.push({file:config,type:'runtime-environment',runtimeRoot:file,runtime,size:fs.statSync(config).size,sha256:hash(config)});return;}
      for(const name of fs.readdirSync(file).sort())visit(path.join(file,name),boundary);return;
    }
    if(!stat.isFile())throw artifactError('产物类型无效：'+file,'artifact_type');
    files.push({file,size:stat.size,sha256:hash(file)});
    if(verification && path.basename(file)==='verify-report.json' && [path.dirname(file),path.dirname(path.dirname(file))].includes(boundary))references.push({file,boundary});
  }
  for(const root of [...new Set(roots)].sort()){
    const absolute=path.resolve(root);
    let stat;try{stat=fs.lstatSync(absolute);}catch{throw artifactError('产物已缺失：'+absolute,'artifact_missing');}
    const boundary=fs.realpathSync(stat.isDirectory()?absolute:path.dirname(absolute));
    visit(absolute,boundary);
  }
  for(const item of references)verificationAttachments(item.file,item.boundary);
  return files;
}
export function verifyManifest(files) {
  for(const item of files) {
    try {
      if(item.type==='runtime-environment'){
        const actual=runtimeEnvironment(item.runtimeRoot);
        if(!actual || actual.sha256!==item.runtime?.sha256 || hash(item.file)!==item.sha256)throw Error('runtime snapshot changed');
      }else if(item.type==='symlink'){
        if(!fs.lstatSync(item.file).isSymbolicLink())throw Error('link changed');
        const link=checkedLink(item.file,item.boundary);
        if(link.link!==item.link || link.target!==item.target || hash(link.target)!==item.sha256)throw Error('link or content changed');
      }else if(!fs.existsSync(item.file) || fs.lstatSync(item.file).isSymbolicLink() || hash(item.file)!==item.sha256)throw Error('content changed');
    }catch(error){throw artifactError('上游产物已改变：'+item.file+'；'+error.message,error.code || 'artifact_changed');}
  }
}
export function reusableAttempt(state,node) {
  const root=path.join(state.runDir+'.meta','node-retries',node);
  if(!fs.existsSync(root))return null;
  const rows=fs.readdirSync(root).map(id=>({file:path.join(root,id,'attempt.json'),job:read(path.join(root,id,'attempt.json'))})).filter(item=>item.job).sort((a,b)=>String(a.job.startedAt).localeCompare(String(b.job.startedAt)));
  const latest=rows.at(-1);if(!latest)return null;
  const {job,file}=latest;
  if(job.status!=='completed' || job.resultStatus==='failed' || job.workflowOwner!==state.id || job.node!==node || job.project!==state.project || job.runId!==path.basename(state.runDir))return null;
  if(path.resolve(job.root || '')!==path.dirname(file) || path.resolve(job.workspace || '')!==path.join(path.dirname(file),'output'))return null;
  const input=read(path.join(job.workspace,'workflow-inputs.json'));
  const report=path.join(state.runDir,'audit-report.json');
  const expected=[...new Map(state.receipts.flatMap(item=>item.outputs).map(item=>[item.file,item])).values()];
  if(input?.workflow!==state.id || input.node!==node || input.report_sha256!==hash(report) || JSON.stringify(input.artifacts)!==JSON.stringify(expected))return null;
  if(hash(path.join(job.workspace,'audit-report.json'))!==hash(report))return null;
  return file;
}

function load(file) {
  const state=read(file);
  if(!state || state.repoRoot!==repo || !stages.includes(state.start) || !under(path.resolve(state.runDir),path.join(repo,'runs')))throw Error('执行计划无效');
  if(read(path.join(state.lock,'workflow-owner.json'))?.id!==state.id)throw Error('项目锁凭据不匹配');
  return state;
}
function alive(pid) {
  if(!Number.isInteger(pid)||pid<2)return false;
  try{process.kill(pid,0);return fs.readFileSync(`/proc/${pid}/stat`,'utf8').split(') ')[1]?.[0]!=='Z';}catch{return false;}
}
function terminateTree(pid,signal='SIGTERM') {
  if(!Number.isInteger(pid)||pid<2||pid===process.pid)return;
  try {
    const children=fs.readFileSync(`/proc/${pid}/task/${pid}/children`,'utf8').trim().split(/\s+/).filter(Boolean).map(Number);
    for(const child of children)terminateTree(child,signal);
    process.kill(pid,signal);
  }catch{}
}
function command(cmd,args,{cwd=repo,env=process.env,log,timeout=86400000,onSpawn=()=>{},handoffFile=null}={}) {
  return new Promise((resolve,reject)=>{
    const fd=log?fs.openSync(log,'a'):null;
    const child=spawn(cmd,args,{cwd,env,stdio:fd===null?'inherit':['ignore',fd,fd]});
    if(fd!==null)fs.closeSync(fd);
    onSpawn(child);
    let expired=false,handoffAt=null;
    const handoff=handoffFile?setInterval(()=>{
      if(read(handoffFile)?.activeTask){handoffAt ??= Date.now();if(Date.now()-handoffAt>15000)terminateTree(child.pid);}
    },1000):null;
    const timer=setTimeout(()=>{expired=true;terminateTree(child.pid);},timeout);
    child.on('error',error=>{clearTimeout(timer);clearInterval(handoff);reject(error);});
    child.on('close',code=>{clearTimeout(timer);clearInterval(handoff);if(expired)reject(Error('节点执行超过时限'));else resolve(code ?? 1);});
  });
}
const artifacts={visual:['visual-rendered'],verify:['verify/agent'],'redteam-lab':['redteam'],'redteam-agent':['redteam'],judge:['judge'],learner:['rsi']};
export function sourceReport(state) {
  const file=path.join(state.runDir,'audit-report.json');
  const report=read(file);
  const keys=['findings','vulnerabilities'].filter(key=>report && Object.hasOwn(report,key));
  if(!keys.length || keys.some(key=>!Array.isArray(report[key]) || report[key].some(item=>!item || typeof item!=='object' || Array.isArray(item))))throw Error('审计报告缺少有效的候选问题数组');
  if(keys.length===2 && JSON.stringify(report.findings)!==JSON.stringify(report.vulnerabilities))throw Error('审计报告的候选问题数组相互冲突');
  if(state.project)reportProject(report,state.project);
  return file;
}
export async function execute(state,node,file) {
  const index=stages.indexOf(node),receipt={node,delivery_schema_version:2,status:'completed',startedAt:new Date().toISOString(),inputs:[],outputs:[]};
  const prior=state.receipts.at(-1);
  for(const earlier of state.receipts)verifyManifest(earlier.outputs);
  receipt.inputs=[...new Map(state.receipts.flatMap(item=>item.outputs).map(item=>[item.file,item])).values()];
  const model=state.models[node==='environment'?'environment':node==='orchestrator'?'audit':node.startsWith('redteam')?'redteam':node] || state.models.audit;
  const run={project:state.project,runId:path.basename(state.runDir),runDir:state.runDir,isLive:false};
  const log=path.join(path.dirname(file),`${node}.log`);
  if(node==='environment') {
    const code=await command('bash',['scripts/env/phase0_env.sh',state.source,'--project',state.project,'--meta-dir',state.runDir+'.meta','--base-image',state.image,'--model',model],{log});
    const env=read(path.join(repo,'env',state.project,'env-manifest.json'));
    if(![0,10].includes(code)||!env?.image)throw Error('环境构建受阻，停止正式流程');
    if(await command('docker',['image','inspect',env.image],{log})!==0)throw Error('环境镜像不可用');
    state.image=env.image;
    receipt.status=code===10?'degraded':'completed';
    receipt.outputs=manifest([path.join(repo,'env',state.project,'env-manifest.json'),state.runDir+'.meta/env-phase.json']);
  } else if(node==='orchestrator') {
    const flags=Object.entries({audit:'--model',environment:'--env-model',visual:'--visual-model',verify:'--verify-model',redteam:'--redteam-model',judge:'--judge-model'}).flatMap(([role,flag])=>state.models[role]?[flag,state.models[role]]:[]);
    const code=await command('bash',['run.sh','--supervise','--target',state.source,'--project',state.project,'--run-dir',state.runDir,'--image',state.image,'--skip-env','--skip-visual','--skip-verify','--skip-redteam','--skip-mining-repair',...flags],{log,env:{...process.env,WORKFLOW_ENV_IMAGE:state.image}});
    const recovered=state.runDir+'-recovery';
    if(!fs.existsSync(path.join(state.runDir,'audit-report.json')) && fs.existsSync(path.join(recovered,'audit-report.json'))) {
      state.recoveredFrom=state.runDir;state.runDir=recovered;save(file,state);
    }
    if(code!==0 && !fs.existsSync(path.join(state.runDir,'audit-report.json')))throw Error('审计编排失败');
    sourceReport(state);
    if(await command(process.env.PYTHON || 'python3',['scripts/mine/check_report.py','--report',path.join(state.runDir,'audit-report.json'),'--project',state.project,'--output',path.join(state.runDir,'report-quality.json'),'--fail-missing','--fail-language'],{log})!==0)throw Error('审计产物未通过完整性检查');
    const status=read(state.runDir+'.meta/status.json') || {};
    write(state.runDir+'.meta/status.json',{...status,env_image:state.image,target:state.source});
    receipt.status=code===0?'completed':'degraded';
    receipt.outputs=manifest(['audit-report.json','audit-report.md','task-artifacts'].map(name=>path.join(state.runDir,name)).filter(fs.existsSync));
  } else {
    const report=sourceReport(state);
    if(state.reportHash && hash(report)!==state.reportHash)throw Error('总报告已改变，禁止继续旧执行计划');
    state.reportHash=hash(report);
    let reason='';
    if(node==='redteam-lab'){try{if(!labCandidates(run).length)reason='没有蓝队已确认且产物完整的候选';}catch(error){if(/没有蓝队|没有可重跑/.test(error.message))reason=error.message;else throw error;}}
    if(node==='redteam-agent'&&!agentCandidates(run).some(item=>item.status==='ready'))reason='没有通过场景检查的候选';
    if(node==='judge'&&!judgeCandidates(run).length)reason='没有已捕获随机标记且来源完整的证据';
    if(reason){if(state.initialJob && node===state.start){const job=read(state.initialJob);write(state.initialJob,{...job,status:'completed',resultStatus:'skipped',exitCode:0,downstreamNotice:reason,endedAt:new Date().toISOString()});}receipt.status='skipped';receipt.reason=reason;receipt.outputs=prior?.outputs || manifest([report]);return receipt;}
    let job;
    if(state.activeAttempt)job=read(state.activeAttempt);
    else if(state.initialJob && node===state.start)job=read(state.initialJob);
    else {
      const id=randomUUID(),root=path.join(state.runDir+'.meta','node-retries',node,id),workspace=path.join(root,'output');
      fs.mkdirSync(workspace,{recursive:true});fs.copyFileSync(report,path.join(workspace,'audit-report.json'));
      if(node==='redteam-lab')prepareLabRetry(run,workspace);
      if(node==='redteam-agent')prepareAgentRetry(run,workspace);
      if(node==='judge')prepareJudgeRetry(run,workspace);
      job={id,node,project:state.project,runId:run.runId,repoRoot:repo,root,workspace,lock:state.lock,model,status:'running',startedAt:new Date().toISOString(),source:state.source,image:state.image};
    }
    if(hash(path.join(job.workspace,'audit-report.json'))!==hash(report))throw Error('节点输入报告与总报告不一致');
    write(path.join(job.workspace,'workflow-inputs.json'),{workflow:state.id,node,report_sha256:state.reportHash,artifacts:receipt.inputs});
    if(job.node!==node)throw Error('未完成节点与当前计划不一致');
    job.cascade=false;job.workflowOwner=state.id;
    const attempt=path.join(job.root,'attempt.json');write(attempt,job);
    state.activeAttempt=attempt;save(file,state);
    if(job.status==='running' && job.workerPid) {
      while(read(attempt)?.status==='running') {
        try{process.kill(job.workerPid,0);}catch{throw Error('节点进程中断，保留已有产物并停止后续节点');}
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
    } else if(job.status==='running') {
      await command(process.execPath,[path.join(repo,'ui/server/node-retries.mjs'),'--worker',attempt],{log:path.join(job.root,'worker.log'),onSpawn:child=>{job.workerPid=child.pid;write(attempt,job);}});
    }
    job=read(attempt);
    if(job.status!=='completed'||job.resultStatus==='failed')throw Error(job.error || `节点执行失败：${node}`);
    receipt.status=job.resultStatus || 'completed';receipt.attempt=attempt;
    const outputs=(artifacts[node] || []).map(name=>path.join(job.workspace,name)).filter(fs.existsSync);
    if(!outputs.length)throw Error(`节点缺少交付产物：${node}`);
    receipt.outputs=manifest([report,...outputs],{verification:node==='verify'});
    delete state.activeAttempt;
  }
  return receipt;
}
export async function step(file,node,executeNode=execute) {
  const state=load(file),expected=state.steps[state.receipts.length];
  // A repeated tool invocation returns the persisted receipt, never repeats the audit.
  const saved=state.receipts.find(item=>item.node===node);
  if(saved){verifyManifest(saved.outputs);return {node,status:saved.status};}
  if(expected!==node)throw Error('节点顺序与已登记计划不一致');
  const guard=file+'.step-lock';
  if(fs.existsSync(guard)) {
    const pid=read(path.join(guard,'owner.json'))?.pid;
    let alive=true;try{if(!pid)throw Error('missing');process.kill(pid,0);}catch{alive=false;}
    if(!alive)fs.rmSync(guard,{recursive:true,force:true});
  }
  fs.mkdirSync(guard);write(path.join(guard,'owner.json'),{pid:process.pid});
  try {
    state.current=node;save(file,state);
    write(state.runDir+'.meta/pipeline-stage.json',{stage:node,updated_at:new Date().toISOString()});
    const receipt=await executeNode(state,node,file);
    receipt.endedAt=new Date().toISOString();
    state.receipts.push(receipt);state.current=null;save(file,state);
    write(path.join(path.dirname(file),'receipts',node+'.json'),receipt);
    if(executeNode===execute && ['orchestrator','verify','redteam-agent','judge','learner'].includes(node)) {
      const code=await command(process.env.PYTHON || 'python3',['scripts/workflow/build_state.py'],{log:path.join(path.dirname(file),'candidate-index.log'),timeout:60000});
      if(code!==0)throw Error('节点已交付，但候选汇总更新失败，请查看候选汇总日志');
    }
    return {node,status:receipt.status};
  } catch(error) {state.error=error.message;state.failure={scope:String(error.code || '').startsWith('artifact_')?'artifact_contract':'stage_execution',code:error.code || 'stage_execution',retryOwner:String(error.code || '').startsWith('artifact_')?'workflow-delivery':'stage-executor'};save(file,state);throw error;}
  finally{fs.rmSync(guard,{recursive:true,force:true});}
}

export function requestStep(file,node) {
  const state=load(file),saved=state.receipts.find(item=>item.node===node);
  if(saved){verifyManifest(saved.outputs);return {node,status:saved.status};}
  if(state.steps[state.receipts.length]!==node)throw Error('节点顺序与已登记计划不一致');
  const directory=path.join(path.dirname(file),'tasks',node),taskFile=path.join(directory,'task.json');
  fs.mkdirSync(path.dirname(directory),{recursive:true});
  if(!fs.existsSync(taskFile)) {
    state.activeTask=taskFile;state.current=node;save(file,state);
    launchTask(directory,{program:process.execPath,args:[self,'--step',file,'--node',node],cwd:repo,timeoutMs:node==='environment'?10800000:93600000,successCodes:[0],envFlags:{STAGE_SKILL_BASELINE:state.baselineFile || '',ENV_BUILD_TASK_OWNER:state.id}});
  }
  const task=taskStatus(taskFile);
  if(task.status==='failed')throw Error(task.error || '节点任务执行失败');
  const receipt=read(file)?.receipts?.find(item=>item.node===node);
  if(task.status==='completed'){if(!receipt)throw Error('任务结束但缺少节点交付回执');verifyManifest(receipt.outputs);return {node,status:receipt.status};}
  return {node,status:'running'};
}

export function createState({runDir,source,project,models,image='mygoldmine:dev',start='environment',initialJob,lock,cycleId}) {
  runDir=path.resolve(runDir);
  if(!under(runDir,path.join(repo,'runs',project)) || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(project) || !stages.includes(start))throw Error('工作流参数无效');
  const cycle=path.join(repo,'runs',`.learning-cycle-${project}.lock`);
  if(fs.existsSync(cycle)&&read(path.join(cycle,'claim.json'))?.id!==cycleId)throw Error('该项目已有学习循环');
  const id=randomUUID();lock=lock || path.join(repo,'runs',`.node-retry-${project}.lock`);
  if(start==='environment' && fs.existsSync(runDir))throw Error('新一轮必须使用独立产物目录');
  fs.mkdirSync(path.dirname(lock),{recursive:true});
  if(!initialJob)fs.mkdirSync(lock);
  fs.mkdirSync(runDir,{recursive:true});
  const folder=path.join(runDir+'.meta','workflows',id);fs.mkdirSync(folder,{recursive:true});
  const file=path.join(folder,'state.json');
  const baselineFile=path.join(folder,'stage-skills-baseline.json');write(baselineFile,read(path.join(repo,'rsi/stage-skills/active.json')) || {});
  models={audit:'360-proxy/deepseek/deepseek-v4.1-flash',...models};
  const state={id,baselineFile,engine:'claude-workflow',status:'running',repoRoot:repo,runDir,source,project,models,image,start,steps:stages.slice(stages.indexOf(start)),receipts:[],lock,initialJob,startedAt:new Date().toISOString()};
  write(path.join(lock,'workflow-owner.json'),{id,file});save(file,state);
  if(start==='environment')write(runDir+'.meta/status.json',{project,target:source,env_image:image,state:'starting',run_dir:runDir,started_at:state.startedAt});
  return file;
}
export function resumeState(file) {
  const state=read(file);
  if(!state || state.repoRoot!==repo || !under(path.resolve(state.runDir),path.join(repo,'runs',state.project)) || !['failed','stopped'].includes(state.status))throw Error('只能恢复已失败或已停止的工作流');
  if(alive(state.coordinatorPid) || (state.activeTask && taskLive(read(state.activeTask))) || (state.activeAttempt && alive(read(state.activeAttempt)?.workerPid)))throw Error('工作流仍有活动任务，不能重复恢复');
  if(state.receipts.length>=state.steps.length)throw Error('没有需要恢复的节点');
  for(const receipt of state.receipts)verifyManifest(receipt.outputs);
  const lock=path.join(repo,'runs',`.node-retry-${state.project}.lock`);
  if(state.lock!==lock)throw Error('工作流锁路径无效');
  fs.mkdirSync(lock);
  try {
    const node=state.steps[state.receipts.length],directory=path.join(path.dirname(file),'tasks',node);
    const archive=path.join(path.dirname(file),'recovery-history',new Date().toISOString().replaceAll(':','-')+'-'+randomUUID());
    fs.mkdirSync(archive,{recursive:true});write(path.join(archive,'state.json'),state);
    if(fs.existsSync(directory))fs.renameSync(directory,path.join(archive,'task'));
    const reusable=reusableAttempt(state,node);
    if(reusable)state.activeAttempt=reusable;else delete state.activeAttempt;
    delete state.activeTask;delete state.waitingForTask;delete state.error;delete state.failure;delete state.endedAt;delete state.coordinatorPid;
    state.status='running';state.current=null;state.resumedAt=new Date().toISOString();
    write(path.join(lock,'workflow-owner.json'),{id:state.id,file});save(file,state);
    const status=read(state.runDir+'.meta/status.json') || {};
    write(state.runDir+'.meta/status.json',{...status,state:'running',workflow_id:state.id,updated_at:state.resumedAt});
    return state;
  } catch(error) {fs.rmSync(lock,{recursive:true,force:true});throw error;}
}
function stopOwnedBuild(state) {
  const pointer=read(path.join(repo,'env',state.project,'.build-tasks/current.json'));
  if(pointer && read(pointer.file)?.owner===state.id)stopTask(pointer.file);
  const workspace=state.activeAttempt?read(state.activeAttempt)?.workspace:null;
  if(workspace && fs.existsSync(workspace)){
    const walk=directory=>{
      for(const item of fs.readdirSync(directory,{withFileTypes:true})){
        const entry=path.join(directory,item.name);
        if(item.isDirectory())walk(entry);
        else if(item.name==='task.json' && entry.includes('/.stage-builds/') && read(entry)?.owner===state.id)stopTask(entry);
      }
    };walk(workspace);
  }
}
export async function coordinate(file) {
  let state=load(file),code=1;
  if(state.baselineFile)process.env.STAGE_SKILL_BASELINE=state.baselineFile;
  const folder=path.dirname(file),log=path.join(folder,'raw.jsonl');
  if(state.start==='environment'){state.coordinatorPid=process.pid;fs.writeFileSync(state.runDir+'.meta/supervisor.pid',String(process.pid));save(file,state);}
  let activePid=null,interrupted=false;
  const stop=()=>{interrupted=true;stopOwnedBuild(read(file) || state);const registered=read(file)?.activeTask;if(registered)stopTask(registered);terminateTree(activePid);const latest=read(file);if(latest?.activeAttempt)terminateTree(read(latest.activeAttempt)?.workerPid);};
  process.on('SIGTERM',stop);process.on('SIGINT',stop);
  try {
    let emptyAttempts=0;
    while(state.receipts.length<state.steps.length) {
      const args={steps:state.steps.slice(state.receipts.length).map(node=>({node,title:titles[stages.indexOf(node)]})),command:`${quote(process.execPath)} ${quote(self)} --request-step ${quote(file)}`};
    const instructions=fs.existsSync(path.join(repo,'.claude/skills/pipeline-workflow/SKILL.md'))?fs.readFileSync(path.join(repo,'.claude/skills/pipeline-workflow/SKILL.md'),'utf8'):'';
    const prompt='执行规范：\n'+instructions+'\n'+`Use the native Workflow tool to run the saved /goldmine-pipeline workflow with these exact args: ${JSON.stringify(args)}. Run the saved script unchanged; do not replace it with direct tool calls. Make exactly one saved Workflow call. A waiting result is normal: return immediately and let the host await its durable task. Do not poll, start a second workflow, or run audits yourself.`;
    code=await command(process.env.PYTHON || 'python3',['scripts/stages/claude_connection.py',state.models.audit || '',process.env.CLAUDE_BIN || 'claude','-p',prompt,'--output-format','stream-json','--verbose','--tools','Workflow,Bash,Read,Skill','--allowedTools','Workflow','Bash(echo *)',`Bash(${args.command} --node *)`,'Read','Skill','--permission-mode','dontAsk'],{log,timeout:7*86400000,handoffFile:file,onSpawn:child=>{activePid=child.pid;}});
      state=load(file);
      if(interrupted)throw Error('工作流已中断');
      if(state.activeTask) {
        const result=await waitTask(state.activeTask,{cancelled:()=>interrupted});
        state=load(file);delete state.activeTask;delete state.waitingForTask;
        if(result.status!=='completed')throw Error(result.error || state.error || `节点任务失败：${result.exitCode}`);
        if(!state.receipts.some(item=>item.node===state.current) && state.current)throw Error('任务结束但缺少节点交付回执');
        save(file,state);emptyAttempts=0;continue;
      }
      if(state.error)throw Error(state.error);
      if(state.receipts.length===state.steps.length)break;
      if(++emptyAttempts>=2)throw Error('原生工作流未启动登记的节点任务');
      state.continuations=(state.continuations || 0)+1;save(file,state);
    }
    if(!fs.readFileSync(log,'utf8').split('\n').some(line=>{try{return JSON.parse(line).message?.content?.some(item=>item.type==='tool_use'&&item.name==='Workflow');}catch{return false;}}))throw Error('本次未调用原生工作流工具');
    state.status='completed';
  } catch(error) {state=read(file) || state;state.status=interrupted?'stopped':'failed';state.error=error.message;}
  finally {
    if(['failed','stopped'].includes(state.status))stopOwnedBuild(state);
    if(interrupted && state.activeTask){let stopTimer;try{await Promise.race([waitTask(state.activeTask),new Promise(resolve=>{stopTimer=setTimeout(resolve,10000);})]);}finally{clearTimeout(stopTimer);}}
    process.off('SIGTERM',stop);process.off('SIGINT',stop);
    if(state.activeAttempt) {
      const job=read(state.activeAttempt);
      if(job?.status!=='running' || !alive(job?.workerPid)) {
        if(job?.status==='running')write(state.activeAttempt,{...job,status:'failed',resultStatus:'failed',error:'节点进程已中断',endedAt:new Date().toISOString()});
        delete state.activeAttempt;
      }
    }
    state.endedAt=new Date().toISOString();save(file,state);
    if(state.start==='environment') {
      const status=read(state.runDir+'.meta/status.json') || {};
      write(state.runDir+'.meta/status.json',{...status,state:state.status==='stopped'?'stopped':state.status==='failed'?'failed':state.receipts.some(item=>['degraded','blocked'].includes(item.status))?'partial':'success',workflow_id:state.id,updated_at:state.endedAt});
    }
    if(state.initialJob && !state.receipts.length && !state.activeAttempt){const job=read(state.initialJob);if(job?.status==='running')write(state.initialJob,{...job,status:'failed',resultStatus:'failed',error:state.error,endedAt:state.endedAt});}
    if(!state.activeAttempt && !(state.activeTask && taskLive(read(state.activeTask))) && read(path.join(state.lock,'workflow-owner.json'))?.id===state.id)fs.rmSync(state.lock,{recursive:true,force:true});
  }
  return state;
}
if(process.argv[1] && path.resolve(process.argv[1])===self) {
  try {
    if(process.argv[2]==='--request-step')console.log(JSON.stringify(requestStep(process.argv[3],process.argv[5])));
    else if(process.argv[2]==='--step')console.log(JSON.stringify(await step(process.argv[3],process.argv[5])));
    else if(process.argv[2]==='--chain') {
      const initial=process.argv[3],job=read(initial),runDir=path.resolve(job.root,'../../..').replace(/\.meta$/,'');
      const file=createState({runDir,source:job.source,project:job.project,models:job.models,image:job.image,start:job.node,initialJob:initial,lock:job.lock});
      process.exitCode=(await coordinate(file)).status==='completed'?0:1;
    } else if(process.argv[2]==='--coordinate') {
      process.exitCode=(await coordinate(process.argv[3])).status==='completed'?0:1;
    } else if(process.argv[2]==='--resume') {
      const file=path.resolve(process.argv[3]),state=resumeState(file);
      const fd=fs.openSync(path.join(path.dirname(file),'controller.log'),'a');
      const child=spawn(process.execPath,[self,'--coordinate',file],{cwd:repo,detached:true,stdio:['ignore',fd,fd]});fs.closeSync(fd);
      child.on('error',error=>{state.status='failed';state.error=error.message;save(file,state);if(read(path.join(state.lock,'workflow-owner.json'))?.id===state.id)fs.rmSync(state.lock,{recursive:true,force:true});});
      state.coordinatorPid=child.pid;save(file,state);
      fs.writeFileSync(state.runDir+'.meta/supervisor.pid',String(child.pid));child.unref();
      console.log(JSON.stringify({id:state.id,status:'running',runDir:state.runDir,resumed:true}));
    } else if(process.argv[2]==='--launch') {
      const options=JSON.parse(process.argv[3]),file=createState(options),state=load(file);
      const fd=fs.openSync(path.join(path.dirname(file),'controller.log'),'a');
      const child=spawn(process.execPath,[self,'--coordinate',file],{cwd:repo,detached:true,stdio:['ignore',fd,fd]});fs.closeSync(fd);
      child.on('error',error=>{state.status='failed';state.error=error.message;save(file,state);if(read(path.join(state.lock,'workflow-owner.json'))?.id===state.id)fs.rmSync(state.lock,{recursive:true,force:true});});
      fs.writeFileSync(state.runDir+'.meta/supervisor.pid',String(child.pid));child.unref();
      console.log(JSON.stringify({id:state.id,status:'running',runDir:state.runDir}));
    } else if(process.argv[2]==='--run') {
      const options=JSON.parse(process.argv[3]);const state=await coordinate(createState(options));console.log(JSON.stringify(state));process.exitCode=state.status==='completed'?0:1;
    } else throw Error('缺少工作流操作');
  }catch(error){console.error(error.message);process.exitCode=1;}
}
