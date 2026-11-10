import fs from 'node:fs';
import path from 'node:path';
import {acceptedStageDelivery} from './delivery-contract.mjs';
const write=(file,value)=>{const tmp=file+'.tmp';fs.writeFileSync(tmp,JSON.stringify(value,null,2));fs.renameSync(tmp,file);};
export function partialJudgeDelivery(workspace,{persist=true}={}) {
 workspace=path.resolve(workspace);
 const file=path.join(workspace,'judge/summary.json');
 const summary=JSON.parse(fs.readFileSync(file,'utf8'));
 const selection=JSON.parse(fs.readFileSync(path.join(workspace,'judge/selection.json'),'utf8'));
 if(!Array.isArray(summary.results) || !Array.isArray(selection.candidates))throw Error('审核批次缺少成员结果或选择清单');
 const rows=new Map(),selected=new Set();
 const valid=id=>/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(id || '');
 for(const row of summary.results) {
  if(!valid(row.id) || rows.has(row.id))throw Error('审核成员编号无效或重复');
  rows.set(row.id,row);
 }
 const deliveries=[],excluded=[];
 for(const candidate of selection.candidates) {
  if(!valid(candidate.id) || selected.has(candidate.id))throw Error('审核选择清单编号无效或重复');
  selected.add(candidate.id);
  let row=rows.get(candidate.id);
  if(!row){row={id:candidate.id,title:candidate.title,run_dir:candidate.run_dir,status:'judge_error'};summary.results.push(row);}
  try {
   if(!row.run_dir || row.run_dir!==candidate.run_dir)throw Error('审核成员目录与本次选择清单不一致');
   const root=path.resolve(row.run_dir);
   if(!root.startsWith(workspace+path.sep) || fs.realpathSync(root)!==root)throw Error('审核成员目录越界或包含链接');
   const delivery=acceptedStageDelivery('judge',root,1);
   if(!delivery.deliveries.some(item=>item.artifact===path.join(root,'judge.json')))throw Error('缺少正式审核交付');
   deliveries.push(...delivery.deliveries);
   row.delivery_status='accepted';delete row.delivery_error;
  }catch(error){
   row.delivery_status='missing';row.delivery_error=error.message;
   row.status='judge_error';row.reason='审核交付未通过：'+error.message;
   excluded.push({id:row.id,reason:error.message});
  }
 }
 if([...rows.keys()].some(id=>!selected.has(id)))throw Error('审核汇总包含本次未选择的成员');
 summary.approved=summary.results.filter(row=>row.status==='judge_approved' && row.delivery_status==='accepted').length;
 summary.delivery_missing=excluded.length;
 summary.status=excluded.length?'degraded':'completed';
 if(persist)write(file,summary);
 return {stage:'judge',root:workspace,accepted:deliveries.length,deliveries,excluded};
}
