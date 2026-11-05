import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {listNodeArtifacts,nodeArtifact,artifactText} from '../server/node-artifacts.mjs';

function fixture(t) {
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'node-artifacts-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const run={runDir:path.join(root,'runs/demo/one')};fs.mkdirSync(run.runDir,{recursive:true});
 return {root,run};
}
test('报告按阶段列出，按清单编号读取，拒绝任意路径',t=>{
 const {run}=fixture(t);
 fs.writeFileSync(path.join(run.runDir,'audit-report.md'),'# report');
 fs.writeFileSync(path.join(run.runDir,'private.json'),'secret');
 const items=listNodeArtifacts(run,'orchestrator');
 assert.equal(items.length,1);assert.equal(items[0].name,'audit-report.md');
 assert.equal(artifactText(nodeArtifact(run,'orchestrator',items[0].id)).text,'# report');
 assert.equal(nodeArtifact(run,'orchestrator','../../private.json'),null);
 assert.equal(listNodeArtifacts(run,'missing').length,0);
});
test('符号链接产物不能读取运行目录外文件',t=>{
 const {root,run}=fixture(t);fs.writeFileSync(path.join(root,'secret'),'secret');
 fs.symlinkSync(path.join(root,'secret'),path.join(run.runDir,'audit-report.json'));
 assert.equal(listNodeArtifacts(run,'orchestrator').length,0);
});
test('长文件限量预览，读取前替换为链接会被拒绝',t=>{
 const {root,run}=fixture(t);const file=path.join(run.runDir,'audit-report.md');
 fs.writeFileSync(file,'a'.repeat(600*1024));
 const item=listNodeArtifacts(run,'orchestrator')[0];
 assert.equal(artifactText(item).truncated,true);assert.equal(artifactText(item).text.length,512*1024);
 fs.writeFileSync(path.join(root,'secret'),'secret');fs.unlinkSync(file);fs.symlinkSync(path.join(root,'secret'),file);
 assert.throws(()=>artifactText(item));
});
