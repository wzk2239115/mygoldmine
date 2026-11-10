
import fs from 'node:fs';
import path from 'node:path';
export function formalLabFiles(workspace,delivery) {
 const root=path.resolve(workspace),files=new Set();
 function add(file) {
  file=path.resolve(file);
  if(!file.startsWith(root+path.sep))throw Error('正式产物超出本次输出目录：'+file);
  let cursor=root;
  for(const name of path.relative(root,file).split(path.sep)){
   cursor=path.join(cursor,name);
   if(fs.lstatSync(cursor).isSymbolicLink())throw Error('正式交付引用不能包含符号链接：'+cursor);
  }
  if(!fs.statSync(file).isFile())throw Error('正式产物必须为文件：'+file);
  files.add(file);
 }
 const redteam=path.join(root,'redteam');
 add(path.join(redteam,'summary.json'));
 const selection=path.join(redteam,'selection.json');
 if(fs.existsSync(selection)){
  add(selection);
  for(const row of JSON.parse(fs.readFileSync(selection)).candidates || [])
   for(const key of ['finding','blue_handoff'])if(row[key])add(row[key]);
 }
 for(const item of delivery.deliveries || []){
  add(item.receipt);add(item.artifact);
  for(const entry of item.files || [])add(entry.path);
  const data=JSON.parse(fs.readFileSync(item.artifact));
  if(typeof data.driver==='string')add(path.resolve(path.dirname(item.artifact),data.driver));
  for(const name of data.status==='blocked'?data.evidence || []:[])add(path.resolve(path.dirname(item.artifact),name));
  const task=path.join(path.dirname(item.artifact),'lab-task.json');
  if(fs.existsSync(task))add(task);
 }
 return [...files];
}
