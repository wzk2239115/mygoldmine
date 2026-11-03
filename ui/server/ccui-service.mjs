import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';

export function createCcuiService({repoRoot, home, url, health, launch, wait = ms => new Promise(resolve => setTimeout(resolve, ms)), attempts = 40}) {
  let starting;
  const target = new URL(url);
  const local = target.protocol === 'http:' && target.hostname === '127.0.0.1';
  const start = launch || (() => {
    fs.mkdirSync(home, {recursive:true});
    const fd = fs.openSync(path.join(home,'service.log'),'a');
    try {
      const child = spawn('bash',[path.join(repoRoot,'scripts/ccui/start.sh'),'--no-import','--host','127.0.0.1','--port',target.port || '80','--home',home],{cwd:repoRoot,detached:true,stdio:['ignore',fd,fd]});
      child.on('error',error => console.error('轨迹查看服务启动失败：',error.message));
      child.unref();
    } finally {fs.closeSync(fd);}
  });
  return {ensure() {
    if (starting) return starting;
    starting = (async () => {
      if (await health(true)) return true;
      if (!local) return false;
      await start();
      for (let i=0;i<attempts;i++) {
        await wait(250);
        if (await health(true)) return true;
      }
      return false;
    })().finally(()=>{starting=null;});
    return starting;
  }};
}
