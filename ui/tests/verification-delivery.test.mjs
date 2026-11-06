
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {verificationReports} from '../server/verification-delivery.mjs';
import {manifest} from '../server/claude-workflows.mjs';

function fixture(t) {
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'verification-contract-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const dir=path.join(root,'F-1');fs.mkdirSync(dir);
 fs.writeFileSync(path.join(dir,'check.sh'),'echo checked');
 fs.writeFileSync(path.join(dir,'verify-report.json'),JSON.stringify({project:'demo',finding_id:'F-1',verdict:'rejected',evidence:[],harness:'check.sh'}));
 fs.writeFileSync(path.join(root,'summary.json'),JSON.stringify({project:'demo',findings:[{finding_id:'F-1'}]}));
 return {root,dir};
}
test('只按正式清单选择报告，诊断和历史副本仍归档但不误作正式结果验收',t=>{
 const {root}=fixture(t);
 for(const folder of ['F-1.diagnostics','other-name','retry-history/F-1/1']) {
  const dir=path.join(root,folder);fs.mkdirSync(dir,{recursive:true});
  fs.writeFileSync(path.join(dir,'verify-report.json'),JSON.stringify({harness:'/tmp/absent/check.sh',verdict:'rejected'}));
 }
 const rows=manifest([root],{verification:true});
 assert.equal(verificationReports(root).length,1);
 assert.equal(rows.filter(x=>path.basename(x.file)==='verify-report.json').length,4);
});
test('正式报告缺少脚本不能被诊断副本或目录过滤掩盖',t=>{
 const {root,dir}=fixture(t);fs.unlinkSync(path.join(dir,'check.sh'));
 assert.throws(()=>manifest([root],{verification:true}),/附件缺失/);
});
test('正式候选缺报告、身份冲突、清单路径越界和重复编号均拒绝',t=>{
 const {root,dir}=fixture(t);
 fs.writeFileSync(path.join(root,'summary.json'),JSON.stringify({findings:[{finding_id:'missing'}]}));
 assert.throws(()=>verificationReports(root),/缺失/);
 fs.writeFileSync(path.join(root,'summary.json'),JSON.stringify({findings:[{finding_id:'F-1',report_path:'/tmp/other.json'}]}));
 assert.throws(()=>verificationReports(root),/路径/);
 fs.writeFileSync(path.join(root,'summary.json'),JSON.stringify({findings:[{finding_id:'F-1'},{finding_id:'F-1'}]}));
 assert.throws(()=>verificationReports(root),/重复/);
 fs.writeFileSync(path.join(root,'summary.json'),JSON.stringify({project:'other',findings:[{finding_id:'F-1'}]}));
 assert.throws(()=>verificationReports(root),/编号不一致/);
 fs.unlinkSync(path.join(root,'summary.json'));
 assert.throws(()=>manifest([root],{verification:true}),/批次清单/);
});
