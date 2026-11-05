import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {attachCandidateFlow} from '../server/candidate-flow.mjs';

test('每个阶段逐条保留总表候选，不把缺少记录算作完成',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'candidate-flow-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const run={runDir:root};
 const findings=Array.from({length:16},(_,i)=>({id:'F-'+i,severity:i<4?'high':'medium'}));
 fs.writeFileSync(path.join(root,'audit-report.json'),JSON.stringify({findings}));
 const nodes=[{id:'orchestrator'},{id:'visual',scenes:{tasks:findings.slice(0,4).map(row=>({...row,state:'completed'}))}},
 {id:'verify',verification:{tasks:findings.slice(0,4).map(row=>({...row,state:'completed',verdict:'confirmed'}))}},
 {id:'redteam-lab',construction:{tasks:[{id:'F-0',state:'completed'}]}},{id:'redteam-agent',execution:{tasks:[]}},{id:'judge',review:{tasks:[]}}];
 attachCandidateFlow(run,nodes);
 for(const node of nodes){assert.equal(node.flow.total,16);assert.equal(node.flow.rows.length,16);assert.equal(node.flow.recorded+node.flow.pending,16);}
 assert.equal(nodes[1].flow.recorded,4);assert.equal(nodes[1].flow.pending,12);
 assert.match(nodes[3].flow.rows.find(row=>row.id==='F-1').reason,/仍待处理/);
 assert.match(nodes[3].flow.rows.find(row=>row.id==='F-5').reason,/等待前置验证/);
});

test('过期输入与当前报告之外的执行记录被明确标记',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'candidate-stale-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 fs.mkdirSync(path.join(root,'verify/agent'),{recursive:true});
 fs.writeFileSync(path.join(root,'audit-report.json'),JSON.stringify({findings:[{id:'F-1'}]}));
 fs.writeFileSync(path.join(root,'verify/agent/selection.json'),JSON.stringify({report_sha256:'old'}));
 const nodes=[{id:'verify',verification:{tasks:[{id:'F-1',state:'completed'},{id:'foreign',state:'completed'}]}}];
 attachCandidateFlow({runDir:root},nodes);
 assert.equal(nodes[0].flow.stale,true);assert.equal(nodes[0].flow.rows[0].state,'stale');
 assert.deepEqual(nodes[0].flow.orphans,['foreign']);
});
