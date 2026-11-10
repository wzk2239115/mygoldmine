
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {acceptedStageDelivery,optionalVisualDelivery} from '../server/delivery-contract.mjs';

test('没有绘图任务时允许零份图片交付',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'optional-visual-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 assert.equal(optionalVisualDelivery(root,0).accepted,0);
});
test('有设计任务却没有有效设计回执时失败，不放宽验证阶段验收',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'optional-visual-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 assert.throws(()=>optionalVisualDelivery(root,2),/回执/);
 assert.throws(()=>acceptedStageDelivery('verify',root,1),/回执/);
});
