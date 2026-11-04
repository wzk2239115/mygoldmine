import {useRef,useState} from 'react';

export default function VerifyTasks({project,runId,verification,traces,onSelect,selectedId}) {
 const [report,setReport]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState('');
 const sequence=useRef(0);
 const tasks=verification?.tasks || [];
 if(!tasks.length)return null;
 const finished=tasks.filter(task=>!['running','queued'].includes(task.state)).length;
 async function openReport(task) {
  const request=++sequence.current;
  setLoading(task.id);setError('');setReport(null);
  try {
   const response=await fetch(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/verify-tasks/${encodeURIComponent(task.id)}/report?attempt=${encodeURIComponent(verification.attemptId)}`);
   const payload=await response.json();if(!response.ok)throw Error(payload.error);
   if(request===sequence.current)setReport({task,data:payload.report});
  } catch(error){if(request===sequence.current)setError(error.message);}finally{if(request===sequence.current)setLoading('');}
 }
 return <details className="verify-tasks" open>
  <summary>候选验证 · {finished}/{tasks.length} 已结束 · {verification.legacy?'旧版串行批次':`并发上限 ${verification.concurrency}`}</summary>
  {!report ? <div className="verify-task-grid">{tasks.map(task=><div key={task.id} className={`verify-task ${selectedId===task.traceId?'is-active':''}`}>
   <button type="button" onClick={()=>onSelect(task.traceId)} disabled={!traces.some(trace=>trace.id===task.traceId)} title={task.title}>
    <span><strong>{task.id}</strong><small>{task.label}</small></span><span className="verify-task-title">{task.title}</span>
   </button>
   <button type="button" className="traj-button" aria-label={`查看 ${task.id} 验证报告`} disabled={!task.hasReport || loading===task.id} onClick={()=>openReport(task)}>{loading===task.id?'读取中…':'查看报告'}</button>
  </div>)}</div> : null}
  {error?<p role="alert">{error}</p>:null}
  {report?<section className="verify-report-preview"><button type="button" className="traj-button" onClick={()=>{sequence.current++;setLoading('');setReport(null);}}>关闭报告</button><strong>{report.task.id} · {report.task.label}</strong><p>{typeof report.data.reason === 'string' ? report.data.reason : report.task.reason || '详见完整报告'}</p><details><summary>完整报告</summary><pre>{JSON.stringify(report.data,null,2)}</pre></details></section>:null}
 </details>;
}
