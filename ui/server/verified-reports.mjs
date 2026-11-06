import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {listNodeArtifacts,artifactText,openArtifact} from './node-artifacts.mjs';
import {nodeAttempts} from './node-retries.mjs';
import {visualRoot} from './visual-assets.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
function imageProof(repo,item) {
 try {
  const fd=openArtifact(item);let bytes;try{bytes=fs.readFileSync(fd);}finally{fs.closeSync(fd);}
  // Historical model responses predate generation sidecars. Require an exact
  // model response cache record bound to this file, never a filename heuristic.
  if(!((bytes.subarray(0,4).toString()==='RIFF' && bytes.subarray(8,12).toString()==='WEBP') || bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))))return false;
  const proof=read(item.file+'.generation.json');
  if(proof)return proof.source==='text-to-image' && Boolean(proof.model && proof.prompt_hash) && proof.sha256===hash(bytes);
  const cache=path.join(repo,'.cache/image2');if(!fs.existsSync(cache))return false;
  return fs.readdirSync(cache).filter(name=>name.endsWith('.json')).some(name=>{
   const row=read(path.join(cache,name));if(!row?.file || !row.model || !row.prompt || !row.usage)return false;
   const recorded=path.resolve(repo,row.file);
   return recorded===item.file && !fs.lstatSync(recorded).isSymbolicLink() && fs.statSync(recorded).mtimeMs<=fs.statSync(path.join(cache,name)).mtimeMs+1000;
  });
 }catch{return false;}
}
const text=value=>Array.isArray(value)?value.join('\n\n'):String(value || '未提供');
export function verifiedReports(repo,findings) {
 const rows=[];
 for(const f of findings) {
  const s=f.stageResults || {};
  if(!f.reviewReady || s.blue?.status!=='confirmed' || s.red?.status!=='flag_captured' || !s.red.provenanceVerified || s.judge?.status!=='judge_approved' || !s.judge.provenanceVerified)continue;
  const runDir=path.resolve(repo,'runs',f.project,f.runId);
  if(runDir!==path.resolve(f.runDir || '') || !runDir.startsWith(path.join(repo,'runs')+path.sep))continue;
  const current=[['verify',s.blue],['redteam-agent',s.red],['judge',s.judge]].every(([node,result])=>{
   const attempt=nodeAttempts(runDir,node).at(-1);
   return attempt?.status==='completed' && attempt.project===f.project && attempt.runId===f.runId && attempt.id===result.attemptId;
  });
  if(!current)continue;
  const run={project:f.project,runId:f.runId,runDir};
  const root=path.resolve(visualRoot(run));
  const artifacts=listNodeArtifacts(run,'visual').filter(item=>item.root===root);
  const image=artifacts.find(item=>item.name==='visual-rendered/scene-'+f.id+'.webp');
  const report=artifacts.find(item=>item.name==='visual-rendered/report-illustrated.md');
  if(!image || !report || !imageProof(repo,image))continue;
  const illustrated=artifactText(report);
  if(illustrated.truncated || !illustrated.text.includes(path.basename(image.name)))continue;
  const imageUrl='/api/runs/'+encodeURIComponent(f.project)+'/'+encodeURIComponent(f.runId)+'/nodes/visual/artifacts/'+image.id+'?image=1';
  const md='# '+text(f.title)+'\n\n'+
   '**项目：** '+f.project+' · **编号：** '+f.id+' · **严重度：** '+f.severity+'\n\n'+
   '蓝队动态验证已确认 · 红队证据已核验 · 独立审核通过\n\n'+
   '![文生图模型生成的场景插图]('+imageUrl+')\n\n'+
   '## 影响\n\n'+text(f.impact)+'\n\n## 根因\n\n'+text(f.rootCause)+
   '\n\n## 触发条件\n\n'+text(f.preconditions)+
   '\n\n## 验证方法\n\n'+text(f.reproduction)+
   '\n\n## 动态验证结论\n\n'+text(s.blue.reason)+
   '\n\n## 独立审核结论\n\n'+text(s.judge.reason)+
   '\n\n## 修复建议\n\n'+text(f.remediation)+
   '\n\n## 源码位置\n\n'+(f.sourcePaths || f.evidence || []).map(x=>'- '+x).join('\n')+
   '\n\n## 证据定位\n\n'+[s.blue.artifact,s.red.artifact,s.judge.artifact].filter(Boolean).map(x=>'- `'+x+'`').join('\n')+
   '\n\n审计运行：`'+f.runId+'` · 提交：`'+(f.commit || '未记录')+'`\n';
  rows.push({exportId:hash(Buffer.from(f.key)).slice(0,24),key:f.key,project:f.project,runId:f.runId,id:f.id,title:f.title,severity:f.severity,imageUrl,markdown:md});
 }
 return rows;
}
