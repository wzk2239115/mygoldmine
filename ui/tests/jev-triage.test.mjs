import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {jevTriage} from '../server/jev-triage.mjs';
const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
test('Jev 报告只暴露摘要与排序结果，不将失败单元算作成功处理',t=>{
 const runDir=fs.mkdtempSync(path.join(os.tmpdir(),'jev-ui-'));t.after(()=>fs.rmSync(runDir,{recursive:true,force:true}));
 assert.equal(jevTriage({runDir}),null);
 write(path.join(runDir,'triage/jev-infra.json'),{stats:{units:3,requests:2},units:[{id:'low',priority:.1,answers:{private:'not for UI'}},{id:'high',priority:.9}],errors:[{unit:'bad',error:'private error'}]});
 const info=jevTriage({runDir});assert.equal(info.status,'partial');assert.equal(info.processedUnits,2);assert.equal(info.failedUnits,1);assert.equal(info.units[0].id,'high');assert.equal(info.units[0].answers,undefined);assert.equal(info.errors,undefined);
});
test('旧任务没有细分进度时明确说明，中断不冒充完成',t=>{
 const runDir=fs.mkdtempSync(path.join(os.tmpdir(),'jev-progress-'));t.after(()=>fs.rmSync(runDir,{recursive:true,force:true}));
 fs.mkdirSync(path.join(runDir,'triage'));fs.writeFileSync(path.join(runDir,'triage/jev.log'),'');
 assert.match(jevTriage({runDir,isLive:true}).notice,/尚无细分进度/);
 write(path.join(runDir,'triage/jev-infra.progress.json'),{status:'running',stats:{units:10},processed_units:3,units:[]});
 assert.equal(jevTriage({runDir,isLive:true}).status,'running');
 assert.equal(jevTriage({runDir,isLive:false}).status,'incomplete');
});
