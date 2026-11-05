import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {nodeAttempts} from './node-retries.mjs';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return null;}};
const fields={visual:'scenes',verify:'verification','redteam-lab':'construction','redteam-agent':'execution',judge:'review'};
export function attachCandidateFlow(run,nodes) {
 const file=path.join(run.runDir,'audit-report.json');
 const report=read(file);const findings=report?.findings || report?.vulnerabilities;
 if(!Array.isArray(findings))return;
 const hash=createHash('sha256').update(fs.readFileSync(file)).digest('hex');
 const blue=new Map((nodes.find(n=>n.id==='verify')?.verification?.tasks || []).map(t=>[t.id,t]));
 const execution=new Map((nodes.find(n=>n.id==='redteam-agent')?.execution?.tasks || []).map(t=>[t.id,t]));
 const ids=new Set(findings.map(row=>row.id || row.finding_id));
 for(const node of nodes) {
  if(node.id!=='orchestrator' && !fields[node.id])continue;
  const latest=nodeAttempts(run.runDir,node.id).at(-1);
  const root=latest?.workspace || run.runDir;
  const plan=read(path.join(root,node.id==='verify'?'verify/agent/selection.json':'redteam/selection.json'));
  const reasons=new Map([...(plan?.deferred || []),...(plan?.excluded || [])].map(item=>[item.id,item.reason]));
  const tasks=node[fields[node.id]]?.tasks || [];
  const byId=new Map(tasks.map(t=>[t.id,t]));
  let stale=Boolean(plan?.report_sha256 && ['verify','redteam-lab'].includes(node.id) && plan.report_sha256!==hash);
  if(latest && fs.existsSync(path.join(root,'audit-report.json')))stale ||= !fs.readFileSync(path.join(root,'audit-report.json')).equals(fs.readFileSync(file));
  if(node.id==='redteam-lab' && plan?.blue_attempt_id) {
    const currentBlue=nodeAttempts(run.runDir,'verify').at(-1)?.id || 'original';
    stale ||= plan.blue_attempt_id!==currentBlue;
  }
  const rows=findings.map(finding=>{
   const id=finding.id || finding.finding_id,task=byId.get(id);
   let state='pending',reason='本阶段尚无执行记录，仍待处理';
   if(node.id==='orchestrator'){state='recorded';reason='已写入审计报告，尚不代表运行验证通过';}
   else if(task){state=task.state || 'recorded';reason=task.reason || task.label || '本阶段已记录';}
   else if(reasons.has(id) && ['verify','redteam-lab'].includes(node.id))reason=reasons.get(id);
   else if(['redteam-lab','redteam-agent'].includes(node.id))reason=!blue.has(id)?'尚无蓝队验证记录，等待前置验证':blue.get(id).verdict!=='confirmed'?'蓝队未确认，保留结论并等待补证':'蓝队已确认，本阶段尚无记录，仍待处理';
   else if(node.id==='judge')reason=execution.get(id)?.captured?'已取得捕获结果，尚无本阶段审核记录':'尚无来源完整的成功捕获证据，不启动审核';
   if(stale){state='stale';reason='本阶段上游报告或验证批次已变化，旧记录不能证明本候选已处理';}
   return {id,title:finding.title || id,severity:finding.severity || 'unknown',state,reason,hasRecord:node.id==='orchestrator' || Boolean(task)};
  });
  const recorded=rows.filter(row=>row.hasRecord).length;
  node.flow={total:rows.length,recorded,pending:rows.length-recorded,stale,orphans:tasks.filter(t=>!ids.has(t.id)).map(t=>t.id),rows};
 }
}
