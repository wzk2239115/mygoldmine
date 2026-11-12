import fs from 'node:fs';
import path from 'node:path';

function read(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { return null; }
}

export function activeWorkflow(runDir, project, alive) {
  const runsRoot = path.resolve(runDir, '../..');
  const lock = path.join(runsRoot, `.node-retry-${project}.lock`);
  const claim = read(path.join(lock, 'workflow-owner.json'));
  if (!claim?.id || !claim.file) return null;
  const file = path.resolve(claim.file);
  const state = read(file);
  const workflowRoot = path.resolve(runDir + '.meta', 'workflows');
  const recoveredFrom = state?.recoveredFrom;
  const originalRoot = typeof recoveredFrom === 'string' &&
    path.resolve(recoveredFrom + '-recovery') === path.resolve(runDir)
      ? path.resolve(recoveredFrom + '.meta', 'workflows') : null;
  if (![workflowRoot, originalRoot].includes(path.dirname(path.dirname(file))) ||
      path.basename(file) !== 'state.json') return null;
  if (state?.id !== claim.id || state?.project !== project ||
      path.resolve(state.runDir || '') !== path.resolve(runDir) ||
      path.resolve(state.lock || '') !== lock ||
      !['running', 'queued'].includes(state.status)) return null;
  if (!Number.isSafeInteger(state.coordinatorPid) || state.coordinatorPid <= 0 ||
      !alive(state.coordinatorPid)) return null;
  return state;
}
