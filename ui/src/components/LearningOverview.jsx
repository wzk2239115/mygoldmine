import {useEffect,useState} from 'react';
import {api} from '../api.js';
const stages={environment:'I 环境构建',orchestrator:'II 审计编排',visual:'III 攻击设计',verify:'IV 蓝队验证','redteam-lab':'V 场景构建','redteam-agent':'VI 红队执行',judge:'VII 独立审核',learner:'VIII 经验学习'};
const categories={method_gap:'方法缺口',project_knowledge:'项目经验',framework_bug:'框架问题',insufficient_evidence:'证据不足',no_change:'无需修改'};
const number=value=>Number.isFinite(value)?value.toLocaleString('zh-CN',{maximumFractionDigits:2}):'未记录';
export default function LearningOverview({project,runId,onTrace}){
 const [data,setData]=useState(null),[error,setError]=useState(''),[evidence,setEvidence]=useState({});
 useEffect(()=>{
  let alive=true,busy=false;
  async function refresh(){if(busy)return;busy=true;try{const value=await api.learningSummary(project,runId);if(alive){setData(value);setError('');}}catch(e){if(alive)setError(e.message);}finally{busy=false;}}
  refresh();const timer=setInterval(refresh,5000);
  return()=>{alive=false;clearInterval(timer);};
 },[project,runId]);
 useEffect(()=>{setEvidence({});},[data?.attemptId]);
 async function openEvidence(ref){
  setEvidence(current=>({...current,[ref.id]:{loading:true}}));
  try{const value=await api.learningSummary(project,runId,ref.id);setEvidence(current=>({...current,[ref.id]:value}));}
  catch(e){setEvidence(current=>({...current,[ref.id]:{error:e.message}}));}
 }
 if(!data)return <section className="learning-overview"><p role={error?'alert':undefined}>{error || '正在读取本轮学习结果…'}</p></section>;
 const failed=data.status==='failed',running=data.status==='running';
 const headline=failed?'本轮学习未完成':running?'正在整理本轮经验':!data.resultAvailable?'本轮尚无学习结论':data.proposals.length?'本轮已提出技能改进':'本轮未提出技能改动';
 return <section className="learning-overview" aria-label="本轮学习">
  <header className="learning-outcome"><span className="learning-eyebrow">本轮学习</span><h3>{headline}</h3>
   <p>{data.resultAvailable?<>整理了 {data.conclusions.length} 项归因，提出 {data.proposals.length} 项改进。{data.accepted?'已有工具接受回执。':'尚无工具接受回执。'}</>:running?'智能体仍在分析；有正式结果后在此更新。不会把有日志等同于学习完成。':'尚未生成结构化学习结果，可查看执行轨迹定位原因。'}</p>
   {data.error?<p role="alert">{data.error}</p>:null}
   {error?<p role="alert">更新失败：{error}；当前保留上次读取结果。</p>:null}
   <button className="traj-button" onClick={onTrace}>查看完整执行轨迹</button>
  </header>
  {data.metrics?<><div className="learning-metrics"><div><span>新增风险加权覆盖</span><strong>{number(data.metrics.coverage)}</strong></div><div><span>新增验证报告</span><strong>{number(data.metrics.reports)}</strong></div><div><span>本轮 RSI 分数</span><strong>{number(data.metrics.reward)}</strong></div></div><p className="learning-note">本轮观测结果，不代表某项技能修改带来了因果改善。</p></>:null}
  <h3>发现了什么</h3>
  {!data.conclusions.length?<p className="learning-note">尚无可展示的归因；不代表未发现问题。</p>:data.conclusions.map((row,index)=><article className="learning-conclusion" key={index}>
   <div className="learning-card-heading"><strong>{stages[row.stage] || row.stage}</strong><span>{categories[row.category] || row.category}</span></div>
   <p>{row.reason}</p><div className="learning-next"><strong>下一步</strong><p>{row.next_action}</p></div>
   <details><summary>查看依据（{row.evidence.length} 份）</summary>{row.evidence.map(ref=><div className="learning-evidence" key={ref.id}>
    <button className="traj-button" disabled={!ref.available || evidence[ref.id]?.loading} title={ref.label} onClick={()=>openEvidence(ref)}>{ref.label}{!ref.available?' · 文件不可用':''}</button>
    {evidence[ref.id]?.loading?<p>正在读取…</p>:null}
    {evidence[ref.id]?.error?<p role="alert">{evidence[ref.id].error}</p>:null}
    {evidence[ref.id]?.text!==undefined?<><pre>{evidence[ref.id].text}</pre>{evidence[ref.id].truncated?<p className="learning-note">仅展示文件开头 6000 字节；完整内容请通过产物或执行轨迹查看。</p>:null}</>:null}
   </div>)}</details>
  </article>)}
  <h3>准备改什么 · 是否生效</h3>
  {!data.proposals.length?<p className="learning-note">{data.resultAvailable?'本轮没有提交技能改进候选；原因见上方归因。不能把学习结束当作技能已更新。':'待学习智能体提交结果后显示。'}</p>:data.proposals.map(item=><article className="learning-conclusion" key={item.id}>
   <div className="learning-card-heading"><strong>{stages[item.stage] || '目标阶段未记录'}</strong><span>{item.active?'当前已启用':item.published?'本轮已发布，当前版本已变化':'尚未发布'}</span></div>
   <p className="learning-note">{item.scope==='general'?'通用技能':item.scope==='project'?'本项目技能':'适用范围未记录'} · 候选 {item.id.slice(0,12)}</p>
   {item.missing?<p>候选记录缺失，无法展示具体修改。</p>:<details><summary>查看修改内容</summary><div className="learning-diff"><div><strong>原有补充</strong><pre>{item.before || '没有可用的父版本内容；基础技能正文未在此作差异比较。'}</pre></div><div><strong>候选补充</strong><pre>{item.content || '未记录'}</pre></div></div></details>}
  </article>)}
  <p className="learning-note">{data.evaluationStatus==='no_verified_improvement'?'历史记录尚无经验证的改善。':data.evaluationStatus==='updated_for_next_round'?'本轮审计技能已更新，下一轮启动时直接加载；运行收益继续观察。':data.evaluationStatus==='learning_failed'?'学习调用失败，未完成本轮评估。':data.evaluationStatus?'已有评估记录；发布及当前启用状态以各候选标记为准。':'本轮暂无评估记录。'} 以实际启用版本为准；已经启动的轮次保持原版本。</p>
  {data.limitations.length?<details><summary>本轮限制（{data.limitations.length} 项）</summary><ul>{data.limitations.map((value,i)=><li key={i}>{value}</li>)}</ul></details>:null}
 </section>;
}
