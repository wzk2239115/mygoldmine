import CoverageTokenChart from "./CoverageTokenChart.jsx";
import { useState } from 'react';

const number=value=>Number.isFinite(value)?value.toLocaleString('zh-CN',{maximumFractionDigits:4}):'—';

export default function RsiRewards({data}) {
  const [open,setOpen]=useState(false);
  const current=data?.current;
  return <><CoverageTokenChart data={data?.coverageTokens} /><section className="rsi-rewards" aria-label="RSI 每轮奖励">
    <button type="button" className="cycle-control" aria-expanded={open} onClick={()=>setOpen(!open)}>
      RSI 奖励 · {current ? `${number(current.total)} 分${current.status==='partial'?' · 数据未齐':''}` : '本轮等待计算'} · {open?'收起':'查看明细'}
    </button>
    {open ? <div>
      <p>R = α × 新增风险加权覆盖 + β × 新验证漏洞。没有新漏洞时，新增覆盖仍获得奖励。</p>
      {current ? <p>本轮：{number(current.delta_risk_coverage)} × {current.alpha} + {current.new_verified} × {current.beta} = <strong>{number(current.total)} 分</strong>。覆盖贡献 {number(current.coverage_reward)} 分，漏洞贡献 {number(current.vulnerability_reward)} 分。</p> : <p>阶段八收集前序结果时计算；已有历史不会补造奖励。</p>}
      <p>代码行按 1 + JEV 优先分数加权；没有优先分数的代码行权重为 1。读取记录表示代码接触范围。</p>
      {(data?.history || []).length ? <div style={{overflowX:'auto'}}><table style={{width:'100%',textAlign:'left'}}>
        <thead><tr>{['审计轮次','新增加权覆盖','覆盖奖励','新验证漏洞','漏洞奖励','总奖励','计算依据'].map(x=><th key={x}>{x}</th>)}</tr></thead>
        <tbody>{data.history.map(row=><tr key={row.run_id}>
          <td><code title={row.run_id}>{row.run_id}</code><small style={{display:'block'}}>{row.status==='complete'?'数据齐全':'数据未齐 · 暂计'} · {new Date(row.updated_at).toLocaleString('zh-CN')}</small></td>
          <td>{number(row.delta_risk_coverage)}</td><td>{number(row.coverage_reward)}</td><td>{row.new_verified}</td><td>{number(row.vulnerability_reward)}</td><td><strong>{number(row.total)}</strong></td>
          <td><details><summary>查看依据</summary>
            <p>公式版本：{row.formula_version}；α = {row.alpha}，β = {row.beta}。</p>
            <p>源码版本：<code>{row.source_version || '缺失'}</code>；新增读取 {number(row.new_lines)} 行。</p>
            {row.notes?.map(note=><p key={note}>{note}</p>)}
            <p>已验证问题：{row.verified_ids?.join('、') || '暂无新增'}。</p>
            <ul>{row.coverage_details?.map((entry,index)=><li key={index}><code>{entry.file}</code>：{entry.ranges.map(([a,b])=>`${a}–${b}`).join('、')} 行；加权 {number(entry.weighted_lines)} 行。</li>)}</ul>
          </details></td>
        </tr>)}</tbody>
      </table></div> : <p>尚无采用此公式计算的轮次。</p>}
      <small>分数表示本轮观测收益；源码版本变化会建立新的覆盖基线，不能据此认定技能改动产生了因果提升。</small>
    </div> : null}
  </section></>;
}
