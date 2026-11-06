import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {visualAsset,visualRoot} from '../server/visual-assets.mjs';
import {artifactLink} from '../src/artifact-links.mjs';

test('视觉接口选择最近完成批次，不混用旧图，不受未完成批次影响',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'visual-assets-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const run={runDir:path.join(root,'one')};fs.mkdirSync(path.join(run.runDir,'visual-rendered'),{recursive:true});
 fs.writeFileSync(path.join(run.runDir,'visual-rendered','old.webp'),'old');
 for(const [id,status] of [['a','completed'],['b','running']]){
  const folder=path.join(run.runDir+'.meta','node-retries','visual',id),workspace=path.join(folder,'output');
  fs.mkdirSync(path.join(workspace,'visual-rendered'),{recursive:true});
  fs.writeFileSync(path.join(folder,'attempt.json'),JSON.stringify({startedAt:id,status,resultStatus:'completed',workspace}));
  fs.writeFileSync(path.join(workspace,'visual-rendered','scene.webp'),id);
 }
 assert.ok(visualRoot(run).includes('/a/output'));
 assert.equal(fs.readFileSync(visualAsset(run,'scene.webp').file,'utf8'),'a');
 assert.equal(visualAsset(run,'old.webp'),null);
 assert.equal(visualAsset(run,'../../secret.json'),null);
});
test('报告链接绑定原产物地址并拦截脚本及外部图片',()=>{
 const base='/api/runs/demo/one/nodes/visual/artifacts/abc';
 assert.equal(artifactLink('scene.webp',base,true),base+'/asset?path=scene.webp');
 assert.equal(artifactLink('https://example.com/pixel',base,true),'');
 assert.equal(artifactLink('javascript:alert(1)',base),'');
 assert.equal(artifactLink('//example.com',base),'');
 assert.equal(artifactLink('#result',base),'#result');
 assert.equal(artifactLink('https://example.com/report',base),'https://example.com/report');
});
