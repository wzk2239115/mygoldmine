import {execFile} from "node:child_process";
import fs from 'node:fs';
import path from 'node:path';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const cache=new Map();
const timelines=new Map(),pending=new Set(),timelineTimes=new Map();
function merge(rows){const out=[];for(const [a,b] of rows.sort((x,y)=>x[0]-y[0])){if(out.length&&a<=out.at(-1)[1]+1)out.at(-1)[1]=Math.max(b,out.at(-1)[1]);else out.push([a,b]);}return out;}
function difference(rows,seen){const out=[];for(const [a,b] of merge(rows)){let cursor=a;for(const [l,r] of seen){if(r<cursor)continue;if(l>b)break;if(l>cursor)out.push([cursor,l-1]);cursor=Math.max(cursor,r+1);}if(cursor<=b)out.push([cursor,b]);}return out;}
export function coverageTokens(repo,project,{fresh=false}={}){
 const key=repo+'/'+project,old=cache.get(key);if(!fresh&&old&&Date.now()-old.time<30000)return old.value;
 const usage=read(path.join(repo,'.runtime/state/token-usage/summary.json'));
 const groups=(usage?.groups||[]).filter(x=>x.project===project&&x.stage==='orchestrator');
 const root=path.join(repo,'runs',project);const runs=[];
 for(const name of fs.existsSync(root)?fs.readdirSync(root):[]){
  const folder=path.join(root,name);if(name.endsWith('.meta')||fs.lstatSync(folder).isSymbolicLink()||!fs.statSync(folder).isDirectory())continue;
  const summary=read(path.join(folder,'task-artifacts/read-coverage/summary.json'));
  if(!summary?.source_version)continue;
  const status=read(folder+'.meta/status.json')||{};
  runs.push({name,folder,summary,time:status.started_at||status.startedAt||new Date(fs.statSync(path.join(folder,'task-artifacts/read-coverage/summary.json')).mtimeMs).toISOString()});
 }
 runs.sort((a,b)=>a.time.localeCompare(b.time)||a.name.localeCompare(b.name));
 const versions=new Map();
 for(const run of runs){
  const version=run.summary.source_version;
  if(!versions.has(version))versions.set(version,{source_version:version,points:[],seen:new Map(),tokens:0,lines:0,weighted:0,incomplete:false});
  const series=versions.get(version);const files=new Map();
  for(const file of run.summary.files||[]){if(file.kind!=='read'||!file.file)continue;const key=file.file+'/'+(file.file_sha256||'');if(!files.has(key))files.set(key,{file:file.file,ranges:[]});for(const r of file.ranges||[])if(Number.isInteger(r.start)&&Number.isInteger(r.end)&&r.start>0&&r.end>=r.start)files.get(key).ranges.push([r.start,r.end]);}
  const priorities=new Map();for(const u of read(path.join(run.folder,'triage/jev-infra.json'))?.units||[]){if(!Number.isInteger(u.line_start)||!Number.isInteger(u.line_end)||!Number.isFinite(u.priority))continue;const p=u.path?.replace(/^\.\//,'');if(!priorities.has(p))priorities.set(p,[]);priorities.get(p).push([u.line_start,u.line_end,Math.max(0,Math.min(1,u.priority))]);}
  for(const [key,file] of files){const seen=series.seen.get(key)||[];const novel=difference(file.ranges,seen);for(const [a,b] of novel){series.lines+=b-a+1;const bounds=new Set([a,b+1]);const ps=priorities.get(file.file)||[];for(const [l,r] of ps)if(l<=b&&r>=a){bounds.add(Math.max(a,l));bounds.add(Math.min(b,r)+1);}const sorted=[...bounds].sort((x,y)=>x-y);for(let i=1;i<sorted.length;i++){const l=sorted[i-1],r=sorted[i];series.weighted+=(r-l)*(1+Math.max(0,...ps.filter(([a,b])=>a<=l&&b>=l).map(x=>x[2])));}}series.seen.set(key,merge([...seen,...file.ranges]));}
  const matching=groups.filter(x=>x.run_id===run.name);let tokens=0,missing=!matching.length;
  for(const g of matching){const fields=g.provider_convention==='openai_prompt_includes_cache'?['input_tokens','output_tokens']:['input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens'];if(!['openai_prompt_includes_cache','claude_reported_categories'].includes(g.provider_convention))missing=true;missing ||= !!g.unknown_usage||fields.some(k=>(g.missing_fields?.[k]||0)>0);for(const k of fields)if(Number.isFinite(g.totals?.[k]))tokens+=g.totals[k];}
  series.tokens+=tokens;series.incomplete ||= missing||!!run.summary.collection_errors;
  series.points.push({run_id:run.name,started_at:run.time,tokens:series.tokens,run_tokens:matching.length?tokens:null,lines:series.lines,weighted_lines:Math.round(series.weighted*100)/100,partial:series.incomplete,usage_missing:missing,risk_fallback:priorities.size===0});
 }
 const value={project,generated_at:usage?.generated_at||null,granularity:'round',token_scope:'orchestrator',series:[...versions.values()].map(({seen,...row})=>row)};
 value.timeline=timelines.get(key) || {series:[],loading:true};
 if(!pending.has(key) && Date.now()-(timelineTimes.get(key)||0)>30000){
  pending.add(key);
  execFile(process.env.RSI_PYTHON || 'python3',[path.join(repo,'scripts/workflow/coverage_timeline.py'),repo,project],{timeout:30000,maxBuffer:32*1024*1024,encoding:'utf8'},(error,output)=>{
   try { if(error)throw error;timelines.set(key,JSON.parse(output)); } catch {if(!timelines.has(key))timelines.set(key,{series:[],unavailable:true});}
   timelineTimes.set(key,Date.now());pending.delete(key);cache.delete(key);
  });
 }

 cache.set(key,{time:Date.now(),value});return value;
}
