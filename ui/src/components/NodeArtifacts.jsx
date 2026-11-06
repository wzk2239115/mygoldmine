import {useEffect,useState,useRef} from 'react';
import {api} from '../api.js';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {FileText,Image as ImageIcon,Braces,Workflow,Sparkles} from 'lucide-react';
import {artifactLink} from '../artifact-links.mjs';

export default function NodeArtifacts({project,runId,node,initialArtifactId=''}) {
 const [items,setItems]=useState(null),[selected,setSelected]=useState(null),[content,setContent]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let alive=true;setItems(null);setSelected(null);setError('');api.nodeArtifacts(project,runId,node).then(data=>{if(alive){setItems([...data.items].sort((a,b)=>{
 const rank=item=>item.name.endsWith('report-illustrated.md')?0:node==='visual' && /(?:^|\/)scene-[^/]+\.webp$/i.test(item.name)?1:item.type==='image' && !item.name.endsWith('.svg')?2:item.name.endsWith('.svg')?3:4;
 return rank(a)-rank(b);
}));setSelected(data.items.find(item=>item.id===initialArtifactId) || (node==='visual'?data.items.find(item=>item.name.endsWith('report-illustrated.md')) || null:null));}}).catch(error=>{if(alive)setError(error.message);});return()=>{alive=false;};},[project,runId,node,initialArtifactId]);
 useEffect(()=>{let alive=true;setContent(null);if(selected?.type==='text')api.nodeArtifact(project,runId,node,selected.id).then(data=>{if(alive)setContent(data);}).catch(error=>{if(alive)setError(error.message);});return()=>{alive=false;};},[selected,project,runId,node]);
 const [source,setSource]=useState(false);
 useEffect(()=>{setSource(false);},[selected]);
 const previewRef=useRef(null);
 useEffect(()=>{if(selected)previewRef.current?.scrollIntoView({block:'nearest',behavior:'instant'});},[selected]);
 const workspaceRef=useRef(null);
 const [gridColumns,setGridColumns]=useState(4);
 useEffect(()=>{
  const element=workspaceRef.current;if(!element)return;
  const observer=new ResizeObserver(([entry])=>{
   const rows=Math.max(1,Math.floor((entry.contentRect.height-28)/28));
   setGridColumns(Math.max(window.innerWidth<760?3:4,Math.ceil((items?.length || 0)/rows)));
  });
  observer.observe(element);return()=>observer.disconnect();
 },[items?.length]);
 const url=selected?api.nodeArtifactUrl(project,runId,node,selected.id):'';
 return <section className="node-artifacts" aria-label="节点产物">
  {error?<p className="inline-error" role="alert">{error}</p>:null}
  <p className="artifact-reading-hint">悬浮左侧文件查看完整路径 · 拖拽面板左边缘调整宽度</p>
  <div className="node-artifact-workspace" ref={workspaceRef} style={{'--artifact-columns':gridColumns}}>
  {items===null?<p>正在读取产物清单…</p>:!items.length?<p>本节点尚无可查看的产物。</p>:<div className="artifact-file-palette"><span className="artifact-file-count">{items.length} 个文件</span><div className="node-artifact-list">{items.map(item=>{
 const ai=node==='visual' && /(?:^|\/)scene-[^/]+\.webp$/i.test(item.name);
 const kind=item.name.endsWith('.svg')?'代码结构图':ai?'AI 生成':item.type==='image'?'图片':item.name.endsWith('report-illustrated.md')?'含图片':'文件';
 return <button type="button" key={item.id} title={`${kind} · ${item.name}\n${item.group} · ${Math.max(1,Math.ceil(item.size/1024))} KB`} aria-label={`${kind}：${item.name}`} aria-pressed={selected?.id===item.id} className={`artifact-cell ${ai?'cell-ai':item.name.endsWith('.svg')?'cell-diagram':item.name.endsWith('.md')?'cell-report':'cell-data'} ${selected?.id===item.id?'is-selected':''}`} onClick={()=>{setSelected(item);setError('');}}>{ai?<Sparkles size={14} aria-hidden="true"/>:item.name.endsWith('.svg')?<Workflow size={14} aria-hidden="true"/>:item.name.endsWith('.md')?<FileText size={14} aria-hidden="true"/>:item.type==='image'?<ImageIcon size={14} aria-hidden="true"/>:<Braces size={14} aria-hidden="true"/>}</button>;
 })}</div></div>}
  {selected?<article ref={previewRef} className="node-artifact-preview" aria-label="产物内容预览" aria-live="polite"><header><strong title={selected.name}>{selected.name.endsWith('.svg')?<span className="artifact-kind-badge">代码结构图</span>:node==='visual' && /(?:^|\/)scene-[^/]+\.webp$/i.test(selected.name)?<span className="artifact-kind-badge">AI 生成</span>:null}{selected.name.split('/').at(-1)}</strong><div className="artifact-actions">{selected.name.endsWith('.md')?<button type="button" aria-pressed={source} onClick={()=>setSource(value=>!value)}>{source?'阅读报告':'查看源码'}</button>:null}<a href={url+(selected.name.endsWith('.md')?'?bundle=1':'?download=1')} download>{selected.name.endsWith('.md')?'下载报告及附件（ZIP）':'下载产物'}</a></div></header>{selected.type==='image'?<img src={url+'?image=1'} alt={selected.name}/>:<>{content?.truncated?<p>内容较长，预览前512 KB；下载可查看完整文件。</p>:null}{content && selected.name.endsWith('.md') && !source?<div className="artifact-markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml urlTransform={(value,key)=>artifactLink(value,url,key==='src')} components={{img:({src,alt})=>src?<img src={src} alt={alt || '报告插图'} loading="lazy"/>:<span>{alt || '图片不可用'}</span>,a:({href,children})=><a href={href || undefined} target={href?.startsWith('http')?'_blank':undefined} rel="noopener noreferrer">{children}</a>}}>{content.text}</Markdown></div>:<pre>{content?.text ?? '正在读取产物…'}</pre>}</>}</article>:<article className="node-artifact-preview artifact-placeholder"><p>点击左侧文件，在此查看内容。</p></article>}
  </div>
 </section>;
}
