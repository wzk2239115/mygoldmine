import {useRef,useState} from 'react';
import TeamAgentIcon from './TeamAgentIcon.jsx';

export default function VerifyTasks({project,runId,verification,traces,onSelect,selectedId}) {
 const [report,setReport]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState('');
 const sequence=useRef(0);
 const tasks=verification?.tasks || [];
 if(!tasks.length)return null;
 const counts=verification.counts || {};
 const severityLabels={critical:'严重',high:'高危',medium:'中危',low:'低危',info:'信息'};
 const severities=Object.entries(severityLabels).map(([key,label])=>[label,tasks.filter(task=>task.severity===key).length]).filter(([,count])=>count>0).map(([label,count])=>`${label} ${count}`).join(' · ');
 const blocked=tasks.filter(task=>task.verdict==='blocked' && task.reason);
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
  <summary>候选进度 · {finished}/{verification.selectedCount ?? tasks.length} 条已结束 · {verification.legacy?'旧版串行批次':`并发上限 ${verification.concurrency}`}</summary>
  <p className="verify-batch-counts">{[['confirmed','确认'],['rejected','排除'],['inconclusive','待定'],['blocked','受阻']].filter(([key])=>counts[key]>0).map(([key,label])=>`${label} ${counts[key]}`).join(' · ')}</p>
  <details className="verify-batch-scope"><summary>本批次范围{verification.reportTotal !== null ? `：选中 ${verification.selectedCount} / 报告 ${verification.reportTotal} 条` : ''}</summary><p>{severities ? `本批次包含：${severities}。` : ''}这里只显示本批次选中的候选，未选中的候选不代表已经验证。执行记录按智能体会话、执行器日志和批次日志分别计数。</p>{blocked.map(task=><p key={task.id}><strong>{task.id} 受阻：</strong>{task.reason}</p>)}</details>
  {!report ? <div className="verify-task-grid">{tasks.map(task=><div key={task.id} className={`verify-task ${selectedId===task.traceId?'is-active':''}`}>
   <button type="button" onClick={()=>onSelect(task.traceId)} disabled={!traces.some(trace=>trace.id===task.traceId)} title={task.title}>
    <span><span className="verify-task-identity"><TeamAgentIcon team="blue" active={task.state==='running'} /><strong>{task.id}</strong></span><small>{task.label}</small></span><span className="verify-task-title">{task.title}</span>
   </button>
   <button type="button" className="traj-button" aria-label={`查看 ${task.id} 验证报告`} disabled={!task.hasReport || loading===task.id} onClick={()=>openReport(task)}>{loading===task.id?'读取中…':'查看报告'}</button>
  </div>)}</div> : null}
  {error?<p role="alert">{error}</p>:null}
  {report?<section className="verify-report-preview"><button type="button" className="traj-button" onClick={()=>{sequence.current++;setLoading('');setReport(null);}}>关闭报告</button><strong>{report.task.id} · {report.task.label}</strong><p>{typeof report.data.reason === 'string' ? report.data.reason : report.task.reason || '详见完整报告'}</p><details><summary>完整报告</summary><pre>{JSON.stringify(report.data,null,2)}</pre></details></section>:null}
 </details>;
}
