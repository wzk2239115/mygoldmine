import fs from 'node:fs';
import path from 'node:path';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(`${file}.tmp`,JSON.stringify(value,null,2));fs.renameSync(`${file}.tmp`,file);};

const helper=fileURLToPath(new URL('../../scripts/redteam/blue_handoff.py',import.meta.url));
function blueSelection(run,output) {
  const selectedFile=path.join(run.runDir,'redteam/candidates.json');
  const args=[helper,'--run-dir',run.runDir,'--project',run.project,'--reuse-selection','--max',fs.existsSync(selectedFile)?'10000':'5'];
  if(output)args.push('--output',output);else args.push('--inspect');
  const result=spawnSync('python3',args,{encoding:'utf8',timeout:30000,maxBuffer:2*1024*1024});
  if(result.error)throw Error(`蓝队交付检查失败：${result.error.message}`);
  let value;try{value=JSON.parse(result.stdout);}catch{throw Error('无法读取蓝队交付检查结果');}
  if(result.status!==0 || value.error)throw Error(value.error || '蓝队交付检查失败');
  if(value.gate_reason)throw Error(value.gate_reason);
  return value;
}
export function labCandidates(run) {
  const selection=blueSelection(run);
  if(!selection.candidates.length)throw Error(`没有蓝队已确认且产物完整的候选${selection.excluded.length?'：'+selection.excluded.slice(0,5).map(item=>`${item.id} ${item.reason}`).join('；'):''}`);
  return selection.candidates;
}
export function prepareLabRetry(run,workspace) {
  const report=fs.readFileSync(path.join(workspace,'audit-report.json'));
  if(!report.equals(fs.readFileSync(path.join(run.runDir,'audit-report.json'))))throw Error('审计报告已变化，请刷新后重试');
  const reportData=JSON.parse(report);
  const originals=new Map((reportData.findings || reportData.vulnerabilities || []).map(item=>[item.id || item.finding_id,item]));
  const root=path.join(workspace,'redteam'), selection=blueSelection(run,root);
  if(!selection.candidates.length)throw Error('没有蓝队已确认且产物完整的候选');
  const inputs=selection.candidates.map(candidate=>{
    const file=path.join(root,'inputs',`${candidate.id}.json`);write(file,originals.get(candidate.id));
    return {...candidate,finding:file};
  });
  write(path.join(root,'selection.json'),{...selection,sourceRunId:run.runId,candidates:inputs});
}

export async function runLabRetry(job, concurrency = 10) {
  if(!Number.isInteger(concurrency) || concurrency<1 || concurrency>10)throw Error('并发数必须在 1 到 10 之间');
  const root=path.join(job.workspace,'redteam');
  const selection=read(path.join(root,'selection.json'));
  if(!selection?.candidates?.length)throw Error('没有可重跑的红队候选');
  const summary={stage:'redteam-lab',buildOnly:true,status:'running',selected:selection.candidates.length,processed:0,ready:0,blocked:0,current:'',concurrency,running:[],results:[]};
  const results=new Map(), tasks=selection.candidates.map(candidate=>({...candidate,state:'queued'}));
  const save=()=>{
    summary.results=selection.candidates.map(candidate=>results.get(candidate.id)).filter(Boolean);
    summary.processed=summary.results.length;summary.ready=summary.results.filter(result=>result.status==='built').length;summary.blocked=summary.processed-summary.ready;
    summary.running=tasks.filter(task=>task.state==='running').map(task=>task.id);summary.current=summary.running.join('、');
    summary.counts={built:summary.ready,blocked:summary.blocked};write(path.join(root,'summary.json'),summary);
  };
  const update=(task,state)=>{task.state=state;write(path.join(root,'tasks',`${task.id}.json`),{...task,concurrency});};
  tasks.forEach(task=>update(task,'queued'));save();
  async function execute(candidate) {
    const lab=path.join(root,'labs',candidate.id);
    fs.mkdirSync(lab,{recursive:true});
    update(candidate,'running');save();
    console.log(`[红队场景构建] 开始 ${candidate.id}（并发上限 ${concurrency}），仅构建本节点`);
    const args=['scripts/redteam/build_lab.py','--project',job.project,'--finding',candidate.finding,'--source',job.source,'--lab-dir',lab,'--claude-model',job.model,'--build-only','--blue-handoff',candidate.blue_handoff];
    let result;
    try {result=await new Promise((resolve,reject)=>{
      const child=spawn('python3',args,{cwd:job.repoRoot,stdio:['ignore','pipe','pipe']});
      let output='';
      child.stdout.on('data',chunk=>{output=(output+chunk.toString()).slice(-65536);process.stdout.write(chunk);});
      child.stderr.on('data',chunk=>process.stderr.write(chunk));
      child.on('error',reject);child.on('close',code=>resolve({code,output}));
    });} catch(error) {result={code:1,output:JSON.stringify({error:error.message})};}
    let delivery;try{delivery=JSON.parse(result.output);if(!delivery || typeof delivery!=='object' || Array.isArray(delivery))delivery={};}catch{delivery={};}
    const scenario=path.join(lab,'scenario.json');
    const ready=result.code===0 && delivery.scenario_valid===true && delivery.finding_id===candidate.id && delivery.scenario===scenario && fs.existsSync(scenario);
    const blocked=!ready && delivery.finding_id===candidate.id && delivery.blocked_valid===true && delivery.status==='blocked';
    const record={id:candidate.id,title:candidate.title,status:ready?'built':blocked?'blocked':'build_failed',scenario:ready?scenario:'',builder_returncode:result.code,
      error:ready?'':delivery.blocked_reason || delivery.error || `场景构建未通过检查（退出码 ${result.code}）`,
      blocked:delivery.blocked || path.join(lab,'BLOCKED.md'),blockedReason:delivery.blocked_reason || '',missingCapabilities:delivery.missing_capabilities || []};
    results.set(candidate.id,record);Object.assign(candidate,{status:record.status,error:record.error});update(candidate,'completed');save();
    console.log(`[红队场景构建] ${candidate.id}：${ready?'场景可用':'受阻'}；已结束 ${summary.processed}/${summary.selected}`);
  }
  let index=0;
  await Promise.all(Array.from({length:Math.min(concurrency,tasks.length)},async()=>{
    while(index<tasks.length) {const candidate=tasks[index++];await execute(candidate);}
  }));
  summary.current='';summary.status=summary.ready===summary.selected?'completed':summary.ready?'degraded':'blocked';save();
  return summary.status;
}
