import {BadgeCheck} from 'lucide-react';
import {taskStateLabel} from '../task-selection.js';
export default function JudgeTasks({review,onSelect}) {
 const tasks=review?.tasks || [];
 if(!tasks.length)return null;
 return <section className="verify-tasks" aria-label="独立审核队员">
  <div className="verify-tasks-heading">审核进度 · {review.processedCount}/{review.selectedCount} 条已结束{review.mode==='serial'?' · 本次重跑逐条执行':''}</div>
  <p className="verify-batch-counts">运行中 {tasks.filter(task=>task.state==='running').length} · 待运行 {tasks.filter(task=>task.state==='queued').length} · 等待前置证据 {tasks.filter(task=>task.state==='blocked').length}</p>
  <div className="verify-task-grid">{tasks.map(task=><div key={task.id} className="verify-task">
   <button type="button" onClick={()=>onSelect(task.id)} aria-label={`查看审核队员 ${task.id} 轨迹 · ${taskStateLabel(task)} · ${task.title}`}>
    <span><span className="verify-task-identity"><BadgeCheck size={20} /><strong>{task.id}</strong></span><small className={`task-state state-${task.state}`}>{taskStateLabel(task)}</small></span>
    <span className="verify-task-title">{task.title}</span>{task.reason?<span className="verify-task-title">{task.reason}</span>:null}<span className="member-open-trace">查看轨迹 →</span>
   </button>
  </div>)}</div>
 </section>;
}
