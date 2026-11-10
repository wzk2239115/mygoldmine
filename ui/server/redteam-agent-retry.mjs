import {signalProcessTree} from './durable-task.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';

const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(`${file}.tmp`,JSON.stringify(value,null,2));fs.renameSync(`${file}.tmp`,file);};
const safe=id=>typeof id==='string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(id);
const repoRootOf=run=>path.resolve(run.runDir,'../../..');
const originalRunDir=job=>path.resolve(job.root,'../../..').replace(/\.meta$/,'');
function pythonCommand() {
  const candidates=[
    process.env.PYTHON,
    process.env.CONDA_PREFIX ? path.join(process.env.CONDA_PREFIX,'bin','python3') : '',
    process.env.VIRTUAL_ENV ? path.join(process.env.VIRTUAL_ENV,'bin','python3') : '',
    path.join(os.homedir(),'miniconda3','bin','python3'),
    'python3'
  ];
  for(const candidate of candidates) {
    if(!candidate) continue;
    if(candidate==='python3' || fs.existsSync(candidate)) return candidate;
  }
  return 'python3';
}

function inside(root,file) {
  const resolved=path.resolve(file);
  const base=path.resolve(root);
  return resolved===base || resolved.startsWith(`${base}${path.sep}`);
}

function firstFile(root,candidates) {
  for(const file of candidates) {
    if(typeof file!=='string' || !file)continue;
    const resolved=path.resolve(file);
    if(!inside(root,resolved))continue;
    try{if(fs.statSync(resolved).isFile())return resolved;}catch{}
  }
  return '';
}

function latestLabWorkspace(run) {
  const root=path.join(`${run.runDir}.meta`,'node-retries','redteam-lab');
  if(!fs.existsSync(root))return null;
  const attempts=fs.readdirSync(root).map(id=>read(path.join(root,id,'attempt.json'))).filter(Boolean).sort((a,b)=>String(a.startedAt).localeCompare(String(b.startedAt)));
  const latest=attempts.at(-1);
  return latest?.workspace ? path.resolve(latest.workspace) : null;
}

function batchFindings(run) {
  const batch=path.join(run.runDir,'redteam/batch');
  if(!fs.existsSync(batch))return [];
  return fs.readdirSync(batch).filter(name=>fs.statSync(path.join(batch,name)).isFile()).map(name=>path.join(batch,name));
}

function resultMap(...sources) {
  const map=new Map();
  for(const source of sources) {
    for(const item of source?.results || []) {
      if(!item || !safe(item.id))continue;
      map.set(item.id,{...map.get(item.id),...item});
    }
  }
  return map;
}

export function agentCandidates(run) {
  const project=run.project;
  if(!safe(project))throw new Error('项目编号无效');
  const repoRoot=repoRootOf(run);
  const report=read(path.join(run.runDir,'audit-report.json')) || {};
  const findings=new Map((report.findings || report.vulnerabilities || []).filter(item=>item && typeof item==='object' && safe(item.id || item.finding_id)).map(item=>[item.id || item.finding_id,item]));
  const workspace=latestLabWorkspace(run);
  const latestSelection=workspace?read(path.join(workspace,'redteam/selection.json')):null;
  const latestSummary=workspace?read(path.join(workspace,'redteam/summary.json')):null;
  const rootSummary=read(path.join(run.runDir,'redteam/summary.json')) || {};
  const candidatesFile=read(path.join(run.runDir,'redteam/candidates.json')) || {};
  const construction=read(path.join(run.runDir,'redteam/batch/construction/summary.json')) || {};
  const results=resultMap(construction,rootSummary,latestSummary);
  const selected=latestSelection?.candidates || candidatesFile.candidates || rootSummary.results || construction.results || [];
  const order=[];
  for(const item of selected) {
    const id=typeof item==='string'?item:item?.id;
    const candidateProject=typeof item==='string'?project:item?.project;
    const candidateRun=typeof item==='string'?'':item?.run_id;
    if(candidateProject && candidateProject!==project)continue;
    if(candidateRun && candidateRun!==run.runId)continue;
    if(safe(id) && !order.includes(id))order.push(id);
  }
  const batch=batchFindings(run);
  const candidates=order.map(id=>{
    const result=results.get(id) || {};
    const finding=firstFile(repoRoot,[
      workspace?path.join(workspace,'redteam/inputs',`${id}.json`):'',
      result.finding,
      ...batch.filter(file=>path.basename(file).endsWith(`-${project}-${id}.json`))
    ]);
    const scenario=firstFile(repoRoot,[
      workspace?path.join(workspace,'redteam/labs',id,'scenario.json'):'',
      result.scenario,
      path.join(run.runDir,'redteam/batch/construction/labs',project,id,'scenario.json'),
      path.join(repoRoot,'labs',project,id,'scenario.json')
    ]);
    const reason=result.delivery_status && result.delivery_status!=='accepted'?'该成员缺少有效场景交付，已跳过':!finding?'缺少本轮候选问题文件':!scenario?'缺少可用红队场景，请先重跑场景构建':'';
    return {
      id,
      title:findings.get(id)?.title || result.title || item?.title || id,
      project,
      runId:run.runId,
      finding,
      scenario,
      status:reason?'blocked':'ready',
      reason
    };
  });
  return candidates;
}

export function prepareAgentRetry(run,workspace) {
  const candidates=agentCandidates(run);
  write(path.join(workspace,'redteam/agent-selection.json'),{
    project:run.project,
    runId:run.runId,
    candidates
  });
  return candidates;
}

function runProcess(command,{cwd,timeout}) {
  return new Promise(resolve=>{
    const child=spawn(command[0],command.slice(1),{cwd,env:process.env,stdio:['ignore','pipe','pipe']});
    let output='',finished=false,timedOut=false;
    const timer=setTimeout(()=>{if(!finished){timedOut=true;signalProcessTree(child.pid,'SIGKILL');}},timeout);
    const collect=chunk=>{output=(output+chunk.toString()).slice(-65536);};
    child.stdout.on('data',collect);
    child.stderr.on('data',collect);
    child.on('error',error=>{if(finished)return;finished=true;clearTimeout(timer);resolve({code:1,output:error.message});});
    child.on('close',code=>{if(finished)return;finished=true;clearTimeout(timer);resolve({code:timedOut?124:(code ?? 1),output});});
  });
}

function statusFor(code,result) {
  const nested=result?.result && typeof result.result==='object'?result.result:{};
  if(code===0)return nested.status==='flag_captured'?'flag_captured':'not_captured';
  if(code===78)return 'blocked_harness_dependency';
  if(code===2)return 'not_captured';
  if(code===4)return 'model_timeout';
  if(code===124)return 'agent_timeout';
  if(code===5)return nested.status || 'lab_unhealthy';
  if(code===6)return nested.status || 'blocked_scenario_invalid';
  return 'agent_error';
}

export function executionSummaryStatus(values,readyCount) {
  const executed=values.filter(item=>['flag_captured','not_captured'].includes(item.status));
  // A candidate-level failure is durable evidence for that candidate, not a
  // reason to discard successful candidates or stop judge/learner for the run.
  // The workflow itself still fails on worker/process errors before aggregation.
  const terminalStatuses=new Set([
    'flag_captured','not_captured','blocked','blocked_harness_dependency',
    'lab_unhealthy','blocked_scenario_invalid','model_timeout','agent_timeout','agent_error'
  ]);
  const errors=values.filter(item=>!terminalStatuses.has(item.status));
  if(errors.length)return 'failed';
  if(!readyCount || !executed.length)return 'blocked';
  return values.every(item=>item.captured) ? 'completed' : 'degraded';
}

export async function runAgentRetry(job,concurrency=10) {
  if(!Number.isInteger(concurrency) || concurrency<1 || concurrency>10)throw new Error('并发数必须在 1 到 10 之间');
  const selection=read(path.join(job.workspace,'redteam/agent-selection.json'));
  if(!selection?.candidates?.length)throw new Error('没有可重跑的红队候选');
  const project=job.project;
  const runsRoot=path.join(job.workspace,'redteam/agent-runs');
  const summary={
    stage:'redteam-agent',
    status:'running',
    selected:selection.candidates.length,
    ready:selection.candidates.filter(item=>item.status==='ready').length,
    processed:0,
    captured:0,
    blocked:0,
    current:'',
    concurrency,
    running:[],
    results:[]
  };
  const candidates=selection.candidates;
  const results=new Map();
  const tasks=new Map(candidates.map(candidate=>[candidate.id,{...candidate,state:candidate.status==='ready'?'queued':'blocked'}]));
  const save=()=>{
    summary.results=candidates.map(candidate=>results.get(candidate.id)).filter(Boolean);
    summary.processed=summary.results.length;
    summary.captured=summary.results.filter(item=>item.captured).length;
    summary.blocked=summary.results.filter(item=>item.status==='blocked' || item.status==='blocked_harness_dependency').length;
    summary.running=[...tasks.values()].filter(item=>item.state==='running').map(item=>item.id);
    summary.current=summary.running.join('、');
    write(path.join(job.workspace,'redteam/summary.json'),summary);
  };
  const update=(candidate,state,extra={})=>{
    const task={...tasks.get(candidate.id),...extra,state};
    tasks.set(candidate.id,task);
    write(path.join(job.workspace,'redteam/tasks',`${candidate.id}.json`),{...task,concurrency});
  };
  for(const candidate of candidates) {
    if(candidate.status==='ready')continue;
    results.set(candidate.id,{
      id:candidate.id,title:candidate.title,status:'blocked',captured:false,
      scenario:candidate.scenario,finding:candidate.finding,run_dir:'',
      error:candidate.reason || '缺少可用红队场景'
    });
    update(candidate,'blocked',{status:'blocked',error:candidate.reason || '缺少可用红队场景'});
  }
  save();
  const ready=candidates.filter(candidate=>candidate.status==='ready');
  const runOne=async candidate=>{
    const index=ready.indexOf(candidate)+1;
    const runId=`agent-retry-${String(job.id).slice(0,8)}-${String(index).padStart(2,'0')}`;
    update(candidate,'running',{status:'running'});
    save();
    const command=[
      pythonCommand(),
      path.join(job.repoRoot,'scripts/runner/auto_repair.py'),
      '--python',pythonCommand(),
      '--output',path.join(job.workspace,'redteam/runner-repairs',candidate.id),
      '--model',job.model,'--execute-agent','--',
      '--finding',candidate.finding,
      '--project',project,
      '--scenario',candidate.scenario,
      '--run-id',runId,
      '--runs-root',runsRoot,
      '--model',job.model
    ];
    const started=Date.now();
    const {code,output}=await runProcess(command,{cwd:job.repoRoot,timeout:((Number(process.env.REDTEAM_AGENT_TIMEOUT)||7200)+1800)*1000});
    const runDir=path.join(runsRoot,project,runId);
    const document=read(path.join(runDir,'result.json')) || {};
    const status=statusFor(code,document);
    const nested=document.result && typeof document.result==='object'?document.result:{};
    const repairRoot=path.join(job.workspace,'redteam/runner-repairs',candidate.id);
    const execution=read(path.join(repairRoot,'execution.json'));
    const repair=execution?.runner || read(path.join(repairRoot,'runner-repair.json'));
    const result={
      runner_repair:repair,
      target_trigger_count:nested.target_trigger_count ?? null,
      verification_reason:nested.verification_reason || '',
      ...(status==='blocked_harness_dependency'?{error_scope:'harness_dependency',retry_owner:'runner-environment',auto_retry:false}:{}),
      id:candidate.id,
      title:candidate.title,
      status,
      captured:status==='flag_captured' && Boolean(nested.captured),
      scenario:candidate.scenario,
      finding:candidate.finding,
      run_dir:runDir,
      returncode:code,
      duration_seconds:Math.round((Date.now()-started)/100)/10,
      error:status==='flag_captured' || status==='not_captured'?'':(nested.error || repair?.reason || output.slice(-800))
    };
    results.set(candidate.id,result);
    update(candidate,'completed',{status,run_dir:runDir,returncode:code,error:result.error});
    save();
  };
  let cursor=0;
  await Promise.all(Array.from({length:Math.min(concurrency,ready.length)},async()=>{
    while(cursor<ready.length) {
      const candidate=ready[cursor++];
      await runOne(candidate);
    }
  }));
  const values=[...results.values()];
  summary.status=executionSummaryStatus(values,ready.length);
  summary.current='';
  summary.running=[];
  save();
  return summary.status;
}

export function recoverExecutionAggregation(file) {
 file=path.resolve(file);
 const job=read(file);
 if(!job || job.node!=='redteam-agent' || job.status!=='completed' || job.exitCode!==0 || job.resultStatus!=='failed')throw Error('只能恢复正常执行结束但汇总失败的红队批次');
 const expected=path.join(job.repoRoot,'runs',job.project,job.runId+'.meta','node-retries','redteam-agent',job.id);
 if(path.dirname(file)!==expected || job.root!==expected || job.workspace!==path.join(expected,'output'))throw Error('批次路径与项目不匹配');
 const summaryFile=path.join(job.workspace,'redteam/summary.json'),summary=read(summaryFile);
 if(summary?.stage!=='redteam-agent' || summary.status!=='failed' || !Array.isArray(summary.results) || !summary.results.length || summary.running?.length)throw Error('批次汇总尚未完整结束');
 const status=executionSummaryStatus(summary.results,summary.ready);
 if(status!=='degraded')throw Error('包含真实执行异常或没有可恢复的未复现结果');
 for(const row of summary.results) {
  if(row.status==='blocked' || row.status==='blocked_harness_dependency')continue;
  if(row.error || ![0,2].includes(row.returncode) || !row.run_dir || !fs.realpathSync(row.run_dir).startsWith(fs.realpathSync(job.workspace)+path.sep))throw Error('执行结果来源或退出码无效');
  const result=read(path.join(row.run_dir,'result.json'))?.result;
  if(result?.status!==row.status || Boolean(result.captured)!==Boolean(row.captured))throw Error('执行原始结果与汇总不符');
 }
 const archive=path.join(job.root,'aggregation-recovery',String(Date.now()));
 fs.mkdirSync(archive,{recursive:true});
 fs.copyFileSync(file,path.join(archive,'attempt.json'));
 fs.copyFileSync(summaryFile,path.join(archive,'summary.json'));
 write(summaryFile,{...summary,status,aggregationRecovery:{previousStatus:summary.status,archive}});
 write(file,{...job,resultStatus:status,aggregationRecovery:{previousResultStatus:job.resultStatus,archive}});
 return {status,archive,attempt:file,modelInvoked:false};
}
