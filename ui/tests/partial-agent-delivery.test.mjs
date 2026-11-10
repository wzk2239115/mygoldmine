
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {partialAgentDelivery} from '../server/partial-agent-delivery.mjs';
test('第六阶段允许部分或全部成员缺交付，并保留每个成员状态',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'partial-agent-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
 const folder=path.join(root,'redteam/agent-runs/good'),file=path.join(folder,'stage-result.json');
 write(file,{status:'not_captured',captured:false});
 write(path.join(folder,'.stage-submissions/redteam-agent/r.json'),{
  stage:'redteam-agent',decision:'accepted',artifact:file,
  sha256:createHash('sha256').update(fs.readFileSync(file)).digest('hex')});
 const summary=path.join(root,'redteam/summary.json');
 write(summary,{results:[{id:'good',status:'not_captured',captured:false,run_dir:folder},
 {id:'bad',status:'agent_timeout',captured:false,run_dir:path.join(root,'redteam/agent-runs/bad')}]});
 let result=partialAgentDelivery(root);
 assert.equal(result.accepted,1);assert.equal(result.excluded.length,1);
 assert.equal(JSON.parse(fs.readFileSync(summary)).status,'degraded');
 fs.rmSync(folder,{recursive:true});
 result=partialAgentDelivery(root);
 assert.equal(result.accepted,0);assert.equal(result.excluded.length,2);
 assert.equal(JSON.parse(fs.readFileSync(summary)).captured,0);
});
