import test from 'node:test';import assert from 'node:assert/strict';
import fs from 'node:fs';import path from 'node:path';import os from 'node:os';import {spawnSync} from 'node:child_process';
import {zipFiles,markdownBundle} from '../server/report-export.mjs';
function unzip(bytes){
 const r=spawnSync('python3',['-c','import zipfile,io,json,sys,base64; z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())); assert z.testzip() is None; print(json.dumps({n:base64.b64encode(z.read(n)).decode() for n in z.namelist()}))'],{input:bytes,maxBuffer:4*1024*1024});
 assert.equal(r.status,0,r.stderr.toString());return Object.fromEntries(Object.entries(JSON.parse(r.stdout)).map(([name,data])=>[name,Buffer.from(data,'base64')]));
}
function fixture(t,md){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'report-package-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const file=path.join(root,'model-report.md');fs.writeFileSync(file,md);return {root,file,name:'model-report.md'};
}
test('ZIP 可解压且校验通过，支持中文文件名',()=>{
 const files=unzip(zipFiles(new Map([['报告.md','正文'],['assets/image.webp',Buffer.from([1,2,3])]])));
 assert.equal(files['报告.md'].toString(),'正文');assert.equal(files['assets/image.webp'].length,3);
});
test('任意模型 Markdown 的图片、引用链接和嵌套章节自动收集，原文不变',t=>{
 const md='# 模型任意标题\n![原理](figures/mechanism.webp)\n[证据][proof]\n\n[proof]: evidence/check.json\n\n[章节](detail.md)\n[外部文档](https://example.com/doc)';
 const item=fixture(t,md);fs.mkdirSync(path.join(item.root,'figures'));fs.mkdirSync(path.join(item.root,'evidence'));
 fs.writeFileSync(path.join(item.root,'figures/mechanism.webp'),'model-image');
 fs.writeFileSync(path.join(item.root,'evidence/check.json'),'{"ok":true}');
 fs.writeFileSync(path.join(item.root,'detail.md'),'![同一图](figures/mechanism.webp)');
 const files=unzip(markdownBundle(item).bytes),report=files['report.md'].toString();
 assert.match(report,/attachments\/figures\/mechanism.webp/);assert.match(report,/attachments\/evidence\/check.json/);
 assert.equal(files['attachments/detail.md'].toString(),'![同一图](figures/mechanism.webp)');
 assert.match(report,/https:\/\/example.com\/doc/);assert.equal(fs.readFileSync(item.file,'utf8'),md);
 assert.ok(files['manifest.json']);assert.equal(Object.keys(files).filter(x=>x.endsWith('mechanism.webp')).length,1);
});
test('缺失附件、越界路径和符号链接明确拒绝',t=>{
 const item=fixture(t,'![图](missing.webp)');assert.throws(()=>markdownBundle(item),/附件不可用/);
 fs.writeFileSync(item.file,'[越界](../outside.txt)');assert.throws(()=>markdownBundle(item),/超出/);
 fs.symlinkSync('/etc/passwd',path.join(item.root,'linked.txt'));fs.writeFileSync(item.file,'[链接](linked.txt)');assert.throws(()=>markdownBundle(item),/超出/);
});
test('归档目录拒绝路径穿越',()=>{assert.throws(()=>zipFiles(new Map([['../escape','bad']])),/无效/);});
