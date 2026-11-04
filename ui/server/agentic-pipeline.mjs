import {verifyTasks} from './verify-tasks.mjs';
import { stageLearning } from './stage-learning.mjs';
import { nodeAttempts, retryEligibility, supportsNodeRetry } from './node-retries.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { listAgenticTraces } from './agentic-traces.mjs';

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function exists(file) {
  return fs.existsSync(file);
}

function usableEnvironment(value) {
  return value === 'ready' || value === 'partial';
}

function makeNode(id, title, agent, status, detail, artifact = '') {
  return { id, title, agent, status, detail, artifact };
}

function environmentCapabilities(run, phase) {
  if (phase?.final?.capabilities) return phase.final.capabilities;
  // 兼容旧记录：共享清单必须仍绑定同一环境，且未在本次运行结束后更新。
  const expected = path.resolve(run.runDir, '../../..', 'env', run.project, 'env-manifest.json');
  if (!phase?.manifest || path.resolve(phase.manifest) !== expected) return null;
  const manifest = readJson(expected);
  const verifiedAt = Date.parse(manifest?.reuse_verification?.verified_at || manifest?.built_at);
  const endedAt = Date.parse(phase.updated_at);
  if (!manifest || manifest.project !== run.project || manifest.source !== phase.source
      || manifest.image !== phase.final?.image || !Number.isFinite(verifiedAt)
      || !Number.isFinite(endedAt) || verifiedAt > endedAt
      || fs.statSync(expected).mtimeMs > endedAt + 1000) return null;
  return { ...manifest, acceptance: manifest.reuse_verification?.checks || manifest.acceptance || [] };
}

function environmentNode(run, status, phase) {
  const id = 'environment';
  const title = '环境构建';
  const agent = 'environment-builder';
  const artifact = phase?.manifest || '';
  if (phase) {
    const finalStatus = phase.final?.status || 'blocked';
    const agentStatus = phase.agent?.status || '';
    const evidence = environmentCapabilities(run, phase);
    const checks = Array.isArray(evidence?.acceptance) ? evidence.acceptance : [];
    const failedChecks = checks.filter(check => check?.required !== false
      && ((check?.exit_code != null && Number(check.exit_code) !== 0) || check?.status === 'failed'));
    const recordedLimits = Array.isArray(evidence?.limitations) && evidence.limitations.length
      ? evidence.limitations : evidence?.partial_reasons;
    const limitations = [...new Set((Array.isArray(recordedLimits) ? recordedLimits : []).filter(item => typeof item === 'string'))];
    const cpuOnly = String(evidence?.platform?.torch || '').includes('+cpu');
    const scope = !usableEnvironment(finalStatus) ? '沙箱不可用' : failedChecks.length ? '沙箱待验收' : cpuOnly ? 'CPU 沙箱可用' : finalStatus === 'partial' ? '部分能力可用' : '沙箱可用';
    const coverage = !usableEnvironment(finalStatus) ? '必要能力缺失' : failedChecks.length ? '必要验收未通过' : finalStatus === 'partial' ? '能力受限' : '已声明能力可用';
    const environment = { status: finalStatus, scope, coverage, limitations,
      checksPassed: checks.filter(check => check?.exit_code != null && Number(check.exit_code) === 0).length,
      checksFailed: failedChecks.length };
    const node = (state, detail) => ({ ...makeNode(id, title, agent, state, detail, artifact), environment });
    if (!usableEnvironment(finalStatus)) return node('blocked', '未交付可用沙箱');
    if (failedChecks.length) return node('degraded', `沙箱部分可用 · ${failedChecks.length} 项必要验收未通过`);
    const fallback = usableEnvironment(phase.baseline?.status) || !usableEnvironment(agentStatus)
      || (phase.agent?.exit_code != null && Number(phase.agent.exit_code) !== 0);
    if (fallback) {
      const reason = usableEnvironment(phase.baseline?.status) || agentStatus.includes('fallback') ? '使用了确定性备用方案' : '构建交付未确认';
      return node('degraded', `${scope} · ${reason}`);
    }
    return node('completed', `${scope} · ${coverage}`);
  }
  if (status.env_status === 'partial') {
    const completed = usableEnvironment(status.env_agent_status) && status.env_agent_reason === 'agent_primary';
    return { ...makeNode(id, title, agent, completed ? 'completed' : 'degraded', '沙箱部分可用 · 能力受限'),
      environment: { status: 'partial', scope: '部分能力可用', coverage: '能力受限', limitations: [] } };
  }
  if (usableEnvironment(status.env_status)) {
    return makeNode(id, title, agent, 'completed', '沙箱已交付');
  }
  if (status.env_status === 'blocked') {
    return makeNode(id, title, agent, 'blocked', status.env_agent_reason || '环境构建受阻');
  }
  if (run.isLive && (run.state === 'starting' || (!run.hasLog && !run.hasReport))) {
    return makeNode(id, title, agent, 'running', '正在准备容器和依赖');
  }
  return makeNode(id, title, agent, 'pending', '尚未生成环境构建记录');
}

function orchestratorNode(run, report) {
  const title = '安全审计编排';
  const agent = 'security-orchestrator';
  const count = Array.isArray(report?.findings) ? report.findings.length : 0;
  if (run.isLive) return makeNode('orchestrator', title, agent, 'running', '正在建模、拆分边界并挖掘候选');
  if (run.reportsComplete || (run.hasReport && ['completed', 'partial'].includes(run.state))) {
    return makeNode('orchestrator', title, agent, 'completed', `审计报告已生成 · ${count} 条候选`, run.reportPath || '');
  }
  if (['failed', 'timeout', 'stopped'].includes(run.state)) {
    const labels = { failed: '审计运行失败', timeout: '审计运行超时', stopped: '审计已停止' };
    const raw = path.join(run.runDir, 'raw.jsonl');
    const startup = path.join(`${run.runDir}.meta`, 'wrapper.log');
    if ((!exists(raw) || fs.statSync(raw).size === 0) && exists(startup)) {
      const fd = fs.openSync(startup, 'r');
      const size = fs.fstatSync(fd).size;
      const buffer = Buffer.alloc(Math.min(size, 8192));
      try { fs.readSync(fd, buffer, 0, buffer.length, Math.max(0, size - buffer.length)); } finally { fs.closeSync(fd); }
      const copyFailed = /cp: cannot create/.test(buffer.toString());
      return makeNode('orchestrator', title, agent, 'failed', copyFailed ? '启动前源码复制失败，审计智能体未启动' : '启动阶段退出，审计智能体尚未生成会话；查看启动日志了解原因', startup);
    }
    return makeNode('orchestrator', title, agent, 'failed', labels[run.state], run.logPath || '');
  }
  return makeNode('orchestrator', title, agent, 'pending', '等待环境就绪');
}

function visualNode(run, summary) {
  const title = '攻击场景设计';
  const agent = 'attack-scene-director';
  const artifact = summary?.output_dir || '';
  if (summary) {
    const step = summary.steps?.render_attack_scenes_agentic || {};
    const count = Number(summary.scene_count || 0);
    if (step.attempted && step.returncode === 0) {
      return makeNode('visual', title, agent, 'completed', `智能体场景设计完成 · ${count} 张场景图`, artifact);
    }
    if (step.attempted) {
      return makeNode('visual', title, agent, 'degraded', `智能体场景设计失败，已使用直接绘图备用方案 · ${count} 张场景图`, artifact);
    }
    return makeNode('visual', title, agent, 'skipped', `未调用场景智能体 · ${count} 张场景图`, artifact);
  }
  if (run.visualStatus === 'blocked') return makeNode('visual', title, agent, 'blocked', '图文场景生成受阻');
  if (run.visualStatus === 'skipped') return makeNode('visual', title, agent, 'skipped', '本次运行已跳过图文场景');
  if (run.visualStatus === 'ready') {
    return makeNode('visual', title, agent, 'degraded', '图文产物就绪，但缺少场景智能体调用记录');
  }
  if (run.isLive && run.hasReport) return makeNode('visual', title, agent, 'running', '正在生成图文报告与场景');
  if (run.hasReport && ['failed', 'partial'].includes(run.state)) {
    return makeNode('visual', title, agent, 'failed', '没有完整的图文场景汇总');
  }
  return makeNode('visual', title, agent, 'pending', '等待审计报告');
}

function verifyNode(run, summary) {
  const title = '蓝队验证';
  const agent = 'verify-agent';
  const artifact = summary ? path.join(run.runDir, 'verify/agent/summary.json') : '';
  if (summary) {
    const counts = Object.entries(summary.counts || {}).map(([key, value]) => `${key}=${value}`).join(' · ');
    const entries = Array.isArray(summary.findings) ? summary.findings : [];
    const blocked = entries.filter((item) => item.verdict === 'blocked').length || Number(summary.counts?.blocked || 0);
    const total = entries.length || Number(summary.processed || 0);
    const state = summary.status === 'failed' ? 'failed'
      : summary.status === 'blocked' || (blocked > 0 && blocked === total) ? 'blocked'
      : summary.status === 'partial' || blocked > 0 ? 'degraded' : 'completed';
    return makeNode('verify', title, agent, state, counts || '验证执行完成', artifact);
  }
  const state = run.verifyAgentStatus || '';
  if (state === 'completed') return makeNode('verify', title, agent, 'completed', '验证阶段已完成');
  if (state === 'failed') return makeNode('verify', title, agent, 'failed', '验证智能体或执行器失败');
  if (state === 'blocked') return makeNode('verify', title, agent, 'blocked', '环境不可用，验证未启动');
  if (state === 'skipped') return makeNode('verify', title, agent, 'skipped', '本次运行已跳过蓝队验证');
  if (run.isLive && run.visualStatus === 'ready') return makeNode('verify', title, agent, 'running', '正在验证候选问题');
  return makeNode('verify', title, agent, 'pending', '等待候选问题和可用环境');
}

function redteamNodes(run, summary) {
  const results = Array.isArray(summary?.results) ? summary.results : [];
  const buildFailed = results.filter((item) => item.status === 'build_failed' || !item.scenario || (Number(item.builder_returncode) || 0) !== 0);
  const labsReady = results.filter((item) => item.scenario && !buildFailed.includes(item));
  let labStatus = 'pending';
  let labDetail = '等待蓝队验证结果';
  if (results.length) {
    labDetail = `${labsReady.length}/${results.length} 个隔离场景可用`;
    labStatus = buildFailed.length === results.length ? 'blocked' : buildFailed.length ? 'degraded' : 'completed';
    if (buildFailed.length) labDetail += ` · ${buildFailed.length} 个场景未就绪`;
  } else if (run.redteamStatus === 'blocked') {
    labStatus = 'blocked';
    labDetail = '环境不可用，红队场景构建未启动';
  } else if (run.redteamStatus === 'failed') {
    labStatus = 'failed';
    labDetail = '红队阶段失败，未生成场景汇总';
  } else if (run.redteamStatus === 'skipped') {
    labStatus = 'skipped';
    labDetail = '本次运行已跳过红队验证';
  } else if (run.redteamStatus === 'no_findings') {
    labStatus = 'skipped';
    labDetail = '没有需要构建的红队场景';
  } else if (run.isLive && run.verifyAgentStatus === 'completed') {
    labStatus = 'running';
    labDetail = '正在构建隔离验证场景';
  }

  const executed = results.filter((item) => item.agent_returncode !== undefined && item.agent_returncode !== null);
  const executionSucceeded = executed.filter((item) => Number(item.agent_returncode) === 0);
  const executionFailed = executed.filter((item) => Number(item.agent_returncode) !== 0);
  let executionStatus = 'pending';
  let executionDetail = '等待可用隔离场景';
  if (executed.length) {
    executionDetail = `${executed.length}/${results.length} 个红队执行已结束`;
    executionStatus = executionSucceeded.length && executionFailed.length
      ? 'degraded'
      : executionSucceeded.length ? 'completed' : 'failed';
    if (executionFailed.length) executionDetail += ` · ${executionFailed.length} 个失败`;
  } else if (labsReady.length && run.isLive) {
    executionStatus = 'running';
    executionDetail = '正在隔离环境执行验证';
  } else if (run.redteamStatus === 'skipped' || run.redteamStatus === 'no_findings') {
    executionStatus = 'skipped';
    executionDetail = labDetail;
  }

  const judged = results.filter((item) => item.judge_returncode !== undefined && item.judge_returncode !== null);
  const approved = results.filter((item) => item.status === 'judge_approved');
  const judgeFailed = judged.filter((item) => Number(item.judge_returncode) === 124 || item.status === 'judge_timeout');
  let judgeStatus = 'pending';
  let judgeDetail = '等待红队执行轨迹';
  if (judged.length) {
    judgeStatus = judgeFailed.length === judged.length ? 'failed' : judgeFailed.length ? 'degraded' : 'completed';
    judgeDetail = `独立审核已完成 · 通过 ${approved.length}/${judged.length}`;
  } else if (executed.length && run.isLive) {
    judgeStatus = 'running';
    judgeDetail = '正在独立审核执行轨迹';
  } else if (run.redteamStatus === 'skipped' || run.redteamStatus === 'no_findings') {
    judgeStatus = 'skipped';
    judgeDetail = labDetail;
  }

  const artifact = summary ? path.join(run.runDir, 'redteam/summary.json') : '';
  return [
    makeNode('redteam-lab', '红队场景构建', 'redteam-lab-builder', labStatus, labDetail, artifact),
    makeNode('redteam-agent', '红队执行', 'scripts/redteam/agent.py', executionStatus, executionDetail, artifact),
    makeNode('judge', '独立审核', 'exploit-judge', judgeStatus, judgeDetail, artifact)
  ];
}

function learnerNode(run, postValidation, learnerLog, driver) {
  const title = '经验学习';
  const agent = 'mining-repair-learner';
  const artifact = postValidation ? path.join(run.runDir, 'rsi/post-validation.json') : '';
  if (postValidation?.status === 'completed') {
    const candidates = Number(postValidation.candidates || 0);
    const evaluation = driver?.status ? ` · 评估：${driver.status}` : '';
    return makeNode('learner', title, agent, 'completed', `经验学习完成 · ${candidates} 个修复候选${evaluation}`, artifact);
  }
  if (learnerLog) {
    return makeNode('learner', title, agent, run.isLive ? 'running' : 'failed', run.isLive ? '正在生成挖掘修复候选' : '学习日志存在，但没有完成记录', path.join(run.runDir, 'rsi/learner.jsonl'));
  }
  return makeNode('learner', title, agent, 'pending', '等待红蓝验证经验');
}

export function buildAgenticPipeline(run) {
  const status = readJson(path.join(`${run.runDir}.meta`, 'status.json')) || {};
  const phase = readJson(path.join(`${run.runDir}.meta`, 'env-phase.json'));
  const report = run.reportPath ? readJson(run.reportPath) : null;
  const visual = readJson(path.join(run.runDir, 'visual-rendered/visual-summary.json'));
  const verify = readJson(path.join(run.runDir, 'verify/agent/summary.json'));
  const redteam = readJson(path.join(run.runDir, 'redteam/summary.json'));
  const postValidation = readJson(path.join(run.runDir, 'rsi/post-validation.json'));
  const driver = readJson(path.join(run.runDir, 'rsi/driver.json'));
  const learnerLog = exists(path.join(run.runDir, 'rsi/learner.jsonl'));
  const nodes = [
    environmentNode(run, status, phase),
    orchestratorNode(run, report),
    visualNode(run, visual),
    verifyNode(run, verify),
    ...redteamNodes(run, redteam),
    learnerNode(run, postValidation, learnerLog, driver)
  ];
  for (const node of nodes) {
    node.traces = listAgenticTraces(run, node.id).map((trace) => ({
      id: trace.id,
      label: trace.label,
      kind: trace.kind,
      size: trace.size,
      updatedAt: trace.updatedAt
    }));
  }
  // The supervisor owns progression; total-run liveness is not node liveness.
  const recordedStage = readJson(path.join(`${run.runDir}.meta`, 'pipeline-stage.json'));
  let active = recordedStage?.node;
  const interrupted = !run.isLive && ['stopped', 'failed', 'timeout'].includes(run.state);
  const environmentStarted = exists(`${run.runDir}.meta/env-phase0.log`) || nodes[0].traces.length > 0;
  if (!active && (run.isLive || (interrupted && environmentStarted))) {
    // Compatibility for runs started before stage recording was added.
    if (learnerLog) active = 'learner';
    else if (exists(`${run.runDir}.meta/redteam.log`)) active = 'redteam-lab';
    else if (exists(`${run.runDir}.meta/verify.log`)) active = 'verify';
    else if (exists(`${run.runDir}.meta/visual-report.log`)) active = 'visual';
    else if (phase || usableEnvironment(status.env_status) || status.env_agent_status === 'skipped_env' || exists(path.join(run.runDir, 'raw.jsonl'))) active = 'orchestrator';
    else active = 'environment';
  }
  const activeIndex = nodes.findIndex(node => node.id === active);
  if (run.isLive && activeIndex >= 0) {
    const descriptions = {
      environment: '正在构建环境并准备源码', orchestrator: '正在执行安全审计',
      visual: '正在生成攻击场景', verify: '正在验证候选问题',
      'redteam-lab': '正在构建红队场景', 'redteam-agent': '正在执行红队验证',
      judge: '正在独立审核', learner: '正在处理审计经验'
    };
    nodes.forEach((node, index) => {
      if (index > activeIndex) {
        node.status = 'pending';
        node.detail = `等待${nodes[index - 1].title}`;
      } else if (index === activeIndex) {
        node.status = 'running';
        node.detail = descriptions[node.id] + (recordedStage?.candidate ? ` · 候选 ${recordedStage.candidate}` : '');
      } else if (node.id === 'orchestrator' && report) {
        node.status = 'completed';
        node.detail = `审计报告已生成 · ${Array.isArray(report.findings) ? report.findings.length : 0} 条候选`;
      } else if (['redteam-lab', 'redteam-agent', 'judge'].includes(node.id) && !redteam && activeIndex >= 4 && activeIndex <= 6) {
        node.status = 'pending';
        node.detail = '红队批次处理中，等待最终汇总';
      } else if (node.status === 'running') {
        node.status = 'pending';
        node.detail = '本阶段已结束，等待结果记录';
      } else if (node.status === 'pending' && !node.traces.length) {
        node.status = 'skipped';
        node.detail = '本阶段未执行，已进入后续阶段';
      }
    });
  }
  let notice = '';
  if (interrupted && activeIndex >= 0) {
    const current = nodes[activeIndex];
    if (['pending', 'running'].includes(current.status)) {
      current.status = 'stopped';
      current.detail = '任务已中断，本阶段未完成；可查看已有执行记录';
    }
    for (const node of nodes.slice(activeIndex + 1)) {
      if (!node.traces.length && ['pending', 'running', 'skipped', 'failed'].includes(node.status)) {
        node.status = 'not_started';
        node.detail = `${current.title}阶段中断，本阶段未执行`;
      }
    }
    notice = `任务在${current.title}阶段中断，后续阶段未执行`;
  }
  for (const node of nodes) {
    if (node.id === 'verify') node.verification = verifyTasks(run);
    node.learning = stageLearning(path.resolve(run.runDir, '../../..'), run.project, node.id);
    if (node.id === 'learner') node.detail += ` · 阶段技能待评估 ${node.learning.projectCandidates} 条`;
    node.retrySupported = supportsNodeRetry(node.id);
    node.retryReason = retryEligibility(run, node.id);
    const latest = nodeAttempts(run.runDir, node.id).at(-1);
    if (latest) {
      node.status = latest.status === 'running' ? 'running' : latest.resultStatus || 'failed';
      node.detail = latest.status === 'running' ? '正在独立重跑此节点' : latest.recovery?.kind === 'aggregation-only' ? '汇总已恢复；候选未重新执行，原始错误记录保留' : '节点重跑已结束；原始流程记录保留';
      node.retryReason = latest.status === 'running' ? '此节点正在重跑' : node.retryReason;
    }
    if (node.id === 'redteam-lab' && latest) {
      const progress=readJson(path.join(latest.workspace,'redteam/summary.json'));
      if(progress)node.detail=`场景构建 ${progress.processed}/${progress.selected} 已结束 · 可用 ${progress.ready} · 受阻 ${progress.blocked}${progress.current ? ` · 当前 ${progress.current}` : ''}`;
    }
    if (node.id === 'verify') {
      const info = node.verification;
      const labels = {confirmed:'确认',rejected:'排除',inconclusive:'待定',blocked:'受阻'};
      node.candidateSummary = Object.entries(labels).filter(([key])=>info.counts[key]>0).map(([key,label])=>`${label} ${info.counts[key]}`).join(' · ');
      if (info.selectedCount || info.tasks.length) {
        const progress = `${info.processedCount}/${info.selectedCount} 条候选已处理`;
        node.detail = [progress,node.candidateSummary].filter(Boolean).join(' · ');
        if (node.status === 'failed') node.detail += ' · 批次异常退出，请查看执行日志';
        else if (node.status === 'running') node.detail += ' · 正在验证';
        const blocked = info.tasks.find(task=>task.verdict==='blocked' && task.reason);
        if (blocked && node.status !== 'running') node.detail += ` · ${blocked.id}：${blocked.reason}`;
      }
      if (node.status === 'degraded') node.statusLabel = info.counts.blocked > 0 ? '部分受阻' : '部分完成';
      if (latest?.recovery?.kind === 'aggregation-only') node.recoveryNotice = '汇总已恢复；候选未重新执行，原始错误记录保留';
    }
  }
  return {
    notice,
    project: run.project,
    projectName: run.projectName,
    runId: run.runId,
    state: run.state,
    activeNode: run.isLive && activeIndex >= 0 ? active : null,
    nodes,
    summary: {
      total: nodes.length,
      completed: nodes.filter((node) => node.status === 'completed').length,
      degraded: nodes.filter((node) => node.status === 'degraded').length,
      blocked: nodes.filter((node) => node.status === 'blocked' || node.status === 'failed').length
    }
  };
}
