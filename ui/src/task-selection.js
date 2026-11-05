export function candidateTasks(node) {
  return node.verification || node.construction || node.execution || node.scenes || node.review || null;
}
export function isCandidateNode(node) {
  return ['verify', 'redteam-lab', 'redteam-agent', 'visual', 'judge'].includes(node.id) || Boolean(candidateTasks(node));
}
export function initialTaskSelection(node) {
  return {batchId: candidateTasks(node)?.attemptId || 'original', taskId: null, history: false, traceId: ''};
}
export function resolveTaskSelection(node, traces, selection) {
  const info = candidateTasks(node), tasks = info?.tasks || [];
  const batchId = info?.attemptId || 'original';
  const current = selection.batchId === batchId ? selection : initialTaskSelection(node);
  const task = current.history ? null : tasks.find(item => item.id === current.taskId) || null;
  // Team sessions are opened only after an explicit member or history selection.
  const trace = task ? traces.find(item => item.id === task.traceId) || null
    : !current.history ? null
    : traces.find(item => item.id === current.traceId) || traces[0] || null;
  return {batchId, task, trace};
}
export function taskStateLabel(task) {
  if (task.state === 'blocked') return '等待前置证据';
  if (task.state === 'queued') return '待运行';
  if (task.state === 'running') return '运行中';
  if (['interrupted', 'cancelled'].includes(task.state)) return '已中断';
  if (task.state === 'failed') return '已结束 · 失败';
  return task.label && task.label !== '已结束' ? `已结束 · ${task.label}` : '已结束';
}
