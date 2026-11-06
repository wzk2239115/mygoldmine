import fs from 'node:fs';
import path from 'node:path';

const fail=message=>{throw Object.assign(new Error(message),{code:'artifact_contract'});};
function read(file) {
 if(fs.lstatSync(file).isSymbolicLink())fail('正式蓝队交付清单或报告不能是符号链接：'+file);
 try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{fail('正式蓝队交付清单或报告无效：'+file);}
}
export function verificationReports(root) {
 root=path.resolve(root);
 const summary=path.join(root,'summary.json');
 if(!fs.existsSync(summary))fail('蓝队交付缺少正式批次清单：'+summary);
 const batch=read(summary);
 if(!batch || !Array.isArray(batch.findings))fail('蓝队正式批次清单缺少候选结果数组');
 const seen=new Set(),reports=[];
 for(const row of batch.findings) {
  const id=row?.finding_id;
  if(typeof id!=='string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(id) || seen.has(id))fail('蓝队正式候选编号无效或重复');
  seen.add(id);
  const folder=path.join(root,id),file=path.join(folder,'verify-report.json');
  if(row.report_path && path.resolve(root,row.report_path)!==file)fail('正式蓝队报告路径与候选编号不一致：'+id);
  if(row.run_dir && path.resolve(root,row.run_dir)!==folder)fail('正式蓝队目录与候选编号不一致：'+id);
  if(!fs.existsSync(file))fail('正式蓝队报告缺失：'+file);
  if(fs.realpathSync(folder)!==folder)fail('正式蓝队候选目录包含符号链接：'+folder);
  const report=read(file);
  if(report.finding_id!==id || (batch.project && report.project!==batch.project))fail('正式蓝队报告的项目或候选编号不一致：'+id);
  reports.push({file,boundary:root});
 }
 return reports;
}
