
import fs from 'node:fs';
import path from 'node:path';
import {acceptedStageDelivery} from './delivery-contract.mjs';

const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file+'.tmp',JSON.stringify(value,null,2));fs.renameSync(file+'.tmp',file);};
export function partialLabDelivery(workspace) {
 const root=path.join(workspace,'redteam'),file=path.join(root,'summary.json');
 const summary=JSON.parse(fs.readFileSync(file,'utf8'));
 if(!Array.isArray(summary.results))throw Error('场景构建批次缺少成员结果');
 const deliveries=[],excluded=[],seen=new Set();
 for(const row of summary.results) {
  if(!/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(row.id || '') || seen.has(row.id))throw Error('场景构建成员编号无效或重复');
  seen.add(row.id);
  try {
   const folder=path.join(root,'labs',row.id);
   if(fs.lstatSync(folder).isSymbolicLink())throw Error('成员目录不能是符号链接');
   const accepted=acceptedStageDelivery('redteam-lab',folder,1);
   if(row.status==='built' && !accepted.deliveries.some(item=>item.artifact===path.join(folder,'scenario.json')))throw Error('当前场景没有有效交付回执');
   deliveries.push(...accepted.deliveries);
   row.delivery_status='accepted';delete row.delivery_error;
  } catch(error) {
   row.delivery_status='missing';row.delivery_error=error.message;
   excluded.push({id:row.id,reason:error.message});
   if(row.status==='built'){row.status='build_failed';row.error='场景未通过交付验收';}
  }
  const task=path.join(root,'tasks',row.id+'.json');
  let saved={};try{saved=JSON.parse(fs.readFileSync(task,'utf8'));}catch{}
  write(task,{...saved,id:row.id,status:row.status,delivery_status:row.delivery_status,
   delivery_error:row.delivery_error || '',error:row.error || '',state:'completed'});
 }
 summary.delivery_accepted=seen.size-excluded.length;summary.delivery_missing=excluded.length;
 summary.ready=summary.results.filter(row=>row.status==='built' && row.delivery_status==='accepted').length;
 summary.blocked=summary.results.length-summary.ready;
 summary.counts={built:summary.ready,blocked:summary.blocked};
 summary.status=excluded.length || summary.blocked?'degraded':'completed';
 write(file,summary);
 return {stage:'redteam-lab',root:workspace,accepted:deliveries.length,deliveries,excluded};
}
