import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';

const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(`${file}.tmp`,JSON.stringify(value,null,2));fs.renameSync(`${file}.tmp`,file);};
const safe=value=>typeof value==='string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(value);

export function labCandidates(run,report=read(path.join(run.runDir,'audit-report.json'))) {
  if(!Array.isArray(report?.findings))throw Error('缺少有效的审计报告');
  const originals=new Map();
  for(const item of report.findings) {
    const id=item?.id || item?.finding_id;
    if(!id)continue;
    if(originals.has(id))throw Error('审计报告含重复的候选编号，无法安全重跑');
    originals.set(id,item);
  }
  const selectedFile=path.join(run.runDir,'redteam/candidates.json');
  let selected;
  if(fs.existsSync(selectedFile)) {
    const snapshot=read(selectedFile);
    if(!Array.isArray(snapshot?.candidates))throw Error('红队候选清单无效');
    selected=snapshot.candidates.map(item=>{
      if(item.project!==run.project || item.run_id!==run.runId)throw Error('红队候选清单不属于当前运行');
      return item.id;
    });
  } else selected=[...originals].filter(([,item])=>['critical','high'].includes(String(item.severity || item.severity_raw || '').toLowerCase())).slice(0,5).map(([id])=>id);
  if(new Set(selected).size!==selected.length)throw Error('红队候选清单含重复编号');
  return selected.map(id=>{
    if(!safe(id) || !originals.has(id))throw Error('红队候选编号无效或不在本轮报告中');
    return {id,finding:originals.get(id)};
  });
}

export function prepareLabRetry(run,workspace) {
  const report=fs.readFileSync(path.join(workspace,'audit-report.json'));
  const candidates=labCandidates(run,JSON.parse(report));
  const root=path.join(workspace,'redteam');
  const inputs=candidates.map(({id,finding})=>{
    const file=path.join(root,'inputs',`${id}.json`);
    write(file,finding);
    return {id,title:finding.title || id,finding:file};
  });
  write(path.join(root,'selection.json'),{sourceRunId:run.runId,project:run.project,reportSha256:createHash('sha256').update(report).digest('hex'),candidates:inputs});
}

export async function runLabRetry(job) {
  const root=path.join(job.workspace,'redteam');
  const selection=read(path.join(root,'selection.json'));
  if(!selection?.candidates?.length)throw Error('没有可重跑的红队候选');
  const summary={stage:'redteam-lab',buildOnly:true,status:'running',selected:selection.candidates.length,processed:0,ready:0,blocked:0,current:'',results:[]};
  const save=()=>{summary.counts={built:summary.ready,blocked:summary.blocked};write(path.join(root,'summary.json'),summary);};
  save();
  for(const candidate of selection.candidates) {
    const lab=path.join(root,'labs',candidate.id);
    fs.mkdirSync(lab,{recursive:true});
    summary.current=candidate.id;save();
    console.log(`[红队场景构建] 开始 ${candidate.id}（${summary.processed+1}/${summary.selected}），仅构建本节点`);
    const args=['scripts/redteam/build_lab.py','--project',job.project,'--finding',candidate.finding,'--source',job.source,'--lab-dir',lab,'--claude-model',job.model,'--build-only'];
    const result=await new Promise((resolve,reject)=>{
      const child=spawn('python3',args,{cwd:job.repoRoot,stdio:['ignore','pipe','pipe']});
      let output='';
      child.stdout.on('data',chunk=>{output=(output+chunk.toString()).slice(-65536);process.stdout.write(chunk);});
      child.stderr.on('data',chunk=>process.stderr.write(chunk));
      child.on('error',reject);child.on('close',code=>resolve({code,output}));
    });
    let delivery;try{delivery=JSON.parse(result.output);}catch{delivery={};}
    const scenario=path.join(lab,'scenario.json');
    const ready=result.code===0 && delivery.scenario_valid===true && delivery.finding_id===candidate.id && delivery.scenario===scenario && fs.existsSync(scenario);
    summary.results.push({id:candidate.id,title:candidate.title,status:ready?'built':'build_failed',scenario:ready?scenario:'',builder_returncode:result.code,
      error:ready?'':delivery.error || `场景构建未通过检查（退出码 ${result.code}）`,blocked:path.join(lab,'BLOCKED.md')});
    summary.processed++;summary[ready?'ready':'blocked']++;save();
    console.log(`[红队场景构建] ${candidate.id}：${ready?'场景可用':'受阻'}；已结束 ${summary.processed}/${summary.selected}`);
  }
  summary.current='';summary.status=summary.ready===summary.selected?'completed':summary.ready?'degraded':'blocked';save();
  return summary.status;
}
