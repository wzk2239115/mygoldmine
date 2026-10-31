export function summarizeRecovery(tasks) {
  if (!tasks || typeof tasks !== 'object' || Array.isArray(tasks)) return null;
  const rows = Object.values(tasks).filter(task => task && typeof task === 'object');
  if (!rows.length) return null;
  const count = status => rows.filter(task => task.status === status).length;
  const active = rows.find(task => task.status === 'running' || task.status === 'retrying');
  return {total: rows.length, reused: count('reused'), completed: count('completed'),
    failed: count('failed'), active: active?.description || null,
    attempt: active && Array.isArray(active.attempts) ? active.attempts.length : 0};
}
