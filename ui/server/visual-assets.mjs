import fs from 'node:fs';
import path from 'node:path';
import {nodeAttempts} from './node-retries.mjs';
import {artifactAsset} from './node-artifacts.mjs';

export function visualRoot(run) {
 const latest=nodeAttempts(run.runDir,'visual').filter(item=>item.status==='completed' && item.resultStatus!=='failed').at(-1);
 return latest?.workspace || run.runDir;
}
export function visualAsset(run,requested) {
 const root=visualRoot(run);
 for(const folder of ['visual-rendered','visual']) {
  const base=path.join(root,folder);
  if(!fs.existsSync(base))continue;
  const item=artifactAsset({file:path.join(base,'report-illustrated.md'),root:fs.realpathSync(base)},requested);
  if(item)return item;
 }
 return null;
}
