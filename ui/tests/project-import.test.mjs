import test from 'node:test';
import assert from 'node:assert/strict';
import fsp from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  browseServerDirectory,
  createGithubBranchLister,
  createProjectImporter,
  normalizeProjectId,
  parseProjectImport
} from '../server/project-import.mjs';

async function fixture() {
  const repoRoot = await fsp.mkdtemp(path.join(os.tmpdir(), 'mygoldmine-import-'));
  const source = path.join(repoRoot, 'local-source');
  await fsp.mkdir(source);
  await fsp.mkdir(path.join(repoRoot, 'ui', 'data'), { recursive: true });
  await fsp.writeFile(path.join(repoRoot, 'ui', 'data', 'projects.json'), '{"schema_version":1,"projects":{}}\n');
  return { repoRoot, source };
}

test('项目标识和公开 GitHub 地址经过严格校验', () => {
  assert.equal(normalizeProjectId('Repo-1'), 'repo-1');
  assert.throws(() => normalizeProjectId('../repo'), /项目标识/);
  assert.throws(() => parseProjectImport({ kind: 'github', source: 'https://example.com/a/b' }), /仅支持/);
  assert.throws(() => parseProjectImport({ kind: 'github', source: 'https://token@github.com/a/b' }), /仅支持/);
  assert.deepEqual(parseProjectImport({ kind: 'github', source: 'https://github.com/acme/repo' }), {
    kind: 'github', project: 'repo', branch: '', localPath: '',
    source: 'https://github.com/acme/repo.git', url: 'https://github.com/acme/repo', owner: 'acme', name: 'repo'
  });
});

test('本地导入登记当前目录并调用完整审计主流程', async () => {
  const { repoRoot, source } = await fixture();
  const calls = [];
  const execute = async (command, args) => {
    calls.push([command, args]);
    if (args.includes('origin')) return { code: 0, stdout: 'https://token@github.com/acme/local.git\n', stderr: '' };
    if (args.includes('HEAD') && args.includes('--abbrev-ref')) return { code: 0, stdout: 'main\n', stderr: '' };
    if (args.includes('HEAD')) return { code: 0, stdout: 'abc123\n', stderr: '' };
    return { code: 0, stdout: '', stderr: '' };
  };
  const importer = createProjectImporter({
    repoRoot,
    execute,
    now: () => new Date('2026-11-03T04:05:06.000Z')
  });
  const result = await importer.import({ kind: 'local', source, project: 'local-project' });
  assert.equal(result.pipeline, 'full');
  assert.equal(result.runId, '20261103T040506Z');
  assert.equal(result.url, 'https://github.com/acme/local.git');
  const start = calls.find(([command]) => command === 'bash');
  assert.deepEqual(start[1], [
    path.join(repoRoot, 'run.sh'), source,
    '--project', 'local-project', '--run-dir', result.runDir
  ]);
  assert.equal(start[1].some((arg) => arg.startsWith('--skip-')), false);
  const manifest = JSON.parse(await fsp.readFile(path.join(repoRoot, 'targets', 'manifest.json'), 'utf8'));
  assert.equal(manifest.projects['local-project'].action, 'imported-local');
  assert.equal(manifest.projects['local-project'].commit, 'abc123');
  await fsp.rm(repoRoot, { recursive: true, force: true });
});

test('GitHub 导入浅克隆指定分支并启动完整审计', async () => {
  const { repoRoot } = await fixture();
  const calls = [];
  const execute = async (command, args) => {
    calls.push([command, args]);
    if (args[0] === 'clone') return { code: 0, stdout: '', stderr: '' };
    if (args.includes('HEAD') && args.includes('--abbrev-ref')) return { code: 0, stdout: 'release\n', stderr: '' };
    if (args.includes('HEAD')) return { code: 0, stdout: 'def456\n', stderr: '' };
    return { code: 0, stdout: '', stderr: '' };
  };
  const importer = createProjectImporter({ repoRoot, execute });
  const result = await importer.import({
    kind: 'github', source: 'https://github.com/acme/repo', project: 'repo-release', branch: 'release'
  });
  const clone = calls.find(([, args]) => args[0] === 'clone');
  assert.deepEqual(clone[1], [
    'clone', '--depth', '1', '--single-branch', '--branch', 'release', '--',
    'https://github.com/acme/repo.git', path.join(repoRoot, 'targets', 'repo-release')
  ]);
  assert.equal(result.branch, 'release');
  assert.equal(result.commit, 'def456');
  assert.equal(calls.some(([command]) => command === 'bash'), true);
  await fsp.rm(repoRoot, { recursive: true, force: true });
});

test('已有实时审计和启动失败不会返回成功', async () => {
  const { repoRoot, source } = await fixture();
  const running = createProjectImporter({ repoRoot, isProjectLive: () => true });
  await assert.rejects(running.import({ kind: 'local', source }), /已有正在运行的审计/);

  const failed = createProjectImporter({
    repoRoot,
    execute: async (command, args) => command === 'bash'
      ? { code: 1, stdout: '', stderr: 'docker unavailable' }
      : { code: args.includes('origin') ? 1 : 0, stdout: args.includes('HEAD') ? 'main\n' : '', stderr: '' }
  });
  await assert.rejects(failed.import({ kind: 'local', source }), /完整审计启动失败/);
  await fsp.rm(repoRoot, { recursive: true, force: true });
});

test('当前页分支按最新提交排序并分别标记默认和本页最新分支', async () => {
  let branchPages = 0;
  const request = async (url) => {
    if (!url.includes('/branches?')) return { payload: { default_branch: 'main' }, links: {} };
    branchPages += 1;
    return {
      payload: [{ name: 'main' }, { name: 'release' }, { name: 'feature' }],
      links: {}
    };
  };
  const execute = async (command, args) => {
    if (args.includes('fetch')) {
      assert.equal(args.includes('--filter=tree:0'), true);
      assert.equal(args.slice(args.indexOf('--') + 2).length, 3);
    }
    if (args.includes('for-each-ref')) {
      return {
        code: 0,
        stdout: 'main\t111\t2026-10-01T08:00:00+00:00\nrelease\t222\t2026-11-03T08:00:00+00:00\nfeature\t333\t2026-10-20T08:00:00+00:00\n',
        stderr: ''
      };
    }
    return { code: 0, stdout: '', stderr: '' };
  };
  const lister = createGithubBranchLister({ execute, request });
  const result = await lister.list('https://github.com/acme/repo');
  assert.equal(result.defaultBranch, 'main');
  assert.equal(result.latestBranch, 'release');
  assert.equal(result.latestScope, 'page');
  assert.deepEqual(result.branches.map((branch) => branch.name), ['release', 'feature', 'main']);
  assert.equal(result.branches[0].isLatest, true);
  assert.equal(result.branches[2].isDefault, true);
  await lister.list('https://github.com/acme/repo');
  assert.equal(branchPages, 1);
});

test('分支查询拒绝非 GitHub 地址', async () => {
  const lister = createGithubBranchLister({ execute: async () => ({ code: 0, stdout: '', stderr: '' }) });
  await assert.rejects(lister.list('https://example.com/acme/repo'), /仅支持/);
});

test('每页只读取 10 个分支提交且并发分页共享一次分支列表', async () => {
  let defaultReads = 0;
  let fetches = 0;
  let fetchedNames = [];
  const commitData = Array.from({ length: 25 }, (_, index) => {
    const number = index + 1;
    const name = `b${String(number).padStart(2, '0')}`;
    return { name, commit: String(number), date: `2026-11-${String(number).padStart(2, '0')}T08:00:00+00:00` };
  });
  const request = async (url) => {
    if (!url.includes('/branches?')) {
      defaultReads += 1;
      return { payload: { default_branch: 'b01' }, links: {} };
    }
    const parsed = new URL(url);
    const page = Number(parsed.searchParams.get('page'));
    const limit = Number(parsed.searchParams.get('per_page'));
    const payload = commitData.slice((page - 1) * limit, page * limit).map((item) => ({ name: item.name }));
    const links = {};
    if (page * limit < commitData.length) {
      const next = new URL(parsed);
      next.searchParams.set('page', String(page + 1));
      links.next = next.toString();
    }
    if (commitData.length > limit) {
      const last = new URL(parsed);
      last.searchParams.set('page', String(Math.ceil(commitData.length / limit)));
      links.last = last.toString();
    }
    return { payload, links };
  };
  const execute = async (command, args) => {
    if (args.includes('fetch')) {
      fetches += 1;
      assert.equal(args.includes('--filter=tree:0'), true);
      fetchedNames = args.slice(args.indexOf('--') + 2).map((refspec) => refspec.split(':')[0].replace('refs/heads/', ''));
      assert.equal(fetchedNames.length <= 10, true);
      return { code: 0, stdout: '', stderr: '' };
    }
    if (args.includes('for-each-ref')) {
      const stdout = commitData.filter((item) => fetchedNames.includes(item.name))
        .map((item) => `${item.name}\t${item.commit}\t${item.date}`).join('\n');
      return { code: 0, stdout: `${stdout}\n`, stderr: '' };
    }
    return { code: 0, stdout: '', stderr: '' };
  };
  const lister = createGithubBranchLister({ execute, request });
  const [first, second] = await Promise.all([
    lister.list('https://github.com/acme/repo', { offset: 0, limit: 10 }),
    lister.list('https://github.com/acme/repo', { offset: 10, limit: 10 })
  ]);
  assert.equal(first.branches.length, 10);
  assert.equal(first.branches[0].name, 'b10');
  assert.equal(first.branches[9].name, 'b01');
  assert.equal(first.total, 25);
  assert.equal(first.hasMore, true);
  assert.equal(first.nextOffset, 10);
  assert.equal(second.branches[0].name, 'b20');
  assert.equal(second.branches[9].name, 'b11');
  const third = await lister.list('https://github.com/acme/repo', { offset: 20, limit: 10 });
  assert.equal(third.branches.length, 5);
  assert.equal(third.branches[0].name, 'b25');
  assert.equal(third.hasMore, false);
  assert.equal(third.nextOffset, null);
  assert.equal(defaultReads, 1);
  assert.equal(fetches, 3);
});

test('服务器目录浏览只列出可见子目录并支持返回上一级', async () => {
  const { repoRoot } = await fixture();
  await fsp.mkdir(path.join(repoRoot, 'beta'));
  await fsp.mkdir(path.join(repoRoot, 'alpha'));
  await fsp.mkdir(path.join(repoRoot, '.hidden'));
  await fsp.writeFile(path.join(repoRoot, 'README.md'), 'test');
  const result = await browseServerDirectory(repoRoot);
  assert.equal(result.path, repoRoot);
  assert.equal(result.parent, path.dirname(repoRoot));
  assert.deepEqual(result.directories.map((entry) => entry.name), ['alpha', 'beta', 'local-source', 'ui']);
  await assert.rejects(browseServerDirectory('relative/path'), /绝对路径/);
  await fsp.rm(repoRoot, { recursive: true, force: true });
});
