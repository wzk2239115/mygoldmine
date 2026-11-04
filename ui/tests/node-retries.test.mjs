import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {startNodeRetry,nodeAttempts,retryEligibility} from '../server/node-retries.mjs';
import {listAgenticTraces} from '../server/agentic-traces.mjs';

test('独立重跑隔离产物、拒绝并发并保留原始输入', async t => {
 const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'node-retry-'));
 t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
 const runDir=path.join(repoRoot,'runs/demo/one');fs.mkdirSync(runDir,{recursive:true});
 const report=JSON.stringify({findings:[]});fs.writeFileSync(path.join(runDir,'audit-report.json'),report);
 const dir=path.join(repoRoot,'scripts/mine');fs.mkdirSync(dir,{recursive:true});
 fs.writeFileSync(path.join(dir,'visual_report.sh'),'sleep 0.2\nexit 1\n');
 const run={runDir,project:'demo',runId:'one',isLive:false};
 assert.match(retryEligibility({...run,isLive:true},'visual'),/正在运行/);
 assert.match(retryEligibility(run,'judge'),/暂不支持/);
 assert.match(retryEligibility(run,'verify'),/镜像/);
 const started=startNodeRetry({repoRoot,run,node:'visual',models:{audit:'test'}});
 assert.throws(()=>startNodeRetry({repoRoot,run,node:'visual',models:{audit:'test'}}),/已有节点/);
 let latest;
 for(let i=0;i<100;i++) {latest=nodeAttempts(runDir,'visual')[0];if(latest.status!=='running')break;await new Promise(r=>setTimeout(r,50));}
 assert.equal(latest.id,started.id);assert.equal(latest.status,'failed');
 assert.equal(fs.readFileSync(path.join(runDir,'audit-report.json'),'utf8'),report);
 assert.ok(fs.existsSync(path.join(latest.workspace,'audit-report.json')));
 assert.equal(fs.existsSync(latest.lock),false);
 assert.ok(listAgenticTraces(run,'visual').some(trace=>trace.id===`${started.id}-worker`));
});
