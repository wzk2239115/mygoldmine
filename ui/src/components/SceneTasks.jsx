import TeamAgentIcon from './TeamAgentIcon.jsx';
import {taskStateLabel} from '../task-selection.js';
export default function SceneTasks({scenes,onSelect,images=[],onImage}) {
 const tasks=scenes?.tasks || [];
 if(!tasks.length)return null;
 return <section className="verify-tasks" aria-label="攻击场景设计队员">
  <div className="verify-tasks-heading">已登记 {tasks.length} 条任务 · 已结束 {scenes.processedCount} 条 · 当前逐条执行</div>
  <p className="verify-batch-counts">运行中 {tasks.filter(task=>task.state==='running').length} · 已中断 {tasks.filter(task=>task.state==='interrupted').length}。后续候选在开始设计时登记。</p>
  <div className="verify-task-grid">{tasks.map(task=>{const image=images.find(item=>item.name.endsWith('/scene-'+task.id+'.webp'));return <div key={task.id} className="verify-task">
   <button type="button" onClick={()=>onSelect(task.id)} aria-label={`查看场景设计队员 ${task.id} 轨迹 · ${taskStateLabel(task)} · ${task.title}`}>
    <span><span className="verify-task-identity"><TeamAgentIcon node="visual" active={task.state==='running'} /><strong>{task.id}</strong></span><small className={`task-state state-${task.state}`}>{taskStateLabel(task)}</small></span>
    <span className="verify-task-title">{task.title}</span><span className="member-open-trace">查看轨迹 →</span>
   </button>
   {image?<button type="button" className="member-image-button" aria-label={`查看 ${task.id} 图片`} onClick={()=>onImage?.(image)}>AI 图片 ↗</button>:null}
  </div>})}</div>
 </section>;
}
