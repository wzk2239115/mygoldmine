import {unified} from 'unified';
import remarkParse from 'remark-parse';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {nodeArtifact,openArtifact} from './node-artifacts.mjs';
import {runtimeEnvironment,verificationAttachments} from './delivery-contract.mjs';

const fail=message=>{throw Object.assign(new Error(message),{status:409});};
const sum=bytes=>createHash('sha256').update(bytes).digest('hex');
const crcTable=Array.from({length:256},(_,i)=>{for(let j=0;j<8;j++)i=i&1?0xedb88320^(i>>>1):i>>>1;return i>>>0;});
function crc32(bytes){let crc=0xffffffff;for(const byte of bytes)crc=crcTable[(crc^byte)&255]^(crc>>>8);return (crc^0xffffffff)>>>0;}
export function zipFiles(entries) {
 const local=[],central=[];let offset=0;
 for(const [name,value] of entries){
  if(name.startsWith('/') || name.split('/').includes('..') || name.includes('\\'))fail('附件归档路径无效');
  const filename=Buffer.from(name),bytes=Buffer.isBuffer(value)?value:Buffer.from(value),crc=crc32(bytes);
  const header=Buffer.alloc(30);header.writeUInt32LE(0x04034b50);header.writeUInt16LE(20,4);header.writeUInt16LE(0x800,6);header.writeUInt16LE(33,12);header.writeUInt32LE(crc,14);header.writeUInt32LE(bytes.length,18);header.writeUInt32LE(bytes.length,22);header.writeUInt16LE(filename.length,26);
  local.push(header,filename,bytes);
  const c=Buffer.alloc(46);c.writeUInt32LE(0x02014b50);c.writeUInt16LE(20,4);c.writeUInt16LE(20,6);c.writeUInt16LE(0x800,8);c.writeUInt16LE(33,14);c.writeUInt32LE(crc,16);c.writeUInt32LE(bytes.length,20);c.writeUInt32LE(bytes.length,24);c.writeUInt16LE(filename.length,28);c.writeUInt32LE(offset,42);
  central.push(c,filename);offset+=header.length+filename.length+bytes.length;
 }
 const directory=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50);end.writeUInt16LE(entries.size,8);end.writeUInt16LE(entries.size,10);end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);
 return Buffer.concat([...local,directory,end]);
}
export function reportBundle(repo,finding,report) {
 const entries=new Map(),inventory=[];let total=0;
 const runs=fs.realpathSync(path.join(repo,'runs'));
 function addFile(file,name,root,required=true){
  try{
   const stat=fs.lstatSync(file),actual=fs.realpathSync(file);
   if(stat.isSymbolicLink() || !stat.isFile() || !actual.startsWith(root+path.sep) || !actual.startsWith(runs+path.sep))fail('附件路径超出本次报告范围');
   if(stat.size>10*1024*1024 || total+stat.size>32*1024*1024)fail('附件过大，无法生成报告包');
   const fd=openArtifact({file:actual,root});let bytes;try{bytes=fs.readFileSync(fd);}finally{fs.closeSync(fd);}
   if(entries.size>=1000)fail('报告附件数量超过上限');
   total+=bytes.length;entries.set(name,bytes);inventory.push({path:name,source:path.relative(repo,actual),size:bytes.length,sha256:sum(bytes)});
  }catch(error){if(required || error.status)throw Object.assign(new Error('报告附件不可用：'+name+'；'+error.message),{status:409});}
 }
 const run={runDir:finding.runDir,project:finding.project,runId:finding.runId};
 const imageId=report.imageUrl.match(/artifacts\/([a-f0-9]{24})/)?.[1];
 const image=nodeArtifact(run,'visual',imageId);if(!image)fail('报告插图已改变，请刷新后重试');
 const imageName='assets/'+path.basename(image.name);addFile(image.file,imageName,image.root);
 addFile(image.file+'.generation.json',imageName+'.generation.json',image.root,false);
 let markdown=report.markdown.replaceAll(report.imageUrl,imageName);
 const sets=[
  ['blue',finding.stageResults.blue,'verify-report.json'],
  ['red',finding.stageResults.red,'result.json'],
  ['judge',finding.stageResults.judge,'result.json']
 ];
 for(const [stage,result,filename] of sets){
  const main=path.resolve(repo,result.artifact || ''),root=path.dirname(main);
  const expected=path.resolve(finding.runDir+'.meta/node-retries');
  if(!root.startsWith(expected+path.sep))fail('报告证据不属于本次运行');
  addFile(main,'evidence/'+stage+'/'+filename,root);
  markdown=markdown.replaceAll('- `'+result.artifact+'`','- ['+stage+' 验证结果](evidence/'+stage+'/'+filename+')');
  const names=stage==='blue'?['finding.json','verdict.json','result.json','verify-report.md','harness.stdout.log','harness.stderr.log']:stage==='red'?['finding.json','scenario.json','trace.jsonl']:['judge.json'];
  for(const name of names)addFile(path.join(root,name),'evidence/'+stage+'/'+name,root,stage==='red');
  // Only this candidate's generated verification evidence and harness are included.
  if(stage==='blue'){
   verificationAttachments(main,root);
   function visit(folder,prefix,depth=0){
    if(depth>8)fail('验证附件目录过深');
    if(!fs.existsSync(folder))return;
    const runtime=runtimeEnvironment(folder);
    if(runtime){
     addFile(path.join(folder,'pyvenv.cfg'),prefix+'/pyvenv.cfg',root);
     const bytes=Buffer.from(JSON.stringify(runtime,null,2)),name=prefix+'/runtime-environment.json';
     if(entries.size>=1000 || total+bytes.length>32*1024*1024)fail('报告运行环境快照过大');
     total+=bytes.length;entries.set(name,bytes);inventory.push({path:name,role:'runtime_only',size:bytes.length,sha256:sum(bytes)});
     return;
    }
    for(const entry of fs.readdirSync(folder)){
     const file=path.join(folder,entry),stat=fs.lstatSync(file);
     if(stat.isSymbolicLink())fail('验证附件不允许符号链接');
     if(stat.isDirectory())visit(file,prefix+'/'+entry,depth+1);
     else addFile(file,prefix+'/'+entry,root);
    }
   }
   visit(path.join(root,'evidence'),'evidence/blue/evidence');visit(path.join(root,'harness'),'evidence/blue/harness');
  }
 }
 entries.set('report.md',Buffer.from(markdown));
 entries.set('README.txt',Buffer.from('解压后打开 report.md 阅读，图片与证据均使用包内相对路径。\nassets：文生图插图及可用的生成记录。\nevidence/blue：动态验证结果、运行输出、验证程序及已落盘证据。\nevidence/red：红队结果、场景、候选和工具执行轨迹。\nevidence/judge：独立审核结果。\nmanifest.json：来源、大小与 SHA-256。源码未包含，请按报告提交版本获取。\n'));
 const manifest={project:finding.project,runId:finding.runId,findingId:finding.id,commit:finding.commit,files:inventory};
 for(const name of ['report.md','README.txt']){const bytes=entries.get(name);manifest.files.push({path:name,size:bytes.length,sha256:sum(bytes)});}
 entries.set('manifest.json',Buffer.from(JSON.stringify(manifest,null,2)));
 return {filename:finding.project+'-'+finding.id+'-'+finding.runId+'.zip',bytes:zipFiles(entries),manifest};
}

const markdownParser=unified().use(remarkParse);
// Parse Markdown instead of relying on a particular model's filename or prose.
// Definitions cover reference-style links and images as well as inline links.
export function rewriteMarkdownAttachments(markdown,resolve) {
 const changes=[],imageDefinitions=new Set(),tree=markdownParser.parse(markdown);
 function scan(node){if(node.type==='imageReference')imageDefinitions.add(node.identifier);for(const child of node.children || [])scan(child);}
 scan(tree);
 function visit(node){
  if(['image','link','definition'].includes(node.type) && node.url){
   const replacement=resolve(node.url,node.type==='image' || node.type==='definition' && imageDefinitions.has(node.identifier));
   if(replacement && replacement!==node.url){
    const start=node.position.start.offset,end=node.position.end.offset;
    const source=markdown.slice(start,end);
    if(!source.includes(node.url))fail('附件引用包含不支持的转义，请检查报告：'+node.url);
    const at=start+source.lastIndexOf(node.url);
    changes.push({start:at,end:at+node.url.length,text:replacement});
   }
  }
  for(const child of node.children || [])visit(child);
 }
 visit(tree);
 // Link nodes may contain formatted text, but nested links are invalid Markdown.
 for(const change of changes.sort((a,b)=>b.start-a.start))markdown=markdown.slice(0,change.start)+change.text+markdown.slice(change.end);
 return markdown;
}
export function markdownBundle(item) {
 const entries=new Map(),files=[],seen=new Map();let total=0;
 const root=fs.realpathSync(item.root);
 function collect(file,name){
  if(seen.has(file))return seen.get(file);
  if(seen.size>=1000)fail('报告引用附件数量超过上限');
  const stat=fs.lstatSync(file),actual=fs.realpathSync(file);
  if(stat.isSymbolicLink() || !stat.isFile() || !actual.startsWith(root+path.sep))fail('附件超出报告产物范围');
  if(total+stat.size>32*1024*1024 || stat.size>10*1024*1024)fail('报告附件过大');
  const fd=openArtifact({file:actual,root});let bytes;try{bytes=fs.readFileSync(fd);}finally{fs.closeSync(fd);}
  total+=bytes.length;seen.set(file,name);
  const originalHash=sum(bytes);
  if(path.extname(file).toLowerCase()==='.md'){
   const rewritten=rewriteMarkdownAttachments(bytes.toString('utf8'),(url,isImage)=>{
    if(url.startsWith('#') || /^(https?:|mailto:)/i.test(url) && !isImage)return null;
    if(/^[a-z][a-z0-9+.-]*:/i.test(url))fail('外部图片或附件不能随包导出：'+url);
    let decoded;try{decoded=decodeURIComponent(url.split('#')[0].split('?')[0]);}catch{fail('附件路径编码无效');}
    if(decoded.includes('\\') || decoded.includes('\0'))fail('附件路径无效');
    const target=path.resolve(path.dirname(file),decoded);
    if(!target.startsWith(root+path.sep))fail('附件超出报告产物范围：'+url);
    const targetName=seen.get(target) || 'attachments/'+path.relative(root,target).split(path.sep).join('/');
    try{collect(target,targetName);}catch(error){fail('附件不可用：'+url+'；'+error.message);}
    const relative=path.posix.relative(path.posix.dirname(name),targetName);
    return relative.split('/').map(part=>encodeURIComponent(part)).join('/')+(url.includes('#')?'#'+url.split('#').slice(1).join('#'):'');
   });
   bytes=Buffer.from(rewritten);
  }
  entries.set(name,bytes);files.push({path:name,source:path.relative(root,file),source_sha256:originalHash,sha256:sum(bytes),size:bytes.length});
  return name;
 }
 collect(item.file,'report.md');
 entries.set('manifest.json',Buffer.from(JSON.stringify({files},null,2)));
 entries.set('README.txt',Buffer.from('解压后打开 report.md。图片、附件及被引用章节已收集到 attachments 目录，引用已改为包内路径。原始模型报告未修改。外部网页链接保留在线地址，不作为附件下载。\n'));
 return {filename:path.basename(item.file,'.md')+'.zip',bytes:zipFiles(entries)};
}
