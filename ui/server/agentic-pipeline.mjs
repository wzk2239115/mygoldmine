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

function environmentNode(run, status, phase) {
  const id = 'environment';
  const title = '环境构建';
  const agent = 'environment-builder';
  const artifact = phase?.manifest || '';
  if (phase) {
    const finalStatus = phase.final?.status || 'blocked';
    const agentStatus = phase.agent?.status || '';
    const detail = `智能体：${agentStatus || '未知'} · 环境：${finalStatus}`;
    if (usableEnvironment(finalStatus) && usableEnvironment(agentStatus)) {
      return makeNode(id, title, agent, 'completed', detail, artifact);
    }
    if (usableEnvironment(finalStatus)) {
      return makeNode(id, title, agent, 'degraded', `${detail} · 使用了确定性备用方案`, artifact);
    }
    return makeNode(id, title, agent, 'blocked', detail, artifact);
  }
  if (usableEnvironment(status.env_status)) {
    return makeNode(id, title, agent, 'completed', `环境：${status.env_status}`);
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
    return makeNode('orchestrator', title, agent, 'failed', `审计运行状态：${run.state}`, run.logPath || '');
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
    return makeNode('verify', title, agent, 'completed', counts || '验证执行完成', artifact);
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
  const buildFailed = results.filter((item) => item.status === 'build_failed' || (Number(item.builder_returncode) || 0) !== 0);
  const labsReady = results.filter((item) => item.scenario && !buildFailed.includes(item));
  let labStatus = 'pending';
  let labDetail = '等待蓝队验证结果';
  if (results.length) {
    labDetail = `${labsReady.length}/${results.length} 个隔离场景可用`;
    labStatus = buildFailed.length === results.length ? 'blocked' : buildFailed.length ? 'degraded' : 'completed';
    if (buildFailed.length) labDetail += ` · ${buildFailed.length} 个构建失败`;
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
  return {
    project: run.project,
    projectName: run.projectName,
    runId: run.runId,
    state: run.state,
    nodes,
    summary: {
      total: nodes.length,
      completed: nodes.filter((node) => node.status === 'completed').length,
      degraded: nodes.filter((node) => node.status === 'degraded').length,
      blocked: nodes.filter((node) => node.status === 'blocked' || node.status === 'failed').length
    }
  };
}
