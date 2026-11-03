import { projectLogo } from './project-logo.mjs';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

export class ProjectImportError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

function text(value, limit = 200) {
  return String(value || '').trim().slice(0, limit);
}

export function normalizeProjectId(value) {
  const id = text(value, 80).toLowerCase();
  if (!/^[a-z0-9][a-z0-9._-]{0,79}$/.test(id) || id === '.' || id === '..') {
    throw new ProjectImportError('项目标识只能包含小写字母、数字、点、下划线和连字符，且必须以字母或数字开头');
  }
  if (['smoke', 'smoke-real', 'smoke-target'].includes(id)) {
    throw new ProjectImportError('该项目标识用于系统测试，请换一个标识');
  }
  return id;
}

function derivedProjectId(value) {
  const derived = text(value, 80)
    .replace(/\.git$/i, '')
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^[._-]+|[._-]+$/g, '');
  return normalizeProjectId(derived);
}

function githubSource(value) {
  const raw = text(value, 500);
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new ProjectImportError('请输入完整的 GitHub 仓库地址');
  }
  const parts = url.pathname.split('/').filter(Boolean);
  if (
    url.protocol !== 'https:' || url.hostname.toLowerCase() !== 'github.com' ||
    url.username || url.password || url.port || url.search || url.hash || parts.length !== 2
  ) {
    throw new ProjectImportError('仅支持 https://github.com/所有者/仓库 形式的公开仓库地址');
  }
  const repo = parts[1].replace(/\.git$/i, '');
  if (!repo || repo === '.' || repo === '..') throw new ProjectImportError('GitHub 仓库名称无效');
  return {
    source: `https://github.com/${parts[0]}/${repo}.git`,
    url: `https://github.com/${parts[0]}/${repo}`,
    owner: parts[0],
    name: repo
  };
}

export function parseProjectImport(body = {}) {
  const kind = text(body.kind, 20);
  if (!['local', 'github'].includes(kind)) {
    throw new ProjectImportError('导入方式必须是本地目录或 GitHub 仓库');
  }
  const source = kind === 'github' ? githubSource(body.source) : null;
  const localPath = kind === 'local' ? text(body.source, 1000) : '';
  if (kind === 'local' && (!localPath || !path.isAbsolute(localPath))) {
    throw new ProjectImportError('本地导入需要服务器上的绝对目录路径');
  }
  const project = body.project
    ? normalizeProjectId(body.project)
    : derivedProjectId(kind === 'github' ? source.name : path.basename(localPath));
  const branch = text(body.branch, 200);
  if (kind === 'local' && branch) throw new ProjectImportError('本地目录直接使用当前内容，不需要填写分支');
  if (branch.startsWith('-') || /[\x00-\x20\x7f]/.test(branch)) {
    throw new ProjectImportError('分支名称无效');
  }
  const commit = text(body.commit, 40).toLowerCase();
  if (commit && (kind !== 'github' || !/^[a-f0-9]{40}$/.test(commit))) throw new ProjectImportError('提交版本必须是完整的 40 位提交编号');
  return { kind, project, branch, ...(commit ? { commit } : {}), localPath, ...(source || {}) };
}

export function executeProcess(command, args, { cwd, timeout = 600000, idleTimeout = 0, env = process.env, maxOutput = 65536, onOutput = () => {}, signal } = {}) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new ProjectImportError('导入已取消', 499));
    const child = spawn(command, args, {
      detached: true,
      cwd,
      env: { ...env, GIT_TERMINAL_PROMPT: '0' },
      stdio: ['ignore', 'pipe', 'pipe']
    });
    let stdout = '';
    let stderr = '';
    let settled = false;
    let timedOut = false;
    const terminate = () => { try { process.kill(-child.pid, 'SIGKILL'); } catch { child.kill('SIGKILL'); } };
    const abort = () => terminate();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    const append = (current, chunk) => `${current}${chunk}`.slice(-maxOutput);
    const expire = () => { if (!settled) { timedOut = true; terminate(); } };
    const timer = timeout > 0 ? setTimeout(expire, timeout) : null;
    let idleTimer;
    const touch = () => {
      if (!idleTimeout || settled) return;
      clearTimeout(idleTimer);
      idleTimer = setTimeout(expire, idleTimeout);
    };
    touch();
    child.stdout.on('data', (chunk) => { touch(); stdout = append(stdout, chunk); onOutput(String(chunk)); });
    child.stderr.on('data', (chunk) => { touch(); stderr = append(stderr, chunk); onOutput(String(chunk)); });
    child.on('error', (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      clearTimeout(idleTimer);
      signal?.removeEventListener('abort', abort);
      reject(new ProjectImportError(`无法启动 ${command}：${error.message}`, 500));
    });
    child.on('close', (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      clearTimeout(idleTimer);
      signal?.removeEventListener('abort', abort);
      if (signal?.aborted) return reject(new ProjectImportError('导入已取消', 499));
      if (timedOut) return reject(new ProjectImportError(idleTimeout ? '连续 3 分钟没有收到下载输出，已停止本次下载；请检查网络后重试' : '操作超时，请检查网络、目录和审计服务日志', 504));
      resolve({ code, stdout, stderr });
    });
  });
}

async function writeJson(file, payload) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  const temporary = `${file}.${process.pid}.${Date.now()}.tmp`;
  await fsp.writeFile(temporary, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  await fsp.rename(temporary, file);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return {};
  }
}

function processError(result, fallback) {
  const detail = text(result.stderr || result.stdout, 1200);
  return new ProjectImportError(detail ? `${fallback}：${detail}` : fallback, 502);
}

async function gitValue(execute, target, args) {
  const result = await execute('git', ['-C', target, ...args], { timeout: 30000 });
  return result.code === 0 ? result.stdout.trim() : '';
}

function sanitizedRemote(value) {
  const remote = text(value, 1000);
  try {
    const url = new URL(remote);
    url.username = '';
    url.password = '';
    return url.toString();
  } catch {
    return remote;
  }
}

function runId(now) {
  return now().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
}

export function createProjectImporter({
  repoRoot,
  execute = executeProcess,
  now = () => new Date(),
  isProjectLive = () => false,
  getModelArgs = () => [],
  onImported = () => {}
}) {
  const targetsRoot = path.join(repoRoot, 'targets');
  const projectsFile = path.join(repoRoot, 'ui', 'data', 'projects.json');
  const manifestFile = path.join(targetsRoot, 'manifest.json');
  let queue = Promise.resolve();

  async function importAndStart(input, progress, signal) {
    const check = () => { if (signal?.aborted) throw new ProjectImportError('导入已取消', 499); };
    check();
    const originalExecute = execute;
    const run = async (command, args, options = {}) => {
      check();
      const result = await originalExecute(command, args, { ...options, signal });
      check();
      return result;
    };
    progress("正在检查项目参数与运行状态");
    const request = parseProjectImport(input);
    if (await isProjectLive(request.project)) {
      throw new ProjectImportError('该项目已有正在运行的审计，请先等待完成或停止当前运行', 409);
    }

    let createdTarget = false;
    let registered = false;
    let auditRunDir;
    const oldProject = readJson(projectsFile).projects?.[request.project];
    const oldManifest = readJson(manifestFile).projects?.[request.project];
    let target = request.localPath;
    try {
    let sourceUrl = request.url || '';
    if (request.kind === 'local') {
      progress('正在检查本地源码目录');
      try {
        target = await fsp.realpath(request.localPath);
        const stat = await fsp.stat(target);
        if (!stat.isDirectory()) throw new Error('not a directory');
      } catch {
        throw new ProjectImportError('本地目录不存在或不可读取');
      }
      sourceUrl = sanitizedRemote(await gitValue(run, target, ['remote', 'get-url', 'origin']));
    } else {
      target = path.join(targetsRoot, request.project);
      await fsp.mkdir(targetsRoot, { recursive: true });
      let exists = fs.existsSync(target);
      if (exists) {
        const head = await gitValue(run, target, ['rev-parse', '--verify', 'HEAD']);
        const entries = await fsp.readdir(target);
        const origin = await gitValue(run, target, ['remote', 'get-url', 'origin']);
        const sameOrigin = origin.replace(/\.git$/i, '') === request.source.replace(/\.git$/i, '');
        if (!head && (entries.length === 0 || (entries.every(name => name === '.git') && sameOrigin))) {
          const backup = path.join(repoRoot, 'backups', 'incomplete-imports', `${request.project}-${Date.now()}`);
          await fsp.mkdir(path.dirname(backup), { recursive: true });
          await fsp.rename(target, backup);
          progress('发现上次未完成的下载，已保留备份，正在重新下载');
          exists = false;
        }
      }
      if (exists) {
        progress('正在检查已有仓库，保留当前内容');
        const origin = await gitValue(run, target, ['remote', 'get-url', 'origin']);
        if (!origin) throw new ProjectImportError('目标目录已存在但不是 Git 仓库，请换一个项目标识', 409);
        if (origin.replace(/\.git$/i, '') !== request.source.replace(/\.git$/i, '')) {
          throw new ProjectImportError('该项目标识已对应另一个仓库，请换一个项目标识', 409);
        }
        const existingCommit = await gitValue(run, target, ['rev-parse', '--verify', 'HEAD']);
        if (!existingCommit) throw new ProjectImportError('现有目录没有有效提交且包含其他内容，请检查目录或更换项目标识', 409);
        if (request.commit && request.commit !== existingCommit) throw new ProjectImportError('现有目录属于另一个提交版本，请使用另一个项目标识以保留已有源码', 409);
        if (request.branch && !request.commit) {
          throw new ProjectImportError('该仓库已经导入，不会切换或覆盖现有分支；新分支请使用另一个项目标识', 409);
        }
      } else {
        progress('正在下载仓库' + (request.commit ? `，提交：${request.commit.slice(0, 8)}` : request.branch ? `，分支：${request.branch}` : '，使用默认分支'));
        createdTarget = true;
        if (request.commit) {
          await fsp.mkdir(target, { recursive: true });
          for (const args of [
            ['init', target],
            ['-C', target, 'remote', 'add', 'origin', request.source],
            ['-C', target, 'fetch', '--progress', '--depth', '1', 'origin', request.commit],
            ['-C', target, 'checkout', '--detach', request.commit]
          ]) {
            const result = await run('git', args, { cwd: repoRoot, timeout: args.includes('fetch') || args[0] === 'clone' ? 0 : 45000, idleTimeout: args.includes('fetch') || args[0] === 'clone' ? 180000 : 0, onOutput: progress });
            if (result.code !== 0) throw processError(result, '下载所选提交版本失败');
          }
          const actual = await gitValue(run, target, ['rev-parse', '--verify', 'HEAD']);
          if (actual !== request.commit) throw new ProjectImportError('下载后的提交版本与所选版本不一致', 502);
        } else {
          const args = ['clone', '--progress', '--depth', '1', '--single-branch'];
          if (request.branch) args.push('--branch', request.branch);
          args.push('--', request.source, target);
          const cloned = await run('git', args, { cwd: repoRoot, timeout: args.includes('fetch') || args[0] === 'clone' ? 0 : 45000, idleTimeout: args.includes('fetch') || args[0] === 'clone' ? 180000 : 0, onOutput: progress });
          if (cloned.code !== 0) throw processError(cloned, 'GitHub 仓库克隆失败');
        }
      }
    }

    if (await isProjectLive(request.project)) {
      throw new ProjectImportError('该项目已有正在运行的审计，请先等待完成或停止当前运行', 409);
    }
    progress('源码已就绪，正在读取版本信息并登记项目');
    const [commit, currentBranch] = await Promise.all([
      gitValue(run, target, ['rev-parse', 'HEAD']),
      gitValue(run, target, ['rev-parse', '--abbrev-ref', 'HEAD'])
    ]);
    const timestamp = now().toISOString();
    const auditRunId = runId(now);
    auditRunDir = path.join(repoRoot, 'runs', request.project, auditRunId);
    if (fs.existsSync(`${auditRunDir}.meta`) || fs.existsSync(auditRunDir)) {
      throw new ProjectImportError('审计目录已存在，请稍后重试', 409);
    }

    const projectsPayload = readJson(projectsFile);
    const projects = projectsPayload.projects && typeof projectsPayload.projects === 'object'
      ? projectsPayload.projects
      : {};
    const metadata = {
      ...(projects[request.project] || {}),
      name: projects[request.project]?.name || request.project,
      url: sourceUrl,
      logo: projectLogo(repoRoot, request.project, projects[request.project]?.logo),
      icon: projects[request.project]?.icon || 'layers',
      tone: projects[request.project]?.tone || 'ink'
    };
    check();
    registered = true;
    projects[request.project] = metadata;
    await writeJson(projectsFile, { schema_version: 1, projects });

    const manifest = readJson(manifestFile);
    manifest.projects = manifest.projects && typeof manifest.projects === 'object' ? manifest.projects : {};
    manifest.projects[request.project] = {
      url: sourceUrl,
      path: target,
      commit,
      branch: currentBranch === 'HEAD' ? 'detached' : currentBranch,
      clone_time: timestamp,
      action: request.kind === 'github' ? 'imported-github' : 'imported-local',
      status: 'ok'
    };
    manifest.generated_at = timestamp;
    manifest.targets_dir = targetsRoot;
    await writeJson(manifestFile, manifest);
    onImported(request.project, metadata);

    check();
    progress('项目已登记，正在启动完整审计');
    const started = await run('bash', [
      path.join(repoRoot, 'run.sh'), target,
      '--project', request.project,
      '--run-dir', auditRunDir, ...getModelArgs()
    ], { cwd: repoRoot, timeout: 45000, onOutput: progress });
    if (started.code !== 0) throw processError(started, '项目已导入，但完整审计启动失败');

    return {
      ok: true,
      project: request.project,
      name: metadata.name,
      kind: request.kind,
      target,
      url: sourceUrl,
      commit,
      branch: currentBranch === 'HEAD' ? 'detached' : currentBranch,
      runId: auditRunId,
      runDir: auditRunDir,
      pipeline: 'full'
    };
    } catch (error) {
      if (createdTarget && !registered) await fsp.rm(target, { recursive: true, force: true });
      if (signal?.aborted) {
        if (auditRunDir && fs.existsSync(`${auditRunDir}.meta`)) {
          const stopped = await originalExecute('bash', [path.join(repoRoot, 'run.sh'), '--stop', auditRunDir], { cwd: repoRoot, timeout: 60000 });
          if (stopped.code !== 0) throw processError(stopped, '取消启动时停止审计失败');
        }
        if (registered) {
          for (const [file, previous] of [[projectsFile, oldProject], [manifestFile, oldManifest]]) {
            const payload = readJson(file);
            payload.projects ||= {};
            if (previous === undefined) delete payload.projects[request.project];
            else payload.projects[request.project] = previous;
            await writeJson(file, payload);
          }
          onImported(request.project, oldProject || null);
        }
        if (createdTarget) await fsp.rm(target, { recursive: true, force: true });
        throw new ProjectImportError('导入已取消', 499);
      }
      throw error;
    }
  }

  async function restartProject(value) {
    const project = normalizeProjectId(value);
    if (await isProjectLive(project)) throw new ProjectImportError('该项目正在审计中，请勿重复启动', 409);
    const registered = readJson(manifestFile).projects?.[project];
    if (!registered?.path) throw new ProjectImportError('没有找到项目源码登记，请重新导入', 404);
    const target = registered.path;
    if (!path.isAbsolute(target)) throw new ProjectImportError('项目源码路径无效，请重新导入');
    try {
      if (!(await fsp.stat(target)).isDirectory() || !(await fsp.readdir(target)).some(name => name !== '.git')) throw new Error('empty');
    } catch { throw new ProjectImportError('项目源码目录不存在或为空，请重新导入'); }
    const id = runId(now);
    const directory = path.join(repoRoot, 'runs', project, id);
    if (fs.existsSync(directory) || fs.existsSync(`${directory}.meta`)) throw new ProjectImportError('请稍后重试，避免重复启动', 409);
    const result = await execute('bash', [path.join(repoRoot, 'run.sh'), target, '--project', project, '--run-dir', directory, ...getModelArgs()], {cwd:repoRoot, timeout:45000});
    if (result.code !== 0) throw processError(result, '审计启动失败');
    return {ok:true,project,name:readJson(projectsFile).projects?.[project]?.name || project,runId:id,runDir:directory,pipeline:'full'};
  }
  return {
    restart(project) {
      const result = queue.then(() => restartProject(project));
      queue = result.catch(() => {});
      return result;
    },
    import(input, progress = () => {}, signal) {
      progress('请求已接收，正在等待导入队列');
      const result = queue.then(() => importAndStart(input, progress, signal));
      queue = result.catch(() => {});
      return result;
    }
  };
}

async function githubRequest(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'mygoldmine-branch-reader' },
      signal: controller.signal
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new ProjectImportError(`GitHub 请求失败（HTTP ${response.status}）`, 502);
    const links = {};
    for (const part of String(response.headers.get('link') || '').split(',')) {
      const match = part.match(/<([^>]+)>;\s*rel="([^"]+)"/);
      if (match) links[match[2]] = match[1];
    }
    return { payload, links };
  } catch (error) {
    if (error instanceof ProjectImportError) throw error;
    throw new ProjectImportError('GitHub 请求超时或网络不可用', 502);
  } finally {
    clearTimeout(timer);
  }
}

export function createGithubBranchLister({
  execute = executeProcess,
  request = githubRequest,
  now = () => Date.now(),
  ttlMs = 300000
} = {}) {
  const cache = new Map();
  const summaryCache = new Map();
  const inflight = new Map();
  const summaryInflight = new Map();

  function getDefaultBranch(repository) {
    const key = repository.source;
    const cached = summaryCache.get(key);
    if (cached && now() - cached.at < ttlMs) return Promise.resolve(cached.payload);
    if (summaryInflight.has(key)) return summaryInflight.get(key);
    const url = `https://api.github.com/repos/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}`;
    const pending = request(url).then((result) => {
      const defaultBranch = String(result.payload?.default_branch || '');
      summaryCache.set(key, { at: now(), payload: defaultBranch });
      return defaultBranch;
    }).finally(() => summaryInflight.delete(key));
    summaryInflight.set(key, pending);
    return pending;
  }

  async function load(repository, offset, limit) {
    const pageNumber = Math.floor(offset / limit) + 1;
    const branchUrl = `https://api.github.com/repos/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/branches?per_page=${limit}&page=${pageNumber}`;
    const [defaultBranch, firstResponse] = await Promise.all([getDefaultBranch(repository), request(branchUrl)]);
    if (!Array.isArray(firstResponse.payload)) throw new ProjectImportError('GitHub 分支响应格式无效', 502);
    let responses = [firstResponse];
    let items = [...firstResponse.payload];
    const skip = offset % limit;
    let pageRefs = items.slice(skip, skip + limit);
    if (pageRefs.length < limit && firstResponse.links.next) {
      const nextResponse = await request(firstResponse.links.next);
      if (!Array.isArray(nextResponse.payload)) throw new ProjectImportError('GitHub 分支响应格式无效', 502);
      responses.push(nextResponse);
      items = [...items, ...nextResponse.payload];
      pageRefs = items.slice(skip, skip + limit);
    }
    const lastResponse = responses.at(-1);
    const lastLink = lastResponse.links.last || firstResponse.links.last;
    let total;
    if (lastLink) {
      const lastPage = Number(new URL(lastLink).searchParams.get('page')) || pageNumber;
      if (lastPage === pageNumber && responses.length === 1) {
        total = (lastPage - 1) * limit + firstResponse.payload.length;
      } else {
        const last = await request(lastLink);
        if (!Array.isArray(last.payload)) throw new ProjectImportError('GitHub 分支响应格式无效', 502);
        total = (lastPage - 1) * limit + last.payload.length;
      }
    } else {
      total = (pageNumber - 1) * limit + firstResponse.payload.length;
    }
    if (offset === 0 && !pageRefs.length) throw new ProjectImportError('该仓库没有可读取的分支', 400);

    let branches = [];
    if (pageRefs.length) {
      const temporary = await fsp.mkdtemp(path.join(os.tmpdir(), 'mygoldmine-branches-'));
      const bare = path.join(temporary, 'repository.git');
      try {
        const initialized = await execute('git', ['init', '--bare', bare], { timeout: 30000 });
        if (initialized.code !== 0) throw processError(initialized, '准备分支读取目录失败');
        const refspecs = pageRefs.map((branch) => `refs/heads/${branch.name}:refs/heads/${branch.name}`);
        const fetched = await execute('git', [
          '-C', bare, 'fetch', '--depth', '1', '--filter=tree:0', '--no-tags', '--', repository.source, ...refspecs
        ], { timeout: 30000 });
        if (fetched.code !== 0) throw processError(fetched, '读取当前页分支提交失败');
        const refs = await execute('git', [
          '-C', bare, 'for-each-ref',
          '--format=%(refname:short)%09%(objectname)%09%(committerdate:iso8601-strict)',
          'refs/heads'
        ], { timeout: 30000 });
        if (refs.code !== 0) throw processError(refs, '解析当前页分支提交失败');
        branches = refs.stdout.split(/\r?\n/).filter(Boolean).map((line) => {
          const [name, commit, committedAt] = line.split('\t');
          return { name, commit, committedAt };
        }).filter((branch) => branch.name && branch.commit).sort((left, right) => {
          const timeDifference = (Date.parse(right.committedAt) || 0) - (Date.parse(left.committedAt) || 0);
          return timeDifference || left.name.localeCompare(right.name);
        });
      } finally {
        await fsp.rm(temporary, { recursive: true, force: true });
      }
    }
    const hasMore = offset + pageRefs.length < total;
    return {
      repository: repository.url,
      defaultBranch,
      latestBranch: branches[0]?.name || '',
      latestScope: 'page',
      branches: branches.map((branch) => ({
        ...branch,
        isDefault: branch.name === defaultBranch,
        isLatest: branch.name === branches[0]?.name
      })),
      offset,
      limit,
      total,
      hasMore,
      nextOffset: hasMore ? offset + pageRefs.length : null
    };
  }

  return {
    list(source, { offset: offsetValue = 0, limit: limitValue = 10 } = {}) {
      let repository;
      try {
        repository = githubSource(source);
      } catch (error) {
        return Promise.reject(error);
      }
      const parsedOffset = Number(offsetValue);
      const parsedLimit = Number(limitValue);
      const offset = Number.isFinite(parsedOffset) ? Math.max(0, Math.floor(parsedOffset)) : 0;
      const limit = Number.isFinite(parsedLimit) ? Math.min(50, Math.max(1, Math.floor(parsedLimit))) : 10;
      const key = `${repository.source}:${offset}:${limit}`;
      const cached = cache.get(key);
      if (cached && now() - cached.at < ttlMs) return Promise.resolve(cached.payload);
      if (inflight.has(key)) return inflight.get(key);
      const pending = load(repository, offset, limit).then((payload) => {
        cache.set(key, { at: now(), payload });
        return payload;
      }).finally(() => inflight.delete(key));
      inflight.set(key, pending);
      return pending;
    }
  };
}

export async function browseServerDirectory(requestedPath = '') {
  const requested = text(requestedPath, 1000) || os.homedir();
  if (!path.isAbsolute(requested)) throw new ProjectImportError('目录浏览需要绝对路径');
  let current;
  let entries;
  try {
    current = await fsp.realpath(requested);
    const stat = await fsp.stat(current);
    if (!stat.isDirectory()) throw new Error('not a directory');
    entries = await fsp.readdir(current, { withFileTypes: true });
  } catch {
    throw new ProjectImportError('目录不存在或不可读取');
  }
  const names = entries
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'))
    .map((entry) => entry.name)
    .sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  const visible = names.slice(0, 300);
  return {
    path: current,
    parent: path.dirname(current) === current ? '' : path.dirname(current),
    home: os.homedir(),
    directories: visible.map((name) => ({ name, path: path.join(current, name) })),
    hasMore: names.length > visible.length
  };
}

export function createGithubCommitLister({ request = githubRequest, now = () => Date.now(), ttlMs = 60000 } = {}) {
  const cache = new Map();
  const inflight = new Map();
  return { list(source, { page = 1, limit = 10 } = {}) {
    const repo = githubSource(source);
    page = Math.max(1, Math.floor(Number(page) || 1));
    limit = Math.min(30, Math.max(1, Math.floor(Number(limit) || 10)));
    const key = `${repo.source}:${page}:${limit}`;
    if (cache.has(key) && now() - cache.get(key).at < ttlMs) return Promise.resolve(cache.get(key).payload);
    if (inflight.has(key)) return inflight.get(key);
    const pending = request(`https://api.github.com/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.name)}/commits?per_page=${limit}&page=${page}`).then(({ payload, links }) => {
      if (!Array.isArray(payload)) throw new ProjectImportError('提交记录响应格式无效', 502);
      const result = { commits: payload.map(item => ({ sha: item.sha, message: item.commit?.message?.split('\n')[0] || '', committedAt: item.commit?.committer?.date || '', author: item.commit?.author?.name || '' })), page, hasMore: Boolean(links?.next) };
      cache.set(key, { at: now(), payload: result });
      return result;
    }).finally(() => inflight.delete(key));
    inflight.set(key, pending);
    return pending;
  }};
}
