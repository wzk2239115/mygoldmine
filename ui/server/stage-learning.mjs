import fs from 'node:fs';
import path from 'node:path';

const read = file => { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return {}; } };
const candidateCache = new Map();
const CACHE_MAX_AGE_MS = 30_000;

function candidatesByProject(directory) {
  if (!fs.existsSync(directory)) return new Map();
  const now = Date.now();
  const modifiedAt = fs.statSync(directory).mtimeMs;
  const cached = candidateCache.get(directory);
  if (cached && cached.modifiedAt === modifiedAt && now - cached.checkedAt < CACHE_MAX_AGE_MS) {
    return cached.projects;
  }

  const projects = new Map();
  for (const name of fs.readdirSync(directory)) {
    if (!name.endsWith('.json')) continue;
    const value = read(path.join(directory, name));
    if (!value.project) continue;
    if (!projects.has(value.project)) projects.set(value.project, []);
    projects.get(value.project).push({ key: value.key, id: value.id, stage: value.stage });
  }
  candidateCache.set(directory, { modifiedAt, checkedAt: now, projects });
  return projects;
}

export function stageLearningForStages(repoRoot, project, stages) {
  const root = path.join(repoRoot, 'rsi/stage-skills');
  const active = read(path.join(root, 'active.json'));
  const candidates = candidatesByProject(path.join(root, 'candidates')).get(project) || [];
  const pending = candidates.filter(value => active[value.key] !== value.id);
  const counts = new Map();
  for (const value of pending) counts.set(value.stage, (counts.get(value.stage) || 0) + 1);
  return Object.fromEntries(stages.map(stage => [stage, {
    general: active[`${stage}/general/shared`] || null,
    project: active[`${stage}/project/${project}`] || null,
    candidates: counts.get(stage) || 0,
    projectCandidates: pending.length
  }]));
}

export function stageLearning(repoRoot, project, stage) {
  return stageLearningForStages(repoRoot, project, [stage])[stage];
}
