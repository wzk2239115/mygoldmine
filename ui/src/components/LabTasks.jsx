import {useRef,useState} from 'react';
import TeamAgentIcon from './TeamAgentIcon.jsx';
export default function LabTasks({project,runId,construction,traces,onSelect,selectedId}) {
 const [report,setReport]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState('');
 const sequence=useRef(0), tasks=construction?.tasks || [];
 if(!tasks.length)return null;
 async function open(task) {
  const request=++sequence.current;setLoading(task.id);setError('');setReport(null);
  try {
   const response=await fetch(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/lab-tasks/${encodeURIComponent(task.id)}/report?attempt=${encodeURIComponent(construction.attemptId)}`);
   const payload=await response.json();if(!response.ok)throw Error(payload.error);
   if(request===sequence.current)setReport(payload.report);
  } catch(error){if(request===sequence.current)setError(error.message);}finally{if(request===sequence.current)setLoading('');}
 }
 return <details className="verify-tasks lab-tasks" open>
  <summary>场景构建 · {construction.processedCount}/{construction.selectedCount} 条已结束 · {construction.legacy?'旧版串行批次':`并发上限 ${construction.concurrency}`}</summary>
  <p className="verify-batch-counts">构建中 {construction.running} · 可用 {construction.ready} · 受阻 {construction.blocked}</p>
  {!report?<div className="verify-task-grid">{tasks.map(task=><div key={task.id} className={`verify-task ${selectedId===task.traceId?'is-active':''}`}>
   <button type="button" disabled={!traces.some(trace=>trace.id===task.traceId)} onClick={()=>onSelect(task.traceId)} title={task.title}>
    <span><span className="verify-task-identity"><TeamAgentIcon team="red" active={task.state==='running'} /><strong>{task.id}</strong></span><small>{task.label}</small></span><span className="verify-task-title">{task.title}</span>
   </button>
   <button type="button" className="traj-button" aria-label={`查看 ${task.id} 场景交付`} disabled={!task.hasReport || loading===task.id} onClick={()=>open(task)}>{loading===task.id?'读取中…':'查看交付'}</button>
  </div>)}</div>:<section className="verify-report-preview"><button type="button" className="traj-button" onClick={()=>{sequence.current++;setReport(null);setLoading('');}}>关闭交付</button><strong>{report.id}</strong><pre>{report.blocked || report.report || JSON.stringify(report.scenario,null,2)}</pre>{report.scenario && report.report?<details><summary>场景配置</summary><pre>{JSON.stringify(report.scenario,null,2)}</pre></details>:null}</section>}
  {error?<p role="alert">{error}</p>:null}
 </details>;
}
