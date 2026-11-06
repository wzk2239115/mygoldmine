import {useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Mail,RefreshCw} from 'lucide-react';
export default function VerifiedReports({data,onRefresh}) {
 const {items,loading,error:loadError}=data;
 const [project,setProject]=useState('all');
 const [selected,setSelected]=useState(''),[error,setError]=useState('');
 const visible=items.filter(item=>project==='all' || item.project===project);
 const report=visible.find(item=>item.key===selected) || visible[0];
 const [downloading,setDownloading]=useState(false);
 async function downloadReport(){
  if(!report || downloading)return;setDownloading(true);setError('');
  try{
   const response=await fetch('/api/verified-reports/'+report.exportId+'/download');
   if(!response.ok){const result=await response.json();throw Error(result.error || '报告下载失败');}
   const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
   link.href=url;link.download=report.project+'-'+report.id+'-'+report.runId+'.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){setError(error.message);}finally{setDownloading(false);}
 }
 return <section className="verified-reports" aria-label="验证报告">
  <header><div><h2><Mail size={20}/>验证报告 <small>{visible.length} / {items.length} 份</small></h2><p>仅展示动态验证确认、红队证据核验通过、独立审核通过，并附文生图模型插图的报告。</p></div><button type="button" className="icon-button" aria-label="刷新验证报告" disabled={loading} onClick={onRefresh}><RefreshCw size={16}/></button></header>
  <div className="verified-report-filter"><label>报告项目 <select aria-label="报告项目" value={project} onChange={event=>setProject(event.target.value)}><option value="all">全部项目（{items.length}）</option>{[...new Set(items.map(item=>item.project))].sort().map(name=><option key={name} value={name}>{name}（{items.filter(item=>item.project===name).length}）</option>)}</select></label><span>此处筛选独立于看板；已有报告不会因切换看板项目而隐藏。</span></div>
  {error || loadError?<p role="alert">{error || loadError}</p>:null}
  {!report?<p>{loading?'正在读取验证报告…':'当前没有符合全部条件的报告；候选问题和受阻记录仍可在看板中查看。'}</p>:<div className="verified-report-layout"><aside aria-label="验证报告列表">{visible.map(item=><button type="button" key={item.key} aria-pressed={report.key===item.key} onClick={()=>setSelected(item.key)}><span>{item.project} · {item.id}</span><strong>{item.title}</strong><small>已验证 · AI 插图</small></button>)}</aside><article className="artifact-markdown" aria-label="已验证漏洞图文报告"><button type="button" className="cycle-control" disabled={downloading} onClick={downloadReport}>{downloading?'正在打包…':'下载报告及附件（ZIP）'}</button><Markdown remarkPlugins={[remarkGfm]} skipHtml>{report.markdown}</Markdown></article></div>}
 </section>;
}
