import {useState} from 'react';
const labels={running:'运行中',completed:'已完成',partial:'部分失败',incomplete:'未完整结束',unavailable:'暂无报告'};
const signals={auth_boundary:'身份与权限边界',untrusted_model_input:'不可信模型输入',auth_check:'身份与权限检查',control_plane:'控制面入口',model_loading:'模型加载',remote_code:'远程代码加载',path_allowlist:'路径白名单',subprocess_exec:'外部命令执行',deserialization:'反序列化',outbound_url:'外部地址请求',default_exposure:'默认暴露',repo_config:'仓库配置',auto_load:'自动加载配置',explicit_confirmation:'显式确认',weight_deserialization:'权重反序列化',adapter_resolver:'适配器路径解析',hardcoded_secret:'硬编码凭据',secret_logging:'敏感信息输出',secret_in_url:'地址中的敏感信息'};
function Signals({values}) {return Object.keys(values).length?Object.entries(values).map(([key,value])=><span className="jev-signal" key={key}>{signals[key] || key}：{typeof value==='number'?value.toFixed(2):String(value)}</span>):'—';}
export default function JevTriage({triage}) {
 const [query,setQuery]=useState('');
 if(!triage)return null;
 const total=triage.stats.units;
 const finished=(triage.processedUnits || 0)+(triage.failedUnits || 0);
 const rows=triage.units.filter(row=>`${row.id} ${row.path}`.toLowerCase().includes(query.toLowerCase()));
 return <details className="jev-panel">
  <summary>Jev 文件初筛 · {labels[triage.status] || triage.status}</summary>
  <p>外层脚本在深度审计前进行语义初筛。分数表示检查优先级，不是漏洞概率或确认结论；低分文件也可能存在遗漏。</p>
  {triage.notice?<p role="status">{triage.notice}</p>:null}
  <div className="jev-stats"><span>成功处理 <strong>{triage.processedUnits ?? '未知'}</strong> / {total ?? '未知'} 个单元</span><span>失败单元 {triage.failedUnits ?? '未知'}</span><span>成功请求 {triage.stats.requests ?? '未知'}</span><span>缓存命中 {triage.stats.cached ?? '未知'}</span><span>错误计数 {triage.stats.errors ?? '未知'}</span></div>
  {total>0?<progress max={total} value={Math.min(total,finished)} aria-label="Jev 初筛处理进度"/>:null}
  {triage.stats.input_tokens!=null?<p>输入词元 {triage.stats.input_tokens.toLocaleString()} · 输出词元 {(triage.stats.output_tokens || 0).toLocaleString()}{triage.stats.cost!=null?` · 接口记录费用 $${Number(triage.stats.cost).toFixed(6)}`:''}</p>:null}
  <p>配置：{triage.profile || '尚未记录'} · 模型：{triage.model || '尚未记录'}{triage.workers?` · 并发上限 ${triage.workers}`:''}{triage.stats.elapsed_ms!=null?` · 已记录耗时 ${Math.round(triage.stats.elapsed_ms/1000)} 秒`:''}</p>
  {triage.units.length?<><label>筛选优先检查文件 <input value={query} onChange={event=>setQuery(event.target.value)} placeholder="输入文件路径" /></label><p>展示分数最高的 {triage.shown} 条 / 已获得 {triage.totalResults} 条结果。审计器还需检查低置信度和未覆盖区域。</p>
  <div className="jev-table-scroll"><table><thead><tr><th>优先级</th><th>文件与行号</th><th>风险信号</th><th>防护信号</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td><strong>{Number(row.priority).toFixed(3)}</strong>{row.cached?<small>缓存</small>:null}</td><td>{row.path || row.id}{row.lineStart?`:${row.lineStart}–${row.lineEnd}`:''}</td><td><Signals values={row.flags}/></td><td><Signals values={row.mitigations}/></td></tr>)}</tbody></table>{!rows.length?<p>没有匹配的文件。</p>:null}</div></>:null}
 </details>;
}
