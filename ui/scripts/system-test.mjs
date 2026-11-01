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

  const browser = startBrowser();
  let cdp;
  let agentLanes = 0;
  try {
    await waitFor('http://127.0.0.1:19222/json/version');
    cdp = await openPage();
    await cdp.send('Page.navigate', { url: BASE });
    await sleep(1200);

    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-strip.is-landing .refinery-stage').length"), 6);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-distribution .severity-critical').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-dist-row').length"), 2);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-distribution .refinery-dist-chip').length"), 9);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.eyebrow').length"), 0);
    assert.equal(await cdp.evaluate("getComputedStyle(document.body).backgroundColor"), 'rgb(255, 255, 255)');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.rail')).backgroundColor"), 'rgb(247, 247, 248)');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-art')).display"), 'block');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-shade')).display"), 'block');
    assert.equal(await cdp.evaluate("document.querySelector('.refinery-art').naturalWidth"), 1024);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"设置\"]').click()");
    await cdp.evaluate("document.querySelectorAll('.settings-segment button')[1].click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.documentElement.dataset.theme"), 'dark');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.rail')).backgroundColor"), 'rgb(23, 23, 23)');
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.refinery-strip')).backgroundColor"), 'rgb(32, 32, 32)');
    await cdp.evaluate("document.querySelectorAll('.settings-segment button')[0].click()");
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"设置\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.rail-tooltip').length"), 8);
    assert.equal(await cdp.evaluate("document.querySelector('.rail-brand img').getAttribute('src')"), '/golden-shovel.webp');
    assert.ok(await cdp.evaluate("document.querySelector('.rail-brand img').naturalWidth > 0"));
    assert.equal(await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"]').getAttribute('title')"), null);
    assert.match(await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"] .rail-tooltip').textContent"), /按审计流程/);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"看板\"]').focus()");
    await sleep(180);
    assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.rail-button[aria-label=\"看板\"] .rail-tooltip')).visibility"), 'visible');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.rail-button[aria-current=\"page\"]').length"), 1);

    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"表格\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '表格');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.search-box').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.content-head').length"), 1);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"自动狩猎\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '自动狩猎');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.search-box').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.content-head').length"), 0);
    await cdp.evaluate("document.querySelector('.rail-button[aria-label=\"系统架构\"]').click()");
    await sleep(150);
    assert.equal(await cdp.evaluate("document.querySelector('.page-title h1').innerText"), '系统架构');
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card').length"), 5);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-stage, .arch-component').length"), 0);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-overview img').length"), 6);
    assert.ok(await cdp.evaluate("[...document.querySelectorAll('.arch-overview img')].every(img => img.complete && img.naturalWidth > 0)"));
    assert.match(await cdp.evaluate("document.querySelector('.arch-overview').innerText"), /从一座矿，到一份可信证据/);
    for (const [zoneIndex, stageCount, componentCount] of [
      [0, 6, 0],
      [1, 4, 0],
      [2, 2, 3],
      [3, 0, 4],
      [4, 0, 2]
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
          assert.match(detailText, /失败语义/);
          assert.match(detailText, /优化时重点检查/);
          assert.doesNotMatch(detailText, /undefined/);
          if (zoneIndex === 0 && index === 0) assert.match(detailText, /parallel_mine\.sh/);
          if (zoneIndex === 0 && index === 1) {
            assert.match(detailText, /sandbox\.sh shell/);
            assert.match(detailText, /sandbox\.sh isolate/);
            assert.match(detailText, /复用同一工作副本/);
          }
          if (zoneIndex === 2 && index === 0) assert.match(detailText, /当前只支持 HTTP 执行契约/);
          await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
          await sleep(100);
          assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone').length"), 1);
        }
      }
      await cdp.evaluate("document.querySelector('.arch-detail-back').click()");
      await sleep(100);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.arch-zone-card').length"), 5);
    }
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
      assert.match(await cdp.evaluate("document.querySelector('.live-strip').innerText"), /实时挖掘/);
      await cdp.evaluate("document.querySelector('.live-run-card').click()");
      for (let i = 0; i < 40; i += 1) {
        if (await cdp.evaluate("document.querySelectorAll('.live-drawer').length")) break;
        await sleep(100);
      }
      assert.equal(await cdp.evaluate("document.querySelectorAll('.live-drawer').length"), 1, await cdp.evaluate("document.body.innerText.slice(-1200)"));
      assert.match(await cdp.evaluate("document.querySelector('.live-drawer').innerText"), /实时挖掘日志|运行轨迹/);
      for (let i = 0; i < 40; i += 1) {
        if (await cdp.evaluate("document.querySelectorAll('.live-drawer .ccui-frame').length")) break;
        await sleep(250);
      }
      assert.equal(await cdp.evaluate("document.querySelectorAll('.live-drawer .ccui-frame').length"), 1);
      await sleep(1800);
      assert.equal(await cdp.evaluate("Boolean(document.querySelector('.ccui-frame')?.contentDocument?.getElementById('mygoldmine-embed-style'))"), true);
      assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.ccui-frame').contentDocument.querySelector('header.pwa-header-safe')).display"), 'none');
      assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.ccui-frame').contentDocument.querySelector('.chat-composer-shell')).display"), 'none');
      await cdp.evaluate("window.__mygoldmineLiveFrame = document.querySelector('.ccui-frame'); window.__mygoldmineFrameTimeOrigin = window.__mygoldmineLiveFrame.contentWindow.performance.timeOrigin; true");
      await sleep(16000);
      assert.equal(await cdp.evaluate("window.__mygoldmineLiveFrame === document.querySelector('.ccui-frame')"), true);
      assert.equal(await cdp.evaluate("window.__mygoldmineFrameTimeOrigin === document.querySelector('.ccui-frame').contentWindow.performance.timeOrigin"), true);
      await cdp.evaluate("[...document.querySelectorAll('.live-drawer .traj-switch button')].find((b) => b.textContent.includes('Agent 拓扑')).click()");
      for (let i = 0; i < 40; i += 1) {
        if (await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-lane').length")) break;
        await sleep(100);
      }
      assert.equal(await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-lane').length"), agentLanes);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-origin').length"), 1);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.agent-topology .agent-stage').length"), 8);
      assert.match(await cdp.evaluate("document.querySelector('.agent-topology').innerText"), /Agent 拓扑/);
      await cdp.evaluate("[...document.querySelectorAll('.live-drawer .traj-switch button')].find((b) => b.textContent.includes('原始日志')).click()");
      await sleep(400);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.live-drawer .live-log').length"), 1);
      await cdp.evaluate("document.querySelector('.live-drawer .on-dark').click()");
      await sleep(200);
    }
    const rawCard = await cdp.evaluate("[...document.querySelectorAll('.refinery-strip.is-landing .refinery-stage')].map(x => x.innerText)");
    assert.match(rawCard[0], /原矿/);
    assert.match(rawCard[0], new RegExp(String(inbox)));
    assert.doesNotMatch(rawCard[0], /723/);

    await cdp.evaluate("document.querySelectorAll('.refinery-strip.is-landing .refinery-stage')[0].click()");
    await sleep(500);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.stage-view').length"), 1);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.refinery-stage.is-active').length"), 1);
    assert.match(await cdp.evaluate("document.querySelector('.refinery-stage.is-active').innerText"), /原矿/);
    assert.equal(Number(await cdp.evaluate("document.querySelector('.stage-count').innerText")), inbox);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.stage-view .finding-card').length"), inbox);
    if (inbox) {
      await cdp.evaluate("document.querySelector('.stage-view .finding-card').click()");
      await sleep(250);
      assert.equal(await cdp.evaluate("document.querySelectorAll('.detail-drawer').length"), 1);
      assert.equal(await cdp.evaluate("getComputedStyle(document.querySelector('.detail-drawer .drawer-head')).backgroundColor"), 'rgb(255, 255, 255)');
      await cdp.evaluate("document.querySelector('.detail-drawer .on-dark').click()");
      await sleep(200);
    }

    await cdp.evaluate("document.querySelectorAll('.refinery-strip .refinery-stage')[1].click()");
    await sleep(500);
    assert.match(await cdp.evaluate("document.querySelector('.refinery-stage.is-active').innerText"), /分诊/);
    assert.equal(Number(await cdp.evaluate("document.querySelector('.stage-count').innerText")), triage);
    assert.equal(await cdp.evaluate("document.querySelectorAll('.stage-view .card-grip').length"), 0);
    await cdp.evaluate("document.querySelector('.refinery-dist-chip.severity-critical').click()");
    await sleep(250);
    const criticalStageCount = Number(await cdp.evaluate("document.querySelector('.stage-count').innerText"));
    const criticalStripCount = Number(await cdp.evaluate("document.querySelectorAll('.refinery-strip .refinery-stage strong')[1].innerText"));
    assert.equal(criticalStripCount, criticalStageCount);
    await cdp.evaluate("document.querySelector('.refinery-dist-chip.severity-critical').click()");
    await sleep(250);

    await cdp.evaluate("document.querySelector('.project-row').click()");
    await sleep(500);
    const projectStageCount = Number(await cdp.evaluate("document.querySelector('.stage-count').innerText"));
    const projectStripCount = Number(await cdp.evaluate("document.querySelectorAll('.refinery-strip .refinery-stage strong')[1].innerText"));
    assert.equal(projectStripCount, projectStageCount);
    assert.ok(projectStageCount <= triage);
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
