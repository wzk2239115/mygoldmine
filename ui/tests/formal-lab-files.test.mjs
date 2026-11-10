
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {formalLabFiles} from '../server/formal-lab-files.mjs';
import {manifest} from '../server/claude-workflows.mjs';
test('只冻结正式交付；未声明工作区链接不扫描，已声明越界链接仍拒绝',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'formal-lab-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const write=(name,value)=>{const file=path.join(root,name);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value));return file;};
 write('redteam/summary.json',{results:[]});
 const artifact=write('redteam/labs/F-1/scenario.json',{driver:'driver.py'});
 const driver=write('redteam/labs/F-1/driver.py',{});
 const receipt=write('redteam/labs/F-1/.stage-submissions/redteam-lab/r.json',{});
 const diagnostic=path.join(root,'redteam/labs/F-1/diagnostics/node_modules');
 fs.mkdirSync(path.dirname(diagnostic),{recursive:true});fs.symlinkSync('/opt/target/api/node_modules',diagnostic);
 const delivery={deliveries:[{artifact,receipt,files:[{path:artifact}]}]};
 const files=formalLabFiles(root,delivery);
 assert.ok(files.includes(driver));assert.ok(!files.includes(diagnostic));
 assert.equal(manifest(files).length,4);
 delivery.deliveries[0].files.push({path:diagnostic});
 assert.throws(()=>formalLabFiles(root,delivery),/符号链接/);
 delivery.deliveries[0].files.pop();fs.unlinkSync(driver);
 assert.throws(()=>formalLabFiles(root,delivery));
});
