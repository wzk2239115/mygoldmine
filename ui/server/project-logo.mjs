import fs from 'node:fs';
import path from 'node:path';

export function projectLogo(repoRoot, project, configured = '') {
  if (configured) return configured;
  if (!/^[a-z0-9][a-z0-9._-]{0,79}$/.test(project) || project === '.' || project === '..') return '';
  return fs.existsSync(path.join(repoRoot, 'ui/public/logos', `${project}.png`)) ? `/logos/${project}.png` : '';
}

const downloads=new Map();
export function queueProjectLogo(repoRoot,project,url,fetcher=globalThis.fetch) {
 if(projectLogo(repoRoot,project) || !/^[a-z0-9][a-z0-9._-]{0,79}$/.test(project))return Promise.resolve('');
 let parsed;try{parsed=new URL(String(url).replace(/^git@([^:]+):/,'https://$1/'));}catch{return Promise.resolve('');}
 if(!['github.com','gitlab.com'].includes(parsed.hostname) || parsed.username || parsed.password)return Promise.resolve('');
 const owner=parsed.pathname.split('/').filter(Boolean)[0];
 if(!owner || !/^[a-zA-Z0-9_.-]+$/.test(owner))return Promise.resolve('');
 const key=path.resolve(repoRoot)+'\0'+project;
 const previous=downloads.get(key);
 if(previous && Date.now()-previous.at<600000)return previous.promise;
 const source='https://'+parsed.hostname+'/'+owner+'.png'+(parsed.hostname==='github.com'?'?size=80':'');
 const promise=(async()=>{
  try {
   const response=await fetcher(source,{signal:AbortSignal.timeout(8000),headers:{'User-Agent':'mygoldmine-logo-fetch/1.0'}});
   if(!response.ok || !(response.headers.get('content-type') || '').startsWith('image/'))return '';
   const length=Number(response.headers.get('content-length') || 0);if(length>1024*1024)return '';
   const chunks=[];let size=0;
   for await(const chunk of response.body){size+=chunk.length;if(size>1024*1024)return '';chunks.push(Buffer.from(chunk));}
   const bytes=Buffer.concat(chunks);
   if(bytes.length<64 || !(bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])) || bytes.subarray(0,3).equals(Buffer.from([255,216,255])) || bytes.subarray(0,4).toString()==='GIF8' || (bytes.subarray(0,4).toString()==='RIFF' && bytes.subarray(8,12).toString()==='WEBP')))return '';
   const folder=path.join(repoRoot,'ui/public/logos');fs.mkdirSync(folder,{recursive:true});
   const target=path.join(folder,project+'.png'),temp=target+'.'+process.pid+'.tmp';
   fs.writeFileSync(temp,bytes);fs.renameSync(temp,target);
   return '/logos/'+project+'.png';
  }catch{return '';}
 })();
 downloads.set(key,{at:Date.now(),promise});return promise;
}
