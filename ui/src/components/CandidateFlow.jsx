export default function CandidateFlow({flow}) {
 if(!flow)return null;
 const labels={recorded:'已记录',pending:'待处理',completed:'已结束',running:'运行中',queued:'排队',blocked:'受阻',failed:'失败',interrupted:'已中断',stale:'版本已变化'};
 return <details className="candidate-flow"><summary>候选交接 · 总表 {flow.total} · 本阶段有记录 {flow.recorded} · 未进入 {flow.pending}</summary>
  <p>每条候选均保留在总表中。未进入本批次、待定和受阻不代表安全，也不计为验证完成。</p>
  {flow.stale?<p role="alert">输入报告版本已变化，请重新核对本阶段结果。</p>:null}
  {flow.orphans.length?<p role="alert">发现不属于当前报告的记录：{flow.orphans.join('、')}，未计入当前候选。</p>:null}
  <div className="candidate-flow-table"><table><thead><tr><th>候选编号</th><th>状态</th><th>去向与原因</th></tr></thead><tbody>{flow.rows.map((row,index)=><tr key={row.id+'-'+index}><td title={row.title}>{row.id}</td><td>{labels[row.state] || '已记录'}</td><td>{row.reason}</td></tr>)}</tbody></table></div>
 </details>;
}
