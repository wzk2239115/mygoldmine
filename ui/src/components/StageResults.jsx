const LABELS = {
 confirmed:'已确认', rejected:'已排除', inconclusive:'待定', blocked:'受阻',
 flag_captured:'已捕获随机标记', not_captured:'未捕获', blocked_harness_dependency:'运行依赖受阻',
 judge_approved:'审核通过', judge_rejected:'审核未通过', judge_needs_review:'需要复核',
 judge_error:'审核异常', running:'运行中', failed:'失败', not_run:'尚未执行',
 not_selected:'未进入本阶段', stale:'结果已过期', invalid:'关联无效',
 identity_ambiguous:'编号有歧义', evidence_invalid:'证据检查未通过', skipped:'已跳过'
};
export default function StageResults({results}) {
 if(!results || !Object.keys(results).length)return null;
 return <section className="detail-section finding-stage-results" aria-label="候选阶段结果">
  <h3>验证与审核结果</h3>
  {[['blue','蓝队验证'],['red','红队执行'],['judge','独立审核']].map(([key,title])=>{
   const row=results[key] || {status:'not_run'};
   return <div key={key} className="finding-stage-result" data-stage={key}>
    <div><strong>{title}</strong><span>{LABELS[row.status] || row.status}</span>{row.provenanceVerified?<small>证据已核验</small>:null}</div>
    {row.reason?<p>{row.reason}</p>:null}
    {row.artifact?<details><summary>结果来源</summary><code>{row.artifact}</code></details>:null}
   </div>;
  })}
 </section>;
}
