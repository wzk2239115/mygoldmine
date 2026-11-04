export function candidateTasks(node) {
  return node.verification || node.construction || null;
}
export function initialTaskSelection(node) {
  const info = candidateTasks(node), tasks = info?.tasks || [];
  const task = tasks.find(item => item.state === 'running') || tasks[0];
  return {batchId: info?.attemptId || 'original', taskId: task?.id || null, history: false, traceId: ''};
}
export function resolveTaskSelection(node, traces, selection) {
  const info = candidateTasks(node), tasks = info?.tasks || [];
  const batchId = info?.attemptId || 'original';
  const current = selection.batchId === batchId ? selection : initialTaskSelection(node);
  const task = current.history ? null : tasks.find(item => item.id === current.taskId)
    || tasks.find(item => item.state === 'running') || tasks[0] || null;
  // A queued candidate must never fall back to another candidate's session.
  const trace = task ? traces.find(item => item.id === task.traceId) || null
    : traces.find(item => item.id === current.traceId) || traces[0] || null;
  return {batchId, task, trace};
}
export function taskStateLabel(task) {
  if (task.state === 'queued') return '待运行';
  if (task.state === 'running') return '运行中';
  if (['interrupted', 'cancelled'].includes(task.state)) return '已中断';
  if (task.state === 'failed') return '已结束 · 失败';
  return task.label && task.label !== '已结束' ? `已结束 · ${task.label}` : '已结束';
}
