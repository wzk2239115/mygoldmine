import { useState } from 'react';
import { Archive, ArrowRight, BadgeCheck, Boxes, Filter, GitBranch, ShieldCheck } from 'lucide-react';
import { stageCount } from '../stage-model.js';
import { SEVERITIES, VERDICTS } from '../constants.js';
import { cx } from '../utils.js';

function Stage({ icon: Icon, label, value, hint, detail, tone, active, onClick, onHover }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      className={`refinery-stage tone-${tone || 'ink'}${active ? ' is-active' : ''}`}
      title={onClick ? `${detail || hint} · 点击进入` : (detail || hint)}
      aria-label={`${label}：${value} 条。${detail || hint}`}
      aria-pressed={onClick ? active : undefined}
      onClick={onClick}
      onMouseEnter={() => onHover?.({ label, detail: detail || hint })}
      onFocus={() => onHover?.({ label, detail: detail || hint })}
      onMouseLeave={() => onHover?.(null)}
      onBlur={() => onHover?.(null)}
    >
      <Icon size={13} aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
    </Tag>
  );
}

export default function RefineryStrip({ stats, stageStats = stats, activeStage, onSelectStage, landing, filters, setFilters, flow, executionChain }) {
  const [hovered, setHovered] = useState(null);
  if (!stats) return null;
  const status = stageStats.status || {};
  const raw = stageCount(stageStats, 'raw');
  const stages = [
    { id: 'raw', icon: Boxes, label: '未处理候选', value: raw, hint: `未处理候选（inbox） ${status.inbox || 0} · 已归档 ${status.archived || 0} 仅统计`, detail: `未进入自动分类的候选；已归档 ${status.archived || 0} 条不在这里展开。下一步：自动分类后台任务会处理未处理候选。`, tone: 'muted' },
    { id: 'triage', icon: Filter, label: '分诊', value: status.triage || 0, hint: '严重和高危候选自动入队', detail: '自动分类判定为严重或高危，等待人工判断可达性、重复和设计意图。下一步：自动流转后台任务会调用验证智能体。', tone: 'cool' },
    { id: 'reproduce', icon: GitBranch, label: '待验证', value: status.reproduce || 0, hint: 'CVE 等级候选或已有确认的验证结论；等待验证（尚未复现）', detail: 'CVE 等级候选或已有确认的验证结论，但尚未复现。下一步：自动流转后台任务会准备图文报告并调用红队。', tone: 'amber' },
    { id: 'cve', icon: ShieldCheck, label: 'CVE 跟踪', value: status.cve || 0, hint: '去重、披露、CNA', detail: '进入 CVE 去重和披露流程；当前需要人工或 CVE 裁定产物推进，不由自动流转创建。', tone: 'hot' },
    { id: 'review', icon: BadgeCheck, label: '待验收', value: stageStats.reviewReady || 0, hint: '红队随机标记、独立审核和图文报告', detail: '同时满足红队捕获随机标记、独立审核通过和图文报告已生成，等待人工最终验收。', tone: 'green' },
    { id: 'closed', icon: Archive, label: '已关闭', value: status.closed || 0, hint: '误报、重复、已知 CVE 或设计限制', detail: '误报、重复、已知 CVE 或设计限制；自动验证结论为已排除时也会进入这里。', tone: 'muted' }
  ];
  const flowStats = flow?.stats || {};
  const flowText = flow === undefined
    ? '自动流转：服务端未加载，需重启界面服务'
    : flow?.updatedAt
      ? `自动流转：${flow.paused ? '已暂停' : '运行中'} · 上轮处理 ${flowStats.processed ?? 0} · 待处理 ${flowStats.pending ?? 0} · 受阻 ${flowStats.blocked ?? 0}`
      : '自动流转：未启动（可运行 scripts/workflow/flow_worker.sh start）';
  return (
    <section className={landing ? "refinery-strip is-landing" : "refinery-strip"} aria-label={landing ? "审计执行链" : "自动分类管线"}>
      <img className="refinery-art" src="/refinery-hero.webp" alt="" aria-hidden="true" />
      <div className="refinery-shade" />
      {landing ? <div className="refinery-execution">{executionChain}</div> : <div className="refinery-track" aria-label="流程计数">
        {stages.map((stage, index) => (
          <div className="refinery-node" key={stage.label}>
            <Stage {...stage} active={activeStage === stage.id} onHover={setHovered} onClick={onSelectStage ? () => onSelectStage(stage.id) : undefined} />
            {index < stages.length - 1 ? <ArrowRight className="refinery-arrow" size={15} aria-hidden="true" /> : null}
          </div>
        ))}
      </div>}
      {!landing ? <div className="refinery-hint" aria-live="polite">
        {hovered ? <><strong>{hovered.label}</strong>：{hovered.detail}</> : flowText}
      </div> : null}
      {filters && setFilters ? (
        <div className="refinery-distribution">
          <div className="refinery-dist-row">
            <span className="refinery-dist-label">严重度</span>
            {SEVERITIES.map((severity) => {
              const selected = filters.severities.includes(severity.id);
              return (
                <button
                  key={severity.id}
                  type="button"
                  className={cx('refinery-dist-chip', `severity-${severity.id}`, selected && 'is-selected')}
                  aria-pressed={selected}
                  onClick={() => setFilters((current) => ({
                    ...current,
                    severities: current.severities.includes(severity.id)
                      ? current.severities.filter((item) => item !== severity.id)
                      : [...current.severities, severity.id]
                  }))}
                >
                  <i />
                  {severity.full}
                  <strong>{stats.severity?.[severity.id] ?? 0}</strong>
                </button>
              );
            })}
          </div>
          <div className="refinery-dist-row">
            <span className="refinery-dist-label">判定</span>
            {VERDICTS.filter((verdict) => verdict.id !== 'untriaged').map((verdict) => {
              const selected = filters.verdicts.includes(verdict.id);
              return (
                <button
                  key={verdict.id}
                  type="button"
                  className={cx('refinery-dist-chip', `verdict-chip-${verdict.id}`, selected && 'is-selected')}
                  aria-pressed={selected}
                  onClick={() => setFilters((current) => ({
                    ...current,
                    verdicts: current.verdicts.includes(verdict.id)
                      ? current.verdicts.filter((item) => item !== verdict.id)
                      : [...current.verdicts, verdict.id]
                  }))}
                >
                  {verdict.full}
                  <strong>{stats.verdict?.[verdict.id] ?? 0}</strong>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      <div className="refinery-flow" aria-hidden="true"><i /><i /><i /></div>
    </section>
  );
}
