
export function circledCount(n) {
 if(n>=1 && n<=20)return String.fromCodePoint(0x2460+n-1);
 if(n>=21 && n<=35)return String.fromCodePoint(0x3251+n-21);
 if(n>=36 && n<=50)return String.fromCodePoint(0x32b1+n-36);
 return String(n);
}
export function reportMarkers(series,reports,project,axis) {
 const grouped=new Map(),known=new Set();
 for(const report of reports || []) {
  const key=report.key || report.exportId || report.project+'/'+report.runId+'/'+report.id;
  if(report.project!==project || known.has(key))continue;
  known.add(key);
  if(!grouped.has(report.runId))grouped.set(report.runId,[]);
  grouped.get(report.runId).push(report);
 }
 const markers=[];let unplaced=0;
 for(const [runId,items] of grouped) {
  const run=series?.runs?.find(row=>row.run_id===runId) || series?.points?.find(row=>row.run_id===runId);
  const points=axis==='tokens'?series?.token_points || series?.points:series?.time_points;
  const point=(points || []).filter(row=>row.run_id===runId).at(-1);
  const position=run?.[axis] ?? point?.[axis];
  if(!point || !Number.isFinite(position) || (axis==='tokens' && point.run_tokens===null)) {
   unplaced+=items.length;continue;
  }
  markers.push({...point,[axis]:position,count:items.length,reports:items,run_id:runId});
 }
 return {markers,unplaced};
}
