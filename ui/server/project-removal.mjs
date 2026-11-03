import fs from 'node:fs';
import path from 'node:path';

export function removeProjectRecords(repoRoot, project) {
  if (!/^[a-z0-9][a-z0-9._-]{0,79}$/.test(project) || project === '.' || project === '..') throw new Error('项目标识无效');
  const dataRoot = path.join(repoRoot, 'ui/data');
  const files = ['projects.json', 'finding-ledger.json', 'state.json', 'curated.json', 'auto-state.json', 'refine-state.json', 'flow-state.json', 'flow-queue.json', 'watch-state.json'];
  const updates = new Map();
  for (const name of files) {
    const file = path.join(dataRoot, name);
    if (fs.existsSync(file)) updates.set(file, JSON.parse(fs.readFileSync(file, 'utf8')));
  }
  const manifest = path.join(repoRoot, 'targets/manifest.json');
  if (fs.existsSync(manifest)) updates.set(manifest, JSON.parse(fs.readFileSync(manifest, 'utf8')));
  const ids = new Set();
  const ledger = updates.get(path.join(dataRoot, 'finding-ledger.json'));
  for (const collection of [ledger?.findings, ledger?.occurrences]) {
    for (const [id, value] of Object.entries(collection || {})) if (value?.project === project || id.startsWith(`${project}:`)) ids.add(id);
  }
  const owned = value => value && typeof value === 'object' && (value.project === project || value.project_id === project);
  const clean = value => {
    if (Array.isArray(value)) return value.filter(item => !owned(item) && !ids.has(item)).map(clean);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(Object.entries(value).filter(([key, item]) => !key.startsWith(`${project}:`) && !ids.has(key) && !owned(item)).map(([key, item]) => [key, clean(item)]));
  };
  for (const [file, payload] of updates) {
    if (payload.projects) delete payload.projects[project];
    if (payload.latest_by_project) delete payload.latest_by_project[project];
    updates.set(file, clean(payload));
  }
  // Remove the actual run artifacts; no source directory is removed.
  fs.rmSync(path.join(repoRoot, 'runs', project), { recursive: true, force: true });
  for (const [file, payload] of updates) {
    const temporary = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(temporary, JSON.stringify(payload, null, 2) + '\n');
    fs.renameSync(temporary, file);
  }
}
