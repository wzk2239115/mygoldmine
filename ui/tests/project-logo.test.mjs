import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {projectLogo} from '../server/project-logo.mjs';

test('重新导入丢失图标配置时恢复本地图片，同时保留显式配置', t => {
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'goldmine-logo-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 fs.mkdirSync(path.join(root,'ui/public/logos'),{recursive:true});
 fs.writeFileSync(path.join(root,'ui/public/logos/verl.png'),'fixture');
 assert.equal(projectLogo(root,'verl'),'/logos/verl.png');
 assert.equal(projectLogo(root,'verl','/custom.svg'),'/custom.svg');
 assert.equal(projectLogo(root,'unknown'),'');
 assert.equal(projectLogo(root,'../verl'),'');
});

test('缺失图标在后台下载，本地缓存与并发请求复用',async t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'logo-download-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const {queueProjectLogo}=await import('../server/project-logo.mjs');
 let calls=0;const bytes=Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),Buffer.alloc(80)]);
 const fake=async url=>{calls++;assert.equal(url,'https://github.com/anomalyco.png?size=80');return new Response(bytes,{headers:{'content-type':'image/png'}});};
 const results=await Promise.all([queueProjectLogo(root,'opencode','https://github.com/anomalyco/opencode',fake),queueProjectLogo(root,'opencode','https://github.com/anomalyco/opencode',fake)]);
 assert.deepEqual(results,['/logos/opencode.png','/logos/opencode.png']);assert.equal(calls,1);
 assert.equal(projectLogo(root,'opencode'),'/logos/opencode.png');
 await queueProjectLogo(root,'opencode','https://github.com/anomalyco/opencode',fake);assert.equal(calls,1);
});
test('错误图片与非托管仓库地址不会保存为图标',async t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'logo-invalid-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const {queueProjectLogo}=await import('../server/project-logo.mjs');
 const fake=async()=>new Response('x'.repeat(100),{headers:{'content-type':'image/png'}});
 assert.equal(await queueProjectLogo(root,'demo','https://github.com/owner/repo',fake),'');
 assert.equal(projectLogo(root,'demo'),'');
 assert.equal(await queueProjectLogo(root,'other','https://github.com.evil/owner/repo',()=>{throw Error('must not fetch');}),'');
});
