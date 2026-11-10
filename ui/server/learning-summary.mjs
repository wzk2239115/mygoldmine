import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {nodeAttempts} from './node-retries.mjs';
const read=file=>{try{if(fs.statSync(file).size>2*1024*1024)return null;return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const safeId=id=>typeof id==='string' && /^[a-zA-Z0-9_-]{1,128}$/.test(id);
function checked(root,name){
 const file=path.isAbsolute(name)?path.normalize(name):path.resolve(root,name);
 if(!file.startsWith(root+path.sep))return null;
 try{if(fs.realpathSync(file)!==file || !fs.statSync(file).isFile())return null;}catch{return null;}
 return file;
}
export function learningSummary(repo,run,evidenceId=null){
 const attempt=nodeAttempts(run.runDir,'learner').at(-1);
 const root=path.resolve(attempt?.workspace || run.runDir);
 const result=read(path.join(root,'rsi/learning-result.json'));
 const execution=read(path.join(root,'rsi/stage-learning-run.json'));
 const retry=read(path.join(root,'rsi/learning-retry.json'));
 const evaluation=read(path.join(root,'rsi/stage-learning-evaluation.json')) || retry?.evaluation;
 const acceptedDir=path.join(root,'.stage-submissions/learner');
 const receipts=fs.existsSync(acceptedDir)?fs.readdirSync(acceptedDir).filter(n=>n.endsWith('.json')).map(n=>read(path.join(acceptedDir,n))).filter(Boolean).sort((a,b)=>String(b.checked_at).localeCompare(String(a.checked_at))):[];
 const receipt=receipts.find(r=>r.artifact===path.join(root,'rsi/learning-result.json'));
 const refs=new Map();
 const conclusions=(result?.conclusions || []).map(row=>({...row,evidence:(row.evidence || []).map(name=>{
  if(typeof name!=='string')return null;
  const file=checked(root,name),id=createHash('sha256').update(name).digest('hex').slice(0,24);
  if(file)refs.set(id,file);
  return {id,label:file?path.relative(root,file):path.basename(name),available:Boolean(file)};
 }).filter(Boolean)}));
 if(evidenceId){
  const file=refs.get(evidenceId);
  if(!file)return null;
  const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  try{const bytes=Buffer.alloc(6000),size=fs.fstatSync(fd).size,n=fs.readSync(fd,bytes,0,bytes.length,0);
   return {label:path.relative(root,file),text:bytes.subarray(0,n).toString('utf8'),truncated:size>n};
  }finally{fs.closeSync(fd);}
 }
 const bank=path.join(repo,'rsi/stage-skills'),active=read(path.join(bank,'active.json')) || {};
 const proposals=(result?.proposal_ids || []).filter(safeId).map(id=>{
  const imported=read(path.join(bank,'imported',id+'.json'));
  const candidate=read(path.join(bank,'candidates',(imported?.candidate || id)+'.json')) || read(path.join(root,'.stage-skill-proposals',id+'.json'));
  if(!candidate)return {id,missing:true};
  const parent=safeId(candidate.parent)?read(path.join(bank,'candidates',candidate.parent+'.json')):null;
  return {id,stage:candidate.stage,scope:candidate.scope,content:candidate.content,
   before:parent?.content || null,parent:candidate.parent || null,
   active:active[candidate.key]===(imported?.candidate || id),
   published:(evaluation?.published || []).some(v=>v===(imported?.candidate || id) || v?.id===(imported?.candidate || id)),
   evaluation:(evaluation?.results || []).find(v=>v.id===id || v.candidate_id===id) || null};
 });
 const objective=evaluation?.exploration?.objective || read(path.join(root,'rsi/reward.json'))?.objective;
 return {attemptId:attempt?.id || null,status:attempt?.status==='running'?'running':execution?.exit_code? 'failed':result?.status || 'unavailable',
  startedAt:execution?.started_at || attempt?.startedAt,endedAt:execution?.ended_at || attempt?.endedAt,
  error:execution?.error==='TimeoutExpired'?'学习执行超过时限，尚未完成交付':execution?.error || attempt?.error?.slice(0,1200) || null,
  accepted:receipt?.decision==='accepted',receiptAt:receipt?.checked_at || null,
  conclusions,proposals,limitations:result?.limitations || [],
  resultAvailable:Boolean(result),evaluationStatus:evaluation?.status || null,
  metrics:objective?{coverage:objective.delta_risk_coverage,reports:objective.new_verified,reward:objective.total}:null};
}
