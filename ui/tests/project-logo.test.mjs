import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {projectLogo} from '../server/project-logo.mjs';

test('重新导入丢失图标配置时恢复本地图片，同时保留显式配置', t => {
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'goldmine-logo-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 fs.mkdirSync(path.join(root,'ui/public/logos'),{recursive:true});
 fs.writeFileSync(path.join(root,'ui/public/logos/verl.png'),'fixture');
 assert.equal(projectLogo(root,'verl'),'/logos/verl.png');
 assert.equal(projectLogo(root,'verl','/custom.svg'),'/custom.svg');
 assert.equal(projectLogo(root,'unknown'),'');
 assert.equal(projectLogo(root,'../verl'),'');
});
