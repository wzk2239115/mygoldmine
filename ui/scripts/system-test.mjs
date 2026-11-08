import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';

const PORT = Number(process.env.SYSTEM_TEST_PORT || 18987);
const BASE = `http://127.0.0.1:${PORT}`;
const CHROME = process.env.CHROME_BIN || `${process.env.HOME}/.cache/ms-playwright/chromium_headless_shell-1169/chrome-linux/headless_shell`;

async function waitFor(url, attempts = 60) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response;
    } catch {}
    await sleep(250);
  }
  throw new Error(`timed out waiting for ${url}`);
}

class Cdp {
  constructor(url) {
    this.url = url;
    this.id = 0;
    this.pending = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(String(event.data));
      if (!message.id) return;
      const waiter = this.pending.get(message.id);
      if (!waiter) return;
      this.pending.delete(message.id);
      if (message.error) waiter.reject(new Error(message.error.message));
      else waiter.resolve(message.result);
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'evaluate failed');
    return result.result.value;
  }

  close() {
    this.ws?.close();
  }
}

function startServer() {
  const child = spawn(process.execPath, ['server/index.mjs'], {
    cwd: new URL('..', import.meta.url).pathname,
    env: { ...process.env, PORT: String(PORT), HOST: '127.0.0.1', REFINE_WORKER: '0' },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  child.stdout.on('data', () => {});
  child.stderr.on('data', () => {});
  return child;
}

function startBrowser() {
  if (!existsSync(CHROME)) throw new Error(`chrome not found: ${CHROME}`);
  const child = spawn(CHROME, [
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--window-size=1440,1000',
    '--remote-debugging-port=19222',
    `--user-data-dir=/tmp/mygoldmine-system-test-${process.pid}`,
    'about:blank'
  ], { stdio: ['ignore', 'ignore', 'ignore'] });
  return child;
}

async function openPage() {
  const response = await fetch('http://127.0.0.1:19222/json/new?about:blank', { method: 'PUT' });
  const target = await response.json();
  const cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.connect();
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  return cdp;
}

async function main() {
  const board = await waitFor(`${BASE}/api/health`).then(() => fetch(`${BASE}/api/board`)).then((response) => response.json());
  const inbox = board.stats.status.inbox;
  const triage = board.stats.status.triage;
  const pipelineTarget = [...board.projects].sort((a, b) => String(b.startedAt || '').localeCompare(String(a.startedAt || '')))[0];
  const pipeline = await fetch(`${BASE}/api/runs/${pipelineTarget.id}/${pipelineTarget.latestRunId}/pipeline`).then((response) => response.json());
  assert.deepEqual(pipeline.nodes.map((node) => node.id), [
    'environment', 'orchestrator', 'visual', 'verify', 'redteam-lab', 'redteam-agent', 'judge', 'learner'
  ]);
  if (pipelineTarget.id === 'codex') {
    assert.deepEqual(pipeline.nodes.map((node) => node.status), [
      'blocked', 'completed', 'degraded', 'blocked', 'blocked', 'pending', 'pending', 'completed'
    ]);
  }

  const browser = startBrowser();
  let cdp;
  let agentLanes = 0;
  try {
    await waitFor('http://127.0.0.1:19222/json/version');
    cdp = await openPage();
    if (process.env.RSI_REWARDS_TEST_ONLY) {
      await cdp.send('Page.addScriptToEvaluateOnNewDocument', {source: `
        const originalFetch = window.fetch.bind(window);
        window.fetch = async (...args) => {
          const response = await originalFetch(...args);
          if (!String(args[0]).endsWith('/pipeline')) return response;
          const payload = await response.clone().json();
          const row = {formula_version:'rsi-two-signal-v1',run_id:'synthetic-ui-check',
            source_version:'test-source',alpha:0.01,beta:10,delta_risk_coverage:150,
            new_lines:100,new_verified:1,coverage_reward:1.5,vulnerability_reward:10,
            total:11.5,status:'complete',updated_at:'2026-11-08T08:00:00Z',
            notes:[],verified_ids:['test-verified-id'],
            coverage_details:[{file:'src/auth.py',ranges:[[1,100]],new_lines:100,weighted_lines:150}]};
          payload.rsiRewards = {current:row,history:[row]};
          return new Response(JSON.stringify(payload), {status:200,headers:{'Content-Type':'application/json'}});
        };
      `});
    }
    await cdp.send('Page.navigate', { url: BASE });
    await sleep(1200);

    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-pipeline .agentic-node').length"), 8);
    assert.deepEqual(await cdp.evaluate("[...document.querySelectorAll('.agentic-pipeline .agentic-node > strong')].map((node) => node.innerText)"), [
      '环境构建', '安全审计编排', '攻击场景设计', '蓝队验证', '红队场景构建', '红队执行', '独立审核', '经验学习'
    ]);
    assert.ok(pipeline.rsiRewards && Array.isArray(pipeline.rsiRewards.history));
    assert.equal(await cdp.evaluate("document.querySelectorAll('.rsi-rewards').length"), 1);
    await cdp.evaluate("document.querySelector('.rsi-rewards button').click()");
    assert.match(await cdp.evaluate("document.querySelector('.rsi-rewards').innerText"), /新增风险加权覆盖/);
    if (process.env.RSI_REWARDS_TEST_ONLY) {
      const text = await cdp.evaluate("document.querySelector('.rsi-rewards').innerText");
      assert.match(text, /11.5/);
      assert.match(text, /1.5/);
      await cdp.evaluate("document.querySelector('.rsi-rewards summary').click()");
      assert.match(await cdp.evaluate("document.querySelector('.rsi-rewards').innerText"), /src\/auth.py/);
      assert.match(await cdp.evaluate("document.querySelector('.rsi-rewards').innerText"), /test-verified-id/);
      assert.match(await cdp.evaluate("document.querySelector('.rsi-rewards').innerText"), /rsi-two-signal-v1/);
      console.log('RSI 奖励总分、两项贡献、历史记录与计算依据的浏览器检查通过（合成展示数据）。');
      return;
    }
    await cdp.evaluate("document.querySelector('.rsi-rewards button').click()");
    await cdp.evaluate("document.querySelector('.agentic-node[data-node-id=\"redteam-agent\"]').click()");
    await sleep(250);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-trace-drawer').innerText"), /红队执行 · 队员/);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"), 0);
    const executionTasks = pipeline.nodes.find(node=>node.id==='redteam-agent').execution?.tasks || [];
    assert.equal(await cdp.evaluate("document.querySelectorAll('[aria-label=\"红队执行队员\"] .verify-task').length"), executionTasks.length);
    if(executionTasks.length) {
      await cdp.evaluate("document.querySelector('[aria-label=\"红队执行队员\"] .verify-task button').click()");
      await sleep(300);
      assert.ok((await cdp.evaluate("document.querySelector('.agentic-current-task').innerText")).includes(executionTasks[0].id));
      const ownTrace = pipeline.nodes.find(node=>node.id==='redteam-agent').traces.find(trace=>trace.id===executionTasks[0].traceId);
      if(ownTrace && ['claude','execution'].includes(ownTrace.kind)) {
        for(let i=0;i<40;i++) {
          if(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"))break;
          await sleep(250);
        }
        assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),1);
        assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-text-trace').length"),0);
      }
      await cdp.evaluate("document.querySelector('.member-back').click()");
      assert.equal(await cdp.evaluate("document.querySelectorAll('[aria-label=\"红队执行队员\"] .verify-task').length"), executionTasks.length);
    }
    console.log('红队执行队员列表、个人轨迹入口和返回列表检查通过');
    await cdp.evaluate("document.querySelector('.agentic-trace-drawer button[aria-label=\"关闭轨迹\"]').click()");
    await cdp.evaluate("document.querySelector('.agentic-node[data-node-id=\"visual\"]').click()");
    await sleep(200);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-trace-drawer').innerText"), /攻击场景设计 · 队员/);
    const sceneTasks = pipeline.nodes.find(node=>node.id==='visual').scenes?.tasks || [];
    assert.equal(await cdp.evaluate("document.querySelectorAll('[aria-label=\"攻击场景设计队员\"] .verify-task').length"),sceneTasks.length);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
    if(sceneTasks.length) {
      await cdp.evaluate("document.querySelector('[aria-label=\"攻击场景设计队员\"] .verify-task button').click()");
      await sleep(200);
      assert.ok((await cdp.evaluate("document.querySelector('.agentic-current-task').innerText")).includes(sceneTasks[0].id));
      await cdp.evaluate("document.querySelector('.member-back').click()");
    }
    console.log('场景设计队员列表、个人会话入口和返回列表检查通过');
    await cdp.evaluate("document.querySelector('.agentic-trace-drawer button[aria-label=\"关闭轨迹\"]').click()");
    await cdp.evaluate("document.querySelector('.agentic-node[data-node-id=\"judge\"]').click()");
    await sleep(200);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-trace-drawer').innerText"), /独立审核 · 队员/);
    const reviewTasks = pipeline.nodes.find(node=>node.id==='judge').review?.tasks || [];
    assert.equal(await cdp.evaluate("document.querySelectorAll('[aria-label=\"独立审核队员\"] .verify-task').length"),reviewTasks.length);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
    if(reviewTasks.length) {
      await cdp.evaluate("document.querySelector('[aria-label=\"独立审核队员\"] .verify-task button').click()");
      await sleep(200);
      assert.ok((await cdp.evaluate("document.querySelector('.agentic-current-task').innerText")).includes(reviewTasks[0].id));
      if(!reviewTasks[0].traceId)assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
      await cdp.evaluate("document.querySelector('.member-back').click()");
    }
    console.log('独立审核队员列表、个人会话入口和返回列表检查通过');
    await cdp.evaluate("document.querySelector('.agentic-trace-drawer button[aria-label=\"关闭轨迹\"]').click()");
    await cdp.evaluate("document.querySelector('.agentic-node[data-node-id=\"orchestrator\"]').click()");
    await sleep(200);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
    assert.ok(await cdp.evaluate("[...document.querySelectorAll('.node-detail-actions button')].some(b=>b.textContent==='查看产物')"));
    const candidateFlow=pipeline.nodes.find(node=>node.id==='orchestrator').flow;
    assert.equal(await cdp.evaluate("document.querySelectorAll('.candidate-flow').length"),candidateFlow?1:0);
    if(candidateFlow)assert.match(await cdp.evaluate("document.querySelector('.candidate-flow summary').innerText"),/候选交接/);
    const triageInfo = pipeline.nodes.find(node=>node.id==='orchestrator').triage;
    assert.equal(await cdp.evaluate("document.querySelectorAll('.jev-panel').length"),triageInfo?1:0);
    if(triageInfo) {
      assert.equal(await cdp.evaluate("document.querySelector('.jev-panel').open"),false);
      await cdp.evaluate("document.querySelector('.jev-panel summary').click()");
      assert.match(await cdp.evaluate("document.querySelector('.jev-panel').innerText"),/不是漏洞概率/);
    }
    await cdp.evaluate("document.querySelector('.agentic-trace-drawer button[aria-label=\"关闭轨迹\"]').click()");
    await cdp.evaluate("document.querySelector('.agentic-node[data-node-id=\"learner\"]').click()");
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
    const learnerNode=pipeline.nodes.find(node=>node.id==='learner');
    if(learnerNode.traces[0]?.kind==='claude') {
    await cdp.evaluate("[...document.querySelectorAll('.node-detail-actions button')].find(b=>b.textContent==='查看执行轨迹').click()");

    for (let i = 0; i < 40; i += 1) {
      if (await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length")) break;
      await sleep(250);
    }
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer').length"), 1);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-trace-drawer').innerText"), /经验学习 · 执行轨迹/);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"), 1);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-trace-drawer .ccui-frame').getAttribute('src')"), /\/ccui\/session\//);
    assert.equal(pipeline.nodes.find(node=>node.id==='learner').retrySupported,true);
    const learnerSession = await fetch(`${BASE}/api/runs/${pipelineTarget.id}/${pipelineTarget.latestRunId}/ccui?node=learner`).then((response) => response.json());
    assert.equal(learnerSession.available, true);
    assert.equal(learnerSession.traceKind, 'claude');
    } else if(!learnerNode.traces.length) {
      assert.equal(await cdp.evaluate("[...document.querySelectorAll('.node-detail-actions button')].find(b=>b.textContent==='查看执行轨迹').disabled"),true);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
    }
    await cdp.evaluate("document.querySelector('.agentic-trace-drawer button[aria-label=\"关闭轨迹\"]').click()");
    await cdp.evaluate("document.querySelector('.agentic-node[data-node-id=\"environment\"]').click()");
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-trace-drawer .ccui-frame').length"),0);
    await cdp.evaluate("[...document.querySelectorAll('.node-detail-actions button')].find(b=>b.textContent==='查看执行轨迹').click()");
    const environmentNode = pipeline.nodes.find(node => node.id === 'environment');
    assert.equal(await cdp.evaluate(`document.querySelector('.agentic-node[data-node-id="environment"]').classList.contains('is-${environmentNode.status}')`), true);
    if (environmentNode.environment) {
      assert.match(await cdp.evaluate("document.querySelector('.agentic-environment-info summary').innerText"), /环境能力/);
      await cdp.evaluate("document.querySelector('.agentic-environment-info summary').click()");
      const details = await cdp.evaluate("document.querySelector('.agentic-environment-info').innerText");
      assert.ok(details.includes(environmentNode.environment.scope));
      for (const limitation of environmentNode.environment.limitations) assert.ok(details.includes(limitation));
    }
    const traceSelector = environmentNode.traces[0]?.kind === 'claude' ? '.agentic-trace-drawer .ccui-frame' : '.agentic-text-trace';
    for (let i = 0; i < 40; i += 1) {
      if (await cdp.evaluate(`document.querySelectorAll('${traceSelector}').length`)) break;
      await sleep(250);
    }
    assert.equal(await cdp.evaluate(`document.querySelectorAll('${traceSelector}').length`), 1);
    await cdp.evaluate("document.querySelector('.agentic-trace-drawer button[aria-label=\"关闭轨迹\"]').click()");
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-strip.is-landing .refinery-stage').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-distribution .severity-critical').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-dist-row').length"), 2);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-distribution .refinery-dist-chip').length"), 9);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.eyebrow').length"), 0);
    assert.equal(await cdp.evaluate("getComputedStyle(document.body).backgroundColor"), 'rgb(255, 255, 255)');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.rail')).backgroundColor"), 'rgb(247, 247, 248)');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-art')).display"), 'none');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-shade')).display"), 'none');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-strip.is-landing')).backgroundColor"), 'rgb(27, 29, 32)');
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"设置\"]').click()");
    await cdp.evaluate("document.querySelectorAll('.settings-segment button')[1].click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.documentElement.dataset.theme"), 'dark');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.rail')).backgroundColor"), 'rgb(23, 23, 23)');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-strip')).backgroundColor"), 'rgb(27, 29, 32)');
    await cdp.evaluate("document.querySelectorAll('.settings-segment button')[0].click()");
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"设置\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.rail-tooltip').length"), 9);
    assert.equal(await cdp.evaluate("document.querySelector('.rail-brand img').getAttribute('src')"), '/golden-shovel.webp');
    assert.ok(await cdp.evaluate("document.querySelector('.rail-brand img').naturalWidth > 0"));
    assert.equal(await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"]').getAttribute('title')"), null);
    assert.match(await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"] .rail-tooltip').textContent"), /按审计流程/);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"]').focus()");
    await sleep(180);
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.rail-button[aria-label=\"看板\"] .rail-tooltip')).visibility"), 'visible');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.rail-button[aria-current=\"page\"]').length"), 1);

    await cdp.evaluate("document.querySelector('.project-import-trigger').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.project-import-dialog').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.project-import-types button').length"), 2);
    await cdp.evaluate("document.querySelectorAll('.project-import-types button')[1].click()");
    await cdp.evaluate("document.querySelector('.project-directory-picker-trigger').click()");
    for (let index = 0; index < 30; index += 1) {
      if (await cdp.evaluate("document.querySelector('.directory-browser-current')?.innerText.startsWith('/')")) break;
      await sleep(100);
    }
    assert.equal(await cdp.evaluate("document.querySelectorAll('.directory-browser').length"), 1);
    assert.ok(await cdp.evaluate("document.querySelector('.directory-browser-current').innerText.startsWith('/')"));
    await cdp.evaluate("document.querySelector('button[aria-label=\"关闭目录选择器\"]').click()");
    assert.equal(await cdp.evaluate("document.querySelectorAll('.directory-browser').length"), 0);
    await cdp.evaluate("document.querySelector('input[aria-label=\"本地目录路径\"]').focus()");
    await cdp.send('Input.insertText', { text: `/tmp/mygoldmine-missing-import-${process.pid}` });
    await cdp.evaluate("document.querySelector('.project-import-dialog form').requestSubmit()");
    for (let index = 0; index < 30; index += 1) {
      if (await cdp.evaluate("document.querySelectorAll('.project-import-error').length")) break;
      await sleep(100);
    }
    assert.match(await cdp.evaluate("document.querySelector('.project-import-error').innerText"), /本地目录不存在或不可读取/);
    await cdp.evaluate("document.querySelector('.project-import-head button').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.project-import-dialog').length"), 0);

    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"表格\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '表格');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.search-box').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.content-head').length"), 1);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"自动审计\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '自动审计');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.search-box').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.content-head').length"), 0);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"系统架构\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '系统架构');
    assert.match(await cdp.evaluate("document.body.innerText"), /红队执行提供队员列表/);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card').length"), 5);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-stage, .arch-component').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-overview img').length"), 6);
    assert.ok(await cdp.evaluate("[...document.querySelectorAll('.arch-overview img')].every(img => img.complete && img.naturalWidth > 0)"));
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card')[4].querySelector('img').getAttribute('src')"), '/architecture/rsi-flywheel.webp');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card')[4].querySelector('img').naturalWidth"), 1536);
    assert.match(await cdp.evaluate("document.querySelector('.arch-overview').innerText"), /从目标源码到可信证据/);
    for (const [zoneIndex, stageCount, componentCount] of [
      [0, 6, 0],
      [1, 4, 0],
      [2, 2, 3],
      [3, 0, 7]
    ]) {
      await cdp.evaluate(`document.querySelectorAll('.arch-zone-card')[${zoneIndex}].click()`);
      await sleep(150);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone').length"), 1);
      assert.ok(await cdp.evaluate("document.querySelector('.arch-zone-hero img').naturalWidth > 0"));
      for (const [selector, count] of [
        ['.arch-zone-stages .arch-stage', stageCount],
        ['.arch-zone-components .arch-component', componentCount]
      ]) {
        for (let index = 0; index < count; index += 1) {
          await cdp.evaluate(`document.querySelectorAll('${selector}')[${index}].click()`);
          await sleep(100);
          assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-detail-card').length"), 4, `zone ${zoneIndex} ${selector}[${index}]`);
          const detailText = await cdp.evaluate("document.querySelector('.arch-detail').innerText");
          assert.match(detailText, /输入/);
          assert.match(detailText, /输出/);
          assert.match(detailText, /失败时如何处理/);
          assert.match(detailText, /优化时重点检查/);
          assert.doesNotMatch(detailText, /undefined/);
          if (await cdp.evaluate("document.querySelector('#arch-detail-title').innerText") === '在隔离环境验证漏洞') {
            assert.match(detailText, /blue_handoff\.py/);
            assert.match(detailText, /不传给独立攻击执行者/);
          }
          if (zoneIndex === 0 && index === 0) {
            assert.equal(await cdp.evaluate("document.querySelector('#arch-detail-title').innerText"), '选择项目并批量审计');
            assert.match(detailText, /项目清单/);
            assert.match(detailText, /parallel_mine\.sh/);
            assert.match(detailText, /控制同时运行的项目数和失败重试/);
            assert.match(detailText, /overnight\.sh/);
            assert.match(detailText, /后台启动、查看进度、停止和恢复未完成项目/);
            assert.match(detailText, /独立目录/);
          }
          if (zoneIndex === 0 && index === 2) {
            assert.equal(await cdp.evaluate("document.querySelector('#arch-detail-title').innerText"), '整理审计线索并拆分任务');
            assert.match(detailText, /0 到 1 的优先检查分数/);
            assert.match(detailText, /flags/);
            assert.match(detailText, /认证边界、子进程执行或危险反序列化/);
            assert.match(detailText, /只用于安排检查/);
            assert.match(detailText, /读过文件不等同于覆盖完成/);
            assert.match(detailText, /假设追踪/);
            assert.match(detailText, /复审只在源码、调用方、视角、假设、技能版本或验证条件变化时创建新尝试/);
            assert.match(detailText, /原生检索和技能加载工具（Grep、Glob、Skill）/);
            assert.match(detailText, /第 1 波固定启动 6 个 infra-analyst/);
            assert.match(detailText, /第 2、3 波最多各启动 6 个 audit-skill-worker/);
            assert.match(detailText, /最多执行 3 波、共 18 个分析任务/);
            assert.match(detailText, /不用任务数量推算召回率/);
            assert.match(detailText, /skill-runner 只作为兼容入口/);
          }
          if (zoneIndex === 0 && index === 3) {
            assert.equal(await cdp.evaluate("document.querySelector('#arch-detail-title').innerText"), '持续更新报告与完整性检查');
            assert.match(detailText, /数据结构、必填字段和系统语言全部通过检查才完整/);
            assert.doesNotMatch(detailText, /质量门/);
          }
          if (zoneIndex === 0 && index === 4) {
            assert.equal(await cdp.evaluate("document.querySelector('#arch-detail-title').innerText"), '时限与恢复');
            assert.match(detailText, /所有尝试共享实际运行时间/);
            assert.match(detailText, /按真实事件判断是否仍在推进/);
            assert.match(detailText, /等待中的工具调用不算空闲/);
            assert.match(detailText, /校验和匹配才复用成果/);
            assert.match(detailText, /原始事件、任务产物和历史恢复检查点/);
            assert.match(detailText, /每次尝试的健康状态/);
            assert.match(detailText, /实际运行时间耗尽后不再启动新尝试/);
            assert.match(detailText, /产物校验和/);
          }
          if (zoneIndex === 3 && selector === '.arch-zone-components .arch-component' && index === 0) {
            assert.equal(await cdp.evaluate("document.querySelector('#arch-detail-title').innerText"), '发现记录表');
            assert.match(detailText, /为每次发现的候选问题保留单独编号/);
            assert.match(detailText, /编号相同但含义不同的问题不共用状态/);
            assert.doesNotMatch(detailText, /同 ID 异义不串状态/);
          }
          if (zoneIndex === 0 && index === 1) {
            assert.match(detailText, /默认直接启动 environment-builder 智能体/);
            assert.match(detailText, /确定性脚本不再抢先执行/);
            assert.match(detailText, /没有产出可用环境时才执行确定性备用方案/);
            assert.match(detailText, /sandbox\.sh shell/);
            assert.match(detailText, /sandbox\.sh isolate/);
            assert.match(detailText, /复用同一工作副本/);
          }
          if (zoneIndex === 2 && index === 0) {
            const expectedTitle = selector === '.arch-zone-stages .arch-stage' ? '在隔离环境验证漏洞' : '隔离场景构建器';
            assert.equal(await cdp.evaluate("document.querySelector('#arch-detail-title').innerText"), expectedTitle);
            assert.match(detailText, /只能在攻击容器中执行命令/);
            assert.match(detailText, /不能读取宿主机文件、直接读取随机标记文件或操作 Docker/);
            assert.match(detailText, /执行器支持 HTTP、固定命令行和进程内库调用三种原语/);
            assert.match(detailText, /结构化 blocked\.json/);
          }
          await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
          await sleep(100);
          assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone').length"), 1);
        }
      }
      await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
      await sleep(100);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card').length"), 5);
    }

    await cdp.evaluate("document.querySelectorAll('.arch-zone-card')[4].click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.arch-zone-hero h2').innerText"), 'RSI 学习流程');
    assert.match(await cdp.evaluate("document.querySelector('.arch-rsi-why').innerText"), /为什么能形成 RSI 学习流程/);
    const boundaryText = await cdp.evaluate("document.querySelector('.arch-rsi-boundary').innerText");
    assert.match(boundaryText, /验证动作只建议；挖掘修复经评估才发布/);
    assert.match(boundaryText, /可用于动作训练的可信样本：0/);
    assert.match(boundaryText, /不证明因果/);
    assert.match(boundaryText, /未参与训练的留出项目/);
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.arch-rsi-step .arch-stage p')).fontSize"), '15px');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-rsi-loop .arch-stage').length"), 6);
    assert.deepEqual(await cdp.evaluate("[...document.querySelectorAll('.arch-rsi-loop .arch-stage h3')].map((node) => node.innerText)"), [
      '真实轨迹', '可信标签', '成本与收益评估', '跨项目验证与前后结果对比', '只读建议（shadow）', '挖掘修复发布'
    ]);
    const rsiStageText = await cdp.evaluate("document.querySelector('.arch-rsi-loop').innerText");
    assert.match(rsiStageText, /比较每种处理方式的成本与收益/);
    assert.match(rsiStageText, /在未参与训练的项目上检查效果，逐项比较前后结果/);
    assert.equal(await cdp.evaluate("[...document.querySelectorAll('.arch-rsi-loop .arch-stage')].every((node) => node.tagName === 'BUTTON' && node.getAttribute('aria-label').includes('实现细节'))"), true);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-rsi-step > svg').length"), 4);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-rsi-loop-links span').length"), 2);
    assert.match(await cdp.evaluate("document.querySelector('.arch-rsi-loop-links').innerText"), /发布后的新结果/);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-rsi-branch-node').length"), 3);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-rsi-branch-track > svg').length"), 2);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-rsi-branch-node > svg').length"), 2);

    for (let index = 0; index < 6; index += 1) {
      await cdp.evaluate(`document.querySelectorAll('.arch-rsi-loop .arch-stage')[${index}].click()`);
      await sleep(100);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-detail-card').length"), 4);
      const detailText = await cdp.evaluate("document.querySelector('.arch-detail').innerText");
      assert.match(detailText, /输入/);
      assert.match(detailText, /输出/);
      assert.match(detailText, /失败时如何处理/);
      assert.doesNotMatch(detailText, /undefined/);
      if (index === 2) {
        assert.match(detailText, /ridge/);
        assert.match(detailText, /verify、deep_read、human_review、duplicate_candidate、defer/);
      }
      if (index === 3) {
        assert.match(detailText, /不是因果离线策略评估/);
        assert.match(detailText, /不构造反事实/);
      }
      if (index === 4) {
        assert.match(detailText, /trusted_support=0/);
        assert.match(detailText, /static-only/);
        assert.match(detailText, /不发布为生产策略/);
      }
      await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
      await sleep(100);
    }

    for (let index = 0; index < 2; index += 1) {
      await cdp.evaluate(`document.querySelectorAll('.arch-rsi-branch-node .arch-component')[${index}].click()`);
      await sleep(100);
      const detailText = await cdp.evaluate("document.querySelector('.arch-detail').innerText");
      assert.match(detailText, /mutation=none/);
      assert.doesNotMatch(detailText, /undefined/);
      if (index === 0) {
        assert.match(detailText, /找出反复出现的执行失败/);
        assert.match(detailText, /只统计真实执行记录/);
        assert.doesNotMatch(await cdp.evaluate("document.querySelector('.arch-detail-group').innerText"), /audit_rsi/);
        assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-detail-card')[1].querySelectorAll('code').length"), 1);
      }
      if (index === 1) assert.match(detailText, /不自动修改验证程序/);
      await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
      await sleep(100);
    }
    await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
    await sleep(100);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card').length"), 5);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"待验收\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '待验收');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.rail-button.is-active').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelector('.rail-button[aria-current=\"page\"]').getAttribute('aria-label')"), '待验收');
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"]').click()");
    await sleep(150);

    await cdp.send('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
    await sleep(350);
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.sidebar')).visibility"), 'hidden');
    await cdp.evaluate("document.querySelector('.topbar-menu').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.topbar-menu').getAttribute('aria-expanded')"), 'true');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.sidebar')).visibility"), 'visible');
    await cdp.evaluate("document.querySelector('.topbar-menu').click()");
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"项目地图\"]').click()");
    await sleep(800);
    if (await cdp.evaluate("document.querySelectorAll('.map-detail').length")) {
      assert.notEqual(await cdp.evaluate("getComputedStyle(document.querySelector('.map-detail')).display"), 'none');
    }
    await cdp.send('Emulation.clearDeviceMetricsOverride');
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"]').click()");
    await sleep(150);

    if (board.liveRuns.length) {
      const liveRun = board.liveRuns[0];
      const topology = await fetch(`${BASE}/api/runs/${liveRun.project}/${liveRun.runId}/agents`).then((response) => response.json());
      agentLanes = topology.agents.length;
      assert.equal(await cdp.evaluate("document.querySelectorAll('.live-strip').length"), 1);
      assert.match(await cdp.evaluate("document.querySelector('.live-strip').innerText"), /实时审计/);
      await cdp.evaluate("document.querySelector('.live-run-card').click()");
      for (let i = 0; i < 40; i += 1) {
        if (await cdp.evaluate("document.querySelectorAll('.live-drawer').length")) break;
        await sleep(100);
      }
      assert.equal(await cdp.evaluate("document.querySelectorAll('.live-drawer').length"), 1, await cdp.evaluate("document.body.innerText.slice(-1200)"));
      assert.match(await cdp.evaluate("document.querySelector('.live-drawer').innerText"), /实时审计日志|运行轨迹/);
      if (agentLanes > 0) {
        for (let i = 0; i < 40; i += 1) {
          if (await cdp.evaluate("document.querySelectorAll('.live-drawer .ccui-frame').length")) break;
          await sleep(250);
        }
        assert.equal(await cdp.evaluate("document.querySelectorAll('.live-drawer .ccui-frame').length"), 1);
        let embedReady = false;
        for (let i = 0; i < 40; i += 1) {
          if (await cdp.evaluate("Boolean(document.querySelector('.ccui-frame')?.contentDocument?.getElementById('mygoldmine-embed-style'))")) {
            embedReady = true;
            break;
          }
          await sleep(250);
        }
        if (embedReady) {
          assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.ccui-frame').contentDocument.querySelector('header.pwa-header-safe')).display"), 'none');
          assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.ccui-frame').contentDocument.querySelector('.chat-composer-shell')).display"), 'none');
          await cdp.evaluate("window.__mygoldmineLiveFrame = document.querySelector('.ccui-frame'); window.__mygoldmineFrameTimeOrigin = window.__mygoldmineLiveFrame.contentWindow.performance.timeOrigin; true");
          await sleep(16000);
          assert.equal(await cdp.evaluate("window.__mygoldmineLiveFrame === document.querySelector('.ccui-frame')"), true);
          assert.equal(await cdp.evaluate("window.__mygoldmineFrameTimeOrigin === document.querySelector('.ccui-frame').contentWindow.performance.timeOrigin"), true);
        }
        await cdp.evaluate("[...document.querySelectorAll('.live-drawer .traj-switch button')].find((b) => b.textContent.includes('智能体拓扑')).click()");
        for (let i = 0; i < 40; i += 1) {
          if (await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-lane').length")) break;
          await sleep(100);
        }
        assert.equal(await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-lane').length"), agentLanes);
        assert.equal(await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-origin').length"), 1);
        assert.equal(await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-stage').length"), 8);
        assert.match(await cdp.evaluate("document.querySelector('.agent-topology').innerText"), /智能体拓扑/);
      }
      await cdp.evaluate("[...document.querySelectorAll('.live-drawer .traj-switch button')].find((b) => b.textContent.includes('原始日志')).click()");
      await sleep(400);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.live-drawer .live-log').length"), 1);
      await cdp.evaluate("document.querySelector('.live-drawer .on-dark').click()");
      await sleep(200);
    }

    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-strip.is-landing .refinery-stage').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-execution .agentic-node').length"), 8);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.pipeline-landing > .agentic-pipeline').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.agentic-cycle-lines .cycle-return').length"), 1);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-cycle-caption').innerText"), /评估通过/);
    assert.match(await cdp.evaluate("document.querySelector('.agentic-cycle-context').innerText"), /连续执行需启动循环任务/);
    assert.ok(await cdp.evaluate("document.body.innerText.includes('审计进度总览')"));
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-execution .cycle-control').length"), 1);
    const tops = await cdp.evaluate("[...document.querySelectorAll('.refinery-execution .agentic-node-index')].map(e=>e.getBoundingClientRect().top)");
    assert.ok(Math.abs(tops[0] - tops[1]) < 1, '同一行节点编号应对齐');

  } finally {
    cdp?.close();
    browser.kill('SIGKILL');
  }
  console.log(JSON.stringify({ ok: true, inbox, triage, agentLanes, rawStageShows: 'inbox only' }, null, 2));
}

let server;
try {
  server = startServer();
  await main();
} finally {
  server?.kill('SIGKILL');
}
