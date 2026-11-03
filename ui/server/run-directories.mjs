import fs from 'node:fs';
import path from 'node:path';

// Startup status can exist before the main output directory is created.
export function discoverRunNames(projectDir) {
  const names = new Set();
  for (const entry of fs.readdirSync(projectDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith('.')) continue;
    if (entry.name.endsWith('.meta')) {
      const name = entry.name.slice(0, -5);
      if (name && fs.existsSync(path.join(projectDir, entry.name, 'status.json'))) names.add(name);
    } else names.add(entry.name);
  }
  return [...names];
}
