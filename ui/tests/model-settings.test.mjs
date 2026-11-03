import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createModelSettings} from '../server/model-settings.mjs';
function fixture(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'goldmine-models-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;}

test('模型配置保存后可重新读取，留空阶段跟随审计，候选不泄漏密钥',t=>{
 const repoRoot=fixture(t);const providerFile=path.join(repoRoot,'providers.json');
 fs.writeFileSync(providerFile,JSON.stringify({provider:{proxy:{options:{apiKey:'secret'},models:{'test-model':{}}}}}));
 const settings=createModelSettings({repoRoot,env:{},providerFile});
 assert.deepEqual(settings.args(),[]);
 settings.save({audit:'provider/audit',environment:'',visual:'provider/scenes',verify:'provider/blue',redteam:'local/red',judge:''});
 const restored=createModelSettings({repoRoot,env:{},providerFile});
 assert.deepEqual(restored.args(),['--model','provider/audit','--env-model','provider/audit','--visual-model','provider/scenes','--verify-model','provider/blue','--redteam-model','local/red','--judge-model','provider/audit']);
 assert.ok(restored.get().choices.includes('proxy/test-model'));
 assert.ok(!JSON.stringify(restored.get()).includes('secret'));
});

test('拒绝无效模型且保留已保存值',t=>{
 const settings=createModelSettings({repoRoot:fixture(t),env:{}});const models=settings.get().models;
 settings.save(models);
 for(const value of ['', 'model;rm', 'model\nother', 'a'.repeat(201)]) assert.throws(()=>settings.save({...models,audit:value}));
 assert.throws(()=>settings.save({audit:'demo'}));
 assert.deepEqual(settings.get().models,models);
});
