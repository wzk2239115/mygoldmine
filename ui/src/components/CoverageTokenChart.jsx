import {circledCount,reportMarkers} from '../coverage-report-markers.js';
import {useEffect,useRef,useState} from 'react';
const short=x=>Number(x).toLocaleString('en-US',{maximumFractionDigits:1});
function Figure({points,runs=[],markers=[],unplaced=0,axis,metric,title,xlabel,filename,color}){
 const ref=useRef(null),maxX=Math.max(1,...points.map(p=>p[axis]),...runs.map(r=>r[axis]).filter(Number.isFinite),...markers.map(r=>r[axis])),maxY=Math.max(1,...points.map(p=>p[metric]));
 const x=v=>80+v/maxX*650,y=v=>250-v/maxY*205;
 let d='M80 250';for(const p of points)d+=`H${x(p[axis])}V${y(p[metric])}`;if(points.length)d+='H730';
 function download(){const blob=new Blob([new XMLSerializer().serializeToString(ref.current)],{type:'image/svg+xml'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename+'.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 return <article style={{minWidth:0}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><strong>{title}</strong><button className="cycle-control" onClick={download} disabled={!points.length}>下载 SVG</button></div>
 <svg ref={ref} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 325" role="img" aria-label={title} style={{width:'100%',background:'#fff',borderRadius:4,marginTop:12}} fontFamily="Arial, Helvetica, sans-serif" fontSize="12" fill="#222">
 <rect width="780" height="325" fill="white"/>
 {[0,.25,.5,.75,1].map(t=><g key={t}><line x1="80" y1={y(t*maxY)} x2="730" y2={y(t*maxY)} stroke="#e4e6e8" strokeWidth=".7"/><text x="70" y={y(t*maxY)+4} textAnchor="end">{short(t*maxY/1000)}</text><line x1={x(t*maxX)} y1="250" x2={x(t*maxX)} y2="255" stroke="#222"/><text x={x(t*maxX)} y="273" textAnchor="middle">{short(t*maxX/(axis==='seconds'?60:1e6))}</text></g>)}
 <path d="M80 40V250H730" fill="none" stroke="#222" strokeWidth="1"/>
 <text x="80" y="25">{metric==='lines'?'Unique lines read (×10³)':'Risk-weighted lines (×10³)'}</text>
 {runs.map((run,index)=>{
   const start=index?runs[index-1][axis]:0,end=run[axis];
   if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)return null;
   const center=x((start+end)/2),label=`Run ${index+1} · II`;
   return <g key={run.run_id} className="coverage-run-boundary">
     {index>0?<line x1={x(start)} y1="42" x2={x(start)} y2="250" stroke="#7c838b" strokeWidth="1" strokeDasharray="4 4"><title>{`第 ${index+1} 次运行开始：${run.run_id}`}</title></line>:null}
     <rect x={center-32} y="44" width="64" height="17" fill="white" fillOpacity=".92"/>
     <text x={center} y="56" textAnchor="middle" fontSize="10" fill="#525b66">{label}<title>{run.run_id}</title></text>
   </g>;
 })}
 {points.length?<path d={d} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round"/>:<text x="400" y="150" textAnchor="middle">No aligned observations available</text>}
 {markers.map((marker,index)=>{
   const px=x(marker[axis]),py=y(marker[metric]),ly=Math.max(77,py-20-(index%3)*18),label=circledCount(marker.count);
   const tip='本轮新增 '+marker.count+' 份当前可阅读的验证报告 · '+marker.run_id+
    '\n阶段 II 累计 Token：'+short(marker.tokens)+'（已关联用量下界）'+
    '\n按所属轮次阶段 II 终点标注，非报告实际生成时刻；不含其他阶段成本。\n'+
    marker.reports.map(row=>row.id+' '+row.title).join('\n');
   return <g key={marker.run_id} className="coverage-report-marker" role="img" tabIndex="0" aria-label={'本轮新增 '+marker.count+' 份验证报告'}>
    <title>{tip}</title>
    <line x1={px} y1={py} x2={px} y2={ly} stroke="#b77913" strokeDasharray="2 2"/>
    <text x={px} y={py+5} textAnchor="middle" fontSize="21" fill="#b77913" stroke="white" strokeWidth=".5">★</text>
    <rect x={Math.min(700,Math.max(80,px-22))} y={ly-15} width="44" height="21" rx="10" fill="#fff8e7" stroke="#d7ad59"/>
    <text x={Math.min(722,Math.max(102,px))} y={ly} textAnchor="middle" fontSize="16" fill="#80580a">{label}</text>
   </g>;
 })}
 <text x="405" y="307" textAnchor="middle">{xlabel}</text>
 </svg><small>{points.length.toLocaleString()} 个观测点 · 阶梯线，不插值 · 虚线分隔运行，编号对应阶段 II 的各次观测 · ★①/② 表示该轮新增 1/2 份验证报告{unplaced?' · '+unplaced+' 份报告暂无对应曲线位置':null}</small></article>;
}
export default function CoverageTokenChart({data}){
 const [version,setVersion]=useState(''),[metric,setMetric]=useState('lines');
 const [reports,setReports]=useState([]),[reportError,setReportError]=useState(false);
 useEffect(()=>{
  const controller=new AbortController();let busy=false;
  async function refresh(){if(busy)return;busy=true;try{
   const response=await fetch('/api/verified-reports',{signal:controller.signal});
   if(!response.ok)throw Error('报告读取失败');
   const value=await response.json();setReports(value.items || []);setReportError(false);
  }catch(error){if(error.name!=='AbortError')setReportError(true);}finally{busy=false;}}
  refresh();const timer=setInterval(refresh,30000);
  return ()=>{clearInterval(timer);controller.abort();};
 },[]);
 const fine=data?.timeline?.series||[],all=fine.length?fine:(data?.series||[]),s=all.find(x=>x.source_version===version)||all.at(-1);
 const tokenPoints=s?.token_points||(s?.points||[]).filter(x=>x.run_tokens!==null),timePoints=s?.time_points||[];
 const tokens=reportMarkers(s,reports,data?.project,'tokens'),times=reportMarkers(s,reports,data?.project,'seconds');
 const rounds=s?.runs?.length||s?.points?.length||0;
 return <section className="coverage-token-chart" aria-label="AgentCov 事件级覆盖曲线">
 <header><strong>AgentCov · 覆盖曲线</strong><div>
 <select aria-label="覆盖曲线源码版本" value={s?.source_version||''} onChange={e=>setVersion(e.target.value)}>{all.map(row=><option key={row.source_version} value={row.source_version}>{row.source_version.slice(0,12)} · {row.runs?.length||row.points?.length||0} 次运行观测</option>)}</select>
 <select aria-label="覆盖曲线指标" value={metric} onChange={e=>setMetric(e.target.value)}><option value="lines">去重读取行数</option><option value="weighted_lines">风险加权覆盖</option></select></div></header>
 <div className="coverage-paper-figures">
 <Figure markers={tokens.markers} unplaced={tokens.unplaced} runs={s?.runs||s?.points||[]} points={tokenPoints} axis="tokens" metric={metric} title="图一 · 覆盖与累计 Token" xlabel="Cumulative stage-II tokens (millions, recorded)" filename="figure1-coverage-tokens" color="#2563a6"/>
 <Figure markers={times.markers} unplaced={times.unplaced} runs={s?.runs||[]} points={timePoints} axis="seconds" metric={metric} title="图二 · 覆盖随时间变化" xlabel="Cumulative observation time (minutes)" filename="figure2-coverage-time" color="#23816e"/>
 </div>
 <p>{rounds} 次运行有读取观测，不代表完成同样数量的八阶段流程。时间曲线使用读取事件时间，各次运行间的空闲不计入横轴。Token 使用带时间戳或工具调用编号可关联的真实请求用量，无法定位的历史请求不均摊补造；横轴为已关联用量下界。{s?.missing_requests?` 有 ${s.missing_requests.toLocaleString()} 条用量记录无法定位。`:''}{!fine.length?' 当前仅有轮次汇总，事件曲线暂不可用。':''}</p>
 <p>★ 圈内数字表示同轮新增的验证报告数，例如 ① 为 1 份、② 为 2 份；悬浮星标查看报告。标记位于所属轮次的阶段 II 观测终点，不是实际报告生成时刻；Token 不含后续阶段消耗。{reportError?' 报告标记更新失败，暂时保留上次结果。':null}</p>
 <small>按源码版本分组；跨运行读取范围去重。保留现有子智能体采集口径；读取量不等于理解或漏洞召回率。</small>
 </section>;
}
