import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';

export function isOperationLog(file) {
 return /(?:^|\/)\.workspace\/logs\/operations\.(?:jsonl|log)(?:\.\d+)?$/.test(file);
}
// Legacy recovery accepts only the exact previously frozen byte prefix.
export function snapshotOperationLog(file,repo,{size,sha256}={}) {
 if(!isOperationLog(file))throw Error('不是受支持的操作日志');
 const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
 let bytes;
 try {
  const stat=fs.fstatSync(fd),length=size??stat.size;
  if(!stat.isFile() || !Number.isSafeInteger(length) || length<0 || length>stat.size || length>64*1024*1024)throw Error('操作日志前缀长度无效');
  bytes=Buffer.alloc(length);let offset=0;
  while(offset<length){const n=fs.readSync(fd,bytes,offset,length-offset,offset);if(!n)throw Error('操作日志读取不完整');offset+=n;}
 }finally{fs.closeSync(fd);}
 const digest=createHash('sha256').update(bytes).digest('hex');
 if(sha256 && digest!==sha256)throw Error('操作日志原始前缀摘要不匹配，不能迁移');
 const directory=path.join(repo,'.state','operation-log-snapshots');fs.mkdirSync(directory,{recursive:true});
 const destination=path.join(directory,digest+path.extname(file));
 try{fs.writeFileSync(destination,bytes,{flag:'wx',mode:0o444});}
 catch(error){if(error.code!=='EEXIST')throw error;if(createHash('sha256').update(fs.readFileSync(destination)).digest('hex')!==digest)throw Error('已有操作日志快照被修改');}
 return {file:destination,size:bytes.length,sha256:digest,source:file,role:'operation-log-snapshot',boundary:directory};
}
