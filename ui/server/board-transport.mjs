
import {gzip} from 'node:zlib';
const heavy=new Set(['stageResults','sourcePaths','evidence','files','rootCause','reproduction',
 'impact','remediation','preconditions','autoDetail','relatedArtifacts','raw','description','finalReviewNote']);
export function summarizeBoard(board) {
 return {...board,detailMode:'lazy',findings:board.findings.map(f=>{
  const row=Object.fromEntries(Object.entries(f).filter(([key])=>!heavy.has(key)));
  return {...row,evidenceCount:f.evidence?.length || 0,
   searchText:[f.rootCause,f.notes].filter(Boolean).join(' ').toLowerCase()};
 })};
}
export function sendJsonResponse(res,status,payload) {
 const body=Buffer.from(JSON.stringify(payload));
 const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','Vary':'Accept-Encoding'};
 const accept=String(res.req?.headers?.['accept-encoding'] || '');
 const gzipAccepted=accept.split(',').some(part=>{
  const [name,...params]=part.trim().split(';');
  return name==='gzip' && !params.some(p=>/^\s*q\s*=\s*0(?:\.0*)?\s*$/.test(p));
 });
 if(body.length<4096 || !gzipAccepted){res.writeHead(status,{...headers,'Content-Length':body.length});res.end(body);return;}
 gzip(body,{level:4},(error,compressed)=>{
  if(res.destroyed)return;
  const result=error?body:compressed;
  res.writeHead(status,{...headers,...(!error?{'Content-Encoding':'gzip'}:{}),'Content-Length':result.length});
  res.end(result);
 });
}
