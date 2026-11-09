
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {partialLabDelivery} from '../server/partial-lab-delivery.mjs';
import {labTasks} from '../server/lab-tasks.mjs';

test('13 个成员中 10 个有效交付继续，缺少交付的 3 个成员在界面标记',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'partial-lab-'));
 t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const runDir=path.join(base,'runs/demo/one');
 const attempt=runDir+'.meta/node-retries/redteam-lab/attempt';
 const workspace=path.join(attempt,'output');
 const root=path.join(workspace,'redteam');
 const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
 const results=Array.from({length:13},(_,i)=>{
  const id='F-'+i,folder=path.join(root,'labs',id);
  const status=i<3 || i>=11?'blocked':'built';
  const file=path.join(folder,status==='built'?'scenario.json':'blocked.json');
  write(file,{finding_id:id,status:status==='built'?'ready':'blocked'});
  if(i>=3)write(path.join(folder,'.stage-submissions/redteam-lab/receipt.json'),{
   stage:'redteam-lab',decision:'accepted',checked_at:'2026-11-09',
   artifact:file,sha256:createHash('sha256').update(fs.readFileSync(file)).digest('hex')
  });
  return {id,status,scenario:status==='built'?file:'',error:status==='blocked'?'构建超时':''};
 });
 write(path.join(root,'summary.json'),{selected:13,processed:13,results});
 write(path.join(root,'selection.json'),{candidates:results.map(row=>({id:row.id}))});
 write(path.join(attempt,'attempt.json'),{id:'attempt',workspace,status:'completed',startedAt:'2026-11-09'});
 write(path.join(workspace,'audit-report.json'),{findings:[]});
 const result=partialLabDelivery(workspace);
 assert.equal(result.accepted,10);
 assert.equal(result.excluded.length,3);
 const summary=JSON.parse(fs.readFileSync(path.join(root,'summary.json')));
 assert.equal(summary.ready,8);
 assert.equal(summary.status,'degraded');
 const tasks=labTasks({runDir,project:'demo',runId:'one',isLive:false});
 assert.equal(tasks.deliveryMissing,3);
 assert.equal(tasks.tasks.filter(row=>row.label==='缺少交付').length,3);
 assert.equal(tasks.ready,8);
 // No receipts are invented for failed members.
 assert.equal(fs.existsSync(path.join(root,'labs/F-0/.stage-submissions')),false);
});
