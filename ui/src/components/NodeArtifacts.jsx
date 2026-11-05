import {useEffect,useState,useRef} from 'react';
import {api} from '../api.js';

export default function NodeArtifacts({project,runId,node}) {
 const [items,setItems]=useState(null),[selected,setSelected]=useState(null),[content,setContent]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let alive=true;api.nodeArtifacts(project,runId,node).then(data=>{if(alive)setItems(data.items);}).catch(error=>{if(alive)setError(error.message);});return()=>{alive=false;};},[project,runId,node]);
 useEffect(()=>{let alive=true;setContent(null);if(selected?.type==='text')api.nodeArtifact(project,runId,node,selected.id).then(data=>{if(alive)setContent(data);}).catch(error=>{if(alive)setError(error.message);});return()=>{alive=false;};},[selected,project,runId,node]);
 const previewRef=useRef(null);
 useEffect(()=>{if(selected)previewRef.current?.scrollIntoView({block:'nearest',behavior:'instant'});},[selected]);
 const url=selected?api.nodeArtifactUrl(project,runId,node,selected.id):'';
 return <section className="node-artifacts" aria-label="节点产物">
  {error?<p className="inline-error" role="alert">{error}</p>:null}
  <p className="member-roster-hint">选择产物查看内容或下载；原始运行与最近重跑分别标记。</p>
  <div className="node-artifact-workspace">
  {items===null?<p>正在读取产物清单…</p>:!items.length?<p>本节点尚无可查看的产物。</p>:<div className="node-artifact-list">{items.map(item=><button type="button" key={item.id} aria-pressed={selected?.id===item.id} className={selected?.id===item.id?'is-selected':''} onClick={()=>{setSelected(item);setError('');}}><strong>{item.name}</strong><small>{item.group} · {Math.max(1,Math.ceil(item.size/1024))} KB</small></button>)}</div>}
  {selected?<article ref={previewRef} className="node-artifact-preview" aria-label="产物内容预览" aria-live="polite"><header><strong>{selected.name}</strong><a href={url+'?download=1'} download>下载产物</a></header>{selected.type==='image'?<img src={url+'?image=1'} alt={selected.name}/>:<>{content?.truncated?<p>内容较长，预览前512 KB；下载可查看完整文件。</p>:null}<pre>{content?.text ?? '正在读取产物…'}</pre></>}</article>:<article className="node-artifact-preview artifact-placeholder"><p>点击左侧文件，在此查看内容。</p></article>}
  </div>
 </section>;
}
