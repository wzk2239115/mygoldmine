import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {nodeAttempts} from './node-retries.mjs';

const specs={
 environment:['environment','env-build'],
 orchestrator:['audit-report.md','audit-report.json','task-artifacts'],
 visual:['visual-rendered','visual/agentic'],
 verify:['verify/agent'],
 'redteam-lab':['redteam/selection.json','redteam/summary.json','redteam/labs'],
 'redteam-agent':['redteam/summary.json','redteam/agent-runs'],
 judge:['judge','redteam/summary.json'],
 learner:['rsi/reward.json','rsi/exploration-feedback.json','rsi/stage-learning-evaluation.json','rsi/learning-retry.json','rsi/stage-feedback','rsi/skillopt','rsi/mining-repairs/agentic']
};
const extensions=new Set(['.md','.json','.png','.jpg','.jpeg','.webp','.svg']);
export function listNodeArtifacts(run,node) {
 if(!specs[node])return [];
 const attempt=nodeAttempts(run.runDir,node).at(-1);
 const roots=[{root:run.runDir,label:'原始运行'}];
 if(attempt?.workspace)roots.unshift({root:attempt.workspace,label:'最近重跑'});
 if(node==='environment')roots.push({root:run.runDir+'.meta',label:'环境元数据',files:['env-phase.json','env-build.json','sandbox.json']});
 const workflowRoot=path.join(run.runDir+'.meta','workflows');
 if(fs.existsSync(workflowRoot))for(const id of fs.readdirSync(workflowRoot))roots.push({root:path.join(workflowRoot,id),label:'原生工作流回执',files:['state.json']});
 const result=[];
 for(const {root,label,files=specs[node]} of roots) {
  if(!fs.existsSync(root))continue;
  const realRoot=fs.realpathSync(root);
  function visit(file,depth=0) {
   if(depth>6 || result.length>=100)return;
   let stat;try{stat=fs.lstatSync(file);}catch{return;}
   if(stat.isSymbolicLink())return;
   const real=fs.realpathSync(file);
   if(!real.startsWith(realRoot+path.sep))return;
   if(stat.isDirectory()) {for(const entry of fs.readdirSync(file).sort())visit(path.join(file,entry),depth+1);return;}
   if(!stat.isFile() || !extensions.has(path.extname(file).toLowerCase()))return;
   const name=path.relative(root,file);
   if(/(?:^|\/)(?:agent|run-meta|finding|scenario|result|judge|summary)\.json$/.test(name) && stat.size>5*1024*1024)return;
   const id=createHash('sha256').update(root+'\0'+name).digest('hex').slice(0,24);
   result.push({id,name,group:label,size:stat.size,updatedAt:stat.mtime.toISOString(),type:/\.(png|jpe?g|webp|svg)$/i.test(name)?'image':'text',file:real,root:realRoot});
  }
  for(const relative of files)visit(path.join(root,relative));
 }
 return result;
}
export function nodeArtifact(run,node,id) {
 return listNodeArtifacts(run,node).find(item=>item.id===id) || null;
}
export function openArtifact(item) {
 const fd=fs.openSync(item.file,fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
 try {
  const actual=fs.realpathSync('/proc/self/fd/'+fd);
  if(!actual.startsWith(item.root+path.sep) || !fs.fstatSync(fd).isFile())throw Error('产物路径已改变，请刷新后重试');
  return fd;
 }catch(error){fs.closeSync(fd);throw error;}
}
export function artifactText(item) {
 const limit=512*1024;
 const fd=openArtifact(item);
 try {const buffer=Buffer.alloc(Math.min(item.size,limit));const count=fs.readSync(fd,buffer,0,buffer.length,0);return {text:buffer.subarray(0,count).toString('utf8'),truncated:item.size>limit};}
 finally{fs.closeSync(fd);}
}

export function artifactAsset(item,requested) {
 if(!requested || requested.includes('\0') || requested.includes('\\') || path.isAbsolute(requested))return null;
 const file=path.resolve(path.dirname(item.file),requested);
 if(!file.startsWith(item.root+path.sep) || !extensions.has(path.extname(file).toLowerCase()))return null;
 try {
  const stat=fs.lstatSync(file),real=fs.realpathSync(file);
  if(!stat.isFile() || stat.isSymbolicLink() || !real.startsWith(item.root+path.sep))return null;
  return {...item,file:real,name:path.basename(file),size:stat.size,type:/\.(png|jpe?g|webp|svg)$/i.test(file)?'image':'text'};
 }catch{return null;}
}
