import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {discoverRunNames} from '../server/run-directories.mjs';

test('只有状态目录的启动运行可被发现，主目录出现后不会重复', async () => {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'run-discovery-'));
  try {
    const id='20261103T084444Z';
    await fs.mkdir(path.join(root,`${id}.meta`));
    await fs.writeFile(path.join(root,`${id}.meta`,'status.json'),'{"state":"running"}');
    await fs.mkdir(path.join(root,'orphan.meta'));
    await fs.mkdir(path.join(root,'.hidden'));
    assert.deepEqual(discoverRunNames(root),[id]);
    await fs.mkdir(path.join(root,id));
    assert.deepEqual(discoverRunNames(root),[id]);
  } finally { await fs.rm(root,{recursive:true,force:true}); }
});
