import path from 'node:path';

export function sessionMatchesTrace(session, tracePath, stat) {
  if (session.sourceMtimeNs != null) {
    return session.sourceFile === path.resolve(tracePath)
      && session.sourceSize === Number(stat.size)
      && session.sourceMtimeNs === String(stat.mtimeNs);
  }
  // 兼容旧缓存；新转换结果按源文件版本判断，不依赖两台机器的时钟。
  return (Date.parse(session.importedAt || '') || 0) >= Number(stat.mtimeNs) / 1e6 - 50;
}
