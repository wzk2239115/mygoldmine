
export const projectIsBusy=project=>project.activity
 ? ['running','queued'].includes(project.activity.status)
 : Boolean(project.isLive);
export const runningProjectCount=board=>Array.isArray(board?.projects)
 ? new Set(board.projects.filter(p=>p.activity?p.activity.status==='running':p.isLive).map(p=>p.id)).size
 : new Set((board?.liveRuns || []).filter(r=>r.project && !r.finished && r.isLive!==false).map(r=>r.project)).size;
