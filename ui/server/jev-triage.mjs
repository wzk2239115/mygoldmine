import fs from 'node:fs';
import path from 'node:path';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
export function jevTriage(run) {
 const root=path.join(run.runDir,'triage');
 if(!fs.existsSync(root))return null;
 const names=fs.readdirSync(root);
 const files=names.filter(name=>/^jev-[\w-]+(?:\.progress)?\.json$/.test(name));
 const newest=files.map(name=>({name,time:fs.statSync(path.join(root,name)).mtimeMs})).sort((a,b)=>b.time-a.time);
 const progressEntry=newest.find(item=>item.name.endsWith('.progress.json'));
 const progress=progressEntry?read(path.join(root,progressEntry.name)):null;
 const reportName=progressEntry?progressEntry.name.replace('.progress.json','.json'):newest.find(item=>!item.name.endsWith('.progress.json'))?.name;
 const report=reportName?read(path.join(root,reportName)):null;
 // A report from an earlier invocation must not override newer running progress.
 const useReport=report && (!progressEntry || progress?.status!=='running' || fs.statSync(path.join(root,reportName)).mtimeMs>=progressEntry.time);
 const data=useReport?report:progress;
 if(!data && !names.includes('jev.log'))return null;
 const raw=path.join(run.runDir,'raw.jsonl');
 const active=Boolean(run.isLive) && (!fs.existsSync(raw) || fs.statSync(raw).size===0);
 const status=useReport?(report.errors?.length?'partial':'completed'):progress?.status==='running'?(active?'running':'incomplete'):progress?.status || (active?'running':'unavailable');
 const units=(data?.units || []).slice().sort((a,b)=>Number(b.priority)-Number(a.priority));
 return {status,profile:data?.profile || '',model:data?.model_returned || data?.model_requested || '',stats:data?.stats || {},plannedRequests:data?.planned_requests ?? null,workers:data?.workers ?? null,processedUnits:useReport?units.length:data?.processed_units ?? null,failedUnits:useReport?new Set((report.errors || []).map(item=>item.unit)).size:data?.failed_units ?? null,shown:Math.min(units.length,80),totalResults:useReport?units.length:data?.processed_units ?? 0,updatedAt:data?.generated_at || null,notice:!data?'本批次尚无细分进度记录，等待初筛报告；旧进程不会补写新增进度。':status==='incomplete'?'初筛未留下完成记录，已有结果不代表完整覆盖。':'',units:units.slice(0,80).map(item=>({id:item.id,path:item.path,lineStart:item.line_start,lineEnd:item.line_end,priority:item.priority,flags:item.flags || {},mitigations:item.mitigations || {},cached:Boolean(item.cached)}))};
}
