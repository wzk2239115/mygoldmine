import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import test from 'node:test';
import {snapshotOperationLog} from '../server/operation-log-snapshot.mjs';
test('旧日志迁移只接受原长度及摘要，追加内容不污染快照',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'log-snapshot-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const file=path.join(root,'.workspace/logs/operations.jsonl');fs.mkdirSync(path.dirname(file),{recursive:true});
 const bytes=Buffer.from('original\n'),sha256=createHash('sha256').update(bytes).digest('hex');fs.writeFileSync(file,bytes);fs.appendFileSync(file,'new content\n');
 const item=snapshotOperationLog(file,root,{size:bytes.length,sha256});assert.equal(fs.readFileSync(item.file,'utf8'),'original\n');
 fs.writeFileSync(file,'tampered\nnew content\n');assert.throws(()=>snapshotOperationLog(file,root,{size:bytes.length,sha256}),/不匹配/);
 assert.throws(()=>snapshotOperationLog(path.join(root,'evidence.log'),root),/不支持|不是/);
});
