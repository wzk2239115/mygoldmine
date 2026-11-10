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
 assert.match(retryEligibility(run,'unknown'),/暂不支持/);
 assert.match(retryEligibility(run,'judge'),/没有已捕获/);
 assert.match(retryEligibility(run,'verify'),/镜像/);
 const started=startNodeRetry({repoRoot,run,node:'visual',models:{audit:'test'}});
 assert.throws(()=>startNodeRetry({repoRoot,run,node:'visual',models:{audit:'test'}}),/已有节点/);
 let latest;
 for(let i=0;i<100;i++) {latest=nodeAttempts(runDir,'visual')[0];if(latest.status!=='running')break;await new Promise(r=>setTimeout(r,50));}
 assert.equal(latest.id,started.id);assert.equal(latest.status,'completed');
 assert.equal(latest.resultStatus,'degraded');assert.equal(latest.visualExitCode,1);
 assert.ok(fs.existsSync(path.join(latest.workspace,'visual-rendered/delivery-status.json')));
 assert.equal(fs.readFileSync(path.join(runDir,'audit-report.json'),'utf8'),report);
 assert.ok(fs.existsSync(path.join(latest.workspace,'audit-report.json')));
 assert.equal(fs.existsSync(latest.lock),false);
 assert.ok(listAgenticTraces(run,'visual').some(trace=>trace.id===`${started.id}-worker`));
});

test('蓝队重跑进程正常退出但候选全部受阻时保留受阻状态', async t => {
 const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'node-retry-blocked-'));
 t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
 const runDir=path.join(repoRoot,'runs/demo/one');fs.mkdirSync(`${runDir}.meta`,{recursive:true});
 fs.mkdirSync(runDir,{recursive:true});
 fs.writeFileSync(path.join(runDir,'audit-report.json'),JSON.stringify({findings:[]}));
 fs.writeFileSync(`${runDir}.meta/status.json`,JSON.stringify({target:'/tmp/source',env_image:'fixture:test'}));
 const dir=path.join(repoRoot,'scripts/verify');fs.mkdirSync(dir,{recursive:true});
 fs.writeFileSync(path.join(dir,'phase4_verify_agent.sh'),`while [ "$#" -gt 0 ]; do if [ "$1" = --output ]; then out="$2"; fi; shift; done
mkdir -p "$out"
printf '%s' '{"status":"blocked","counts":{"blocked":4}}' > "$out/summary.json"
exit 0
`);
 startNodeRetry({repoRoot,run:{runDir,project:'demo',runId:'one',isLive:false},node:'verify',models:{audit:'test'}});
 let latest;
 for(let i=0;i<100;i++) {latest=nodeAttempts(runDir,'verify')[0];if(latest.status!=='running')break;await new Promise(r=>setTimeout(r,50));}
 assert.equal(latest.status,'completed');
 assert.equal(latest.resultStatus,'blocked');
});

test('第二阶段补正入口检查原报告与环境，并展示修复会话', t => {
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),'orchestrator-retry-'));
 t.after(()=>fs.rmSync(repo,{recursive:true,force:true}));
 const runDir=path.join(repo,'runs/demo/one');
 fs.mkdirSync(runDir,{recursive:true});
 fs.mkdirSync(runDir+'.meta',{recursive:true});
 fs.writeFileSync(path.join(runDir,'audit-report.json'),JSON.stringify({findings:[]}));
 const run={runDir,project:'demo',runId:'one',isLive:false};
 assert.match(retryEligibility(run,'orchestrator'),/环境信息/);
 fs.writeFileSync(runDir+'.meta/status.json',JSON.stringify({target:'/source',env_image:'test:image'}));
 assert.equal(retryEligibility(run,'orchestrator'),'');
 const root=path.join(runDir+'.meta/node-retries/orchestrator/id');
 fs.mkdirSync(root,{recursive:true});
 fs.writeFileSync(path.join(root,'attempt.json'),JSON.stringify({id:'id',root,workspace:path.join(root,'output'),status:'running',startedAt:new Date().toISOString()}));
 fs.writeFileSync(path.join(root,'repair-agent.jsonl'),'{}\n');
 const traces=listAgenticTraces(run,'orchestrator');
 assert.ok(traces.some(trace=>trace.id==='id-repair'));
});
