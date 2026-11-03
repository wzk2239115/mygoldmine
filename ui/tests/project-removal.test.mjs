import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {removeProjectRecords} from '../server/project-removal.mjs';

test('删除项目登记、运行和候选问题，保留源码与其他项目', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'project-removal-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const write=(file,payload)=>{const p=path.join(root,file);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(payload));};
  write('ui/data/projects.json',{projects:{verl:{name:'verl'},other:{name:'other'}}});
  write('targets/manifest.json',{projects:{verl:{status:'ok'},other:{status:'ok'}}});
  write('ui/data/finding-ledger.json',{schema_version:2,findings:{s1:{project:'verl'},s2:{project:'other'}},occurrences:{o1:{project:'verl'},o2:{project:'other'}},indexes:{legacy_to_semantics:{'verl:F1':['s1'],'other:F1':['s2']}},latest_by_project:{verl:{run_id:'run'},other:{run_id:'run'}}});
  write('ui/data/state.json',{'verl:F1':{notes:'removed'},s1:{notes:'removed'},'other:F1':{notes:'preserved'}});
  write('runs/verl/run.meta/status.json',{state:'failed'});
  write('runs/other/run/audit-report.json',{findings:[]});
  write('targets/verl/source.json',{preserved:true});
  removeProjectRecords(root,'verl');
  assert.equal(fs.existsSync(path.join(root,'runs/verl')),false);
  assert.ok(fs.existsSync(path.join(root,'targets/verl/source.json')));
  assert.ok(fs.existsSync(path.join(root,'runs/other/run/audit-report.json')));
  const read=file=>JSON.parse(fs.readFileSync(path.join(root,file),'utf8'));
  assert.equal(read('ui/data/projects.json').projects.verl,undefined);
  assert.equal(read('targets/manifest.json').projects.verl,undefined);
  const ledger=read('ui/data/finding-ledger.json');
  assert.equal(ledger.findings.s1,undefined);assert.ok(ledger.findings.s2);
  assert.equal(ledger.latest_by_project.verl,undefined);
  assert.deepEqual(read('ui/data/state.json'),{'other:F1':{notes:'preserved'}});
});

test('删除拒绝路径穿越标识',()=>{
  assert.throws(()=>removeProjectRecords('/tmp','../source'),/标识无效/);
});
