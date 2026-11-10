
import fs from 'node:fs';
import path from 'node:path';
import {acceptedStageDelivery} from './delivery-contract.mjs';
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file+'.tmp',JSON.stringify(value,null,2));fs.renameSync(file+'.tmp',file);};
export function partialAgentDelivery(workspace) {
 const file=path.join(workspace,'redteam/summary.json'),summary=JSON.parse(fs.readFileSync(file,'utf8'));
 if(!Array.isArray(summary.results))throw Error('红队执行批次缺少成员结果');
 const deliveries=[],excluded=[],seen=new Set();
 for(const row of summary.results){
  if(!/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(row.id || '') || seen.has(row.id))throw Error('红队成员编号无效或重复');
  seen.add(row.id);
  if(!row.run_dir)continue;
  try {
   const root=path.resolve(row.run_dir);
   if(!root.startsWith(path.resolve(workspace)+path.sep) || fs.realpathSync(root)!==root)throw Error('执行成员目录越界或包含链接');
   const delivery=acceptedStageDelivery('redteam-agent',root,1);
   if(!delivery.deliveries.some(item=>item.artifact===path.join(root,'stage-result.json')))throw Error('缺少最终执行交付');
   deliveries.push(...delivery.deliveries);row.delivery_status='accepted';
  }catch(error){
   row.delivery_status='missing';row.delivery_error=error.message;
   row.captured=false;
   if(row.status==='flag_captured')row.status='delivery_failed';
   excluded.push({id:row.id,reason:error.message});
  }
  const task=path.join(workspace,'redteam/tasks',row.id+'.json');
  let saved={};try{saved=JSON.parse(fs.readFileSync(task,'utf8'));}catch{}
  write(task,{...saved,delivery_status:row.delivery_status,delivery_error:row.delivery_error,
   status:row.status,captured:row.captured,state:'completed'});
 }
 summary.captured=summary.results.filter(row=>row.captured && row.delivery_status==='accepted').length;
 summary.delivery_missing=excluded.length;
 if(excluded.length)summary.status='degraded';
 write(file,summary);
 return {stage:'redteam-agent',root:workspace,accepted:deliveries.length,deliveries,excluded};
}
