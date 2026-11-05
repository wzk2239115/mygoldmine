import TeamAgentIcon from './TeamAgentIcon.jsx';
import {taskStateLabel} from '../task-selection.js';
export default function AgentTasks({execution,onSelect}) {
 const tasks=execution?.tasks || [];
 if(!tasks.length)return null;
 return <section className="verify-tasks" aria-label="红队执行队员">
  <div className="verify-tasks-heading">执行进度 · {execution.processedCount}/{execution.selectedCount} 条已结束{execution.concurrency ? ` · 并发上限 ${execution.concurrency}` : ''}</div>
  <p className="verify-batch-counts">运行中 {tasks.filter(task=>task.state==='running').length} · 待运行 {tasks.filter(task=>task.state==='queued').length} · 已结束 {execution.processedCount}</p>
  <div className="verify-task-grid">{tasks.map(task=><div key={task.id} className="verify-task">
   <button type="button" onClick={()=>onSelect(task.id)} aria-label={`查看红队执行队员 ${task.id} 轨迹 · ${taskStateLabel(task)} · ${task.title}`}>
    <span><span className="verify-task-identity"><TeamAgentIcon team="red" active={task.state==='running'} /><strong>{task.id}</strong></span><small className={`task-state state-${task.state}`}>{taskStateLabel(task)}</small></span>
    <span className="verify-task-title">{task.title}</span><span className="member-open-trace">查看轨迹 →</span>
   </button>
  </div>)}</div>
 </section>;
}
