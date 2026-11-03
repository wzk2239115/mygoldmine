import fs from 'node:fs';
import path from 'node:path';

export function projectLogo(repoRoot, project, configured = '') {
  if (configured) return configured;
  if (!/^[a-z0-9][a-z0-9._-]{0,79}$/.test(project) || project === '.' || project === '..') return '';
  return fs.existsSync(path.join(repoRoot, 'ui/public/logos', `${project}.png`)) ? `/logos/${project}.png` : '';
}
