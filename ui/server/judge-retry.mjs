import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {nodeAttempts} from './node-retries.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(`${file}.tmp`,JSON.stringify(data,null,2));fs.renameSync(`${file}.tmp`,file);};
export function judgeCandidates(run) {
 const latest=nodeAttempts(run.runDir,'redteam-agent').at(-1);
 if(latest?.status==='running')throw Error('红队执行正在重跑，请等待结束');
 const root=path.join(latest?.workspace || run.runDir,'redteam');
 const summary=read(path.join(root,'summary.json'));
 const base=path.resolve(latest?.workspace || run.runDir);
 return (summary?.results || []).flatMap(item=>{
  if(item.delivery_status && item.delivery_status!=='accepted')return [];
  if(!item.run_dir || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(item.id))return [];
  const source=path.resolve(item.run_dir);
  // Original execution directories may live under the repository runs directory.
  const allowed=latest?[base]:[path.resolve(run.runDir),path.resolve(run.runDir,'../../redteam',run.project)];
  if(!allowed.some(directory=>source.startsWith(directory+path.sep)))return [];
  const document=read(path.join(source,'result.json'));
  const finding=read(path.join(source,'finding.json'));
  if(document?.project && document.project!==run.project)return [];
  if((finding?.id || finding?.finding_id)!==item.id)return [];
  if(!document?.result?.captured || !document.result.flag_provenance)return [];
  const files=['finding.json','result.json','trace.jsonl','agent.jsonl','flag.txt','scenario.json'];
  if(!files.every(file=>{try{return fs.lstatSync(path.join(source,file)).isFile();}catch{return false;}}))return [];
  return [{id:item.id,title:item.title || finding.title || item.id,source}];
 });
}
export function prepareJudgeRetry(run,workspace) {
 const candidates=judgeCandidates(run);
 if(!candidates.length)throw Error('没有已捕获随机标记且证据完整的红队结果，请先完成红队执行');
 const selected=candidates.map(candidate=>{
  const directory=path.join(workspace,'judge/runs',candidate.id);
  fs.mkdirSync(directory,{recursive:true});
  for(const file of ['finding.json','result.json','trace.jsonl','agent.jsonl','flag.txt','scenario.json'])fs.copyFileSync(path.join(candidate.source,file),path.join(directory,file));
  return {...candidate,run_dir:directory};
 });
 write(path.join(workspace,'judge/selection.json'),{candidates:selected});
}
export async function runJudgeRetry(job) {
 const selection=read(path.join(job.workspace,'judge/selection.json'));
 if(!selection?.candidates?.length)throw Error('缺少本次审核输入');
 const summary={status:'running',selected:selection.candidates.length,processed:0,approved:0,results:[]};
 const save=()=>write(path.join(job.workspace,'judge/summary.json'),summary);
 save();
 for(const candidate of selection.candidates) {
  summary.current=candidate.id;save();
  const log=fs.openSync(path.join(candidate.run_dir,'judge-worker.log'),'a');
  let code;
  try {
   code=await new Promise((resolve,reject)=>{
    const child=spawn(process.env.PYTHON || 'python3',[path.join(job.repoRoot,'scripts/redteam/judge.py'),'--run-dir',candidate.run_dir,'--claude-model',job.model,'--timeout','360'],{cwd:job.repoRoot,env:{...process.env,RSI_VALIDATION_TRAJECTORY:path.join(job.workspace,'judge/validation.jsonl')},stdio:['ignore',log,log]});
    child.on('error',reject);child.on('close',value=>resolve(value ?? 1));
   });
  } finally {fs.closeSync(log);}
  const verdict=read(path.join(candidate.run_dir,'judge.json'));
  const approved=code===0 && verdict?.verdict==='approved';
  summary.results.push({id:candidate.id,title:candidate.title,run_dir:candidate.run_dir,judge_returncode:code,status:approved?'judge_approved':verdict?.verdict==='rejected'?'judge_rejected':verdict?.verdict==='needs_review'?'judge_needs_review':'judge_error'});
  summary.processed++;summary.approved+=Number(approved);save();
 }
 summary.current='';
 const errors=summary.results.filter(item=>item.status==='judge_error').length;
 summary.status=errors===summary.selected?'failed':errors?'degraded':'completed';save();
 return summary.status;
}
