
export function projectActivity(project,isLive,tickets,readState=()=>null) {
 const rows=(tickets || []).filter(row=>row.project===project);
 const active=rows.find(row=>row.status==='active');
 if(active)return {status:'running',label:'运行中',position:0};
 const queued=rows.find(row=>row.status==='queued');
 if(queued){
  const state=readState(queued.file);
  const position=state?.admission?.status==='queued'?state.admission.position:0;
  return {status:'queued',label:'排队中',position:Number(position)||0};
 }
 return {status:isLive?'running':'idle',label:isLive?'运行中':'',position:0};
}
