import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
const database = process.env.DATABASE_PATH || path.join(os.homedir(), '.cloudcli/auth.db');
if (!fs.existsSync(database)) throw new Error('会话索引文件不存在，请恢复或启动会话服务');
process.env.DATABASE_PATH = database;
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const base = path.join(root, 'third_party/claudecodeui/dist-server/server');
const { closeConnection } = await import(pathToFileURL(path.join(base, 'modules/database/index.js')));
const { ClaudeSessionSynchronizer } = await import(pathToFileURL(path.join(base, 'modules/providers/list/claude/claude-session-synchronizer.provider.js')));
try {
  const id = await new ClaudeSessionSynchronizer().synchronizeFile(process.argv[2]);
  if (!id) throw new Error('未能登记轨迹会话');
  console.log(id);
} finally { closeConnection(); }
