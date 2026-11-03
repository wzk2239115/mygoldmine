import { useEffect, useRef, useState } from 'react';
import { ArrowUp, FolderOpen, Github, Home, Plus, RefreshCw, X } from 'lucide-react';
import { api } from '../api.js';
import { cx } from '../utils.js';

export default function ProjectImport({ onImported }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState('github');
  const [source, setSource] = useState('');
  const [project, setProject] = useState('');
  const [branch, setBranch] = useState('');
  const [branches, setBranches] = useState([]);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [branchesLoadingMore, setBranchesLoadingMore] = useState(false);
  const [branchesError, setBranchesError] = useState('');
  const [branchTotal, setBranchTotal] = useState(0);
  const [branchesHasMore, setBranchesHasMore] = useState(false);
  const [branchReload, setBranchReload] = useState(0);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerPath, setPickerPath] = useState('');
  const [pickerParent, setPickerParent] = useState('');
  const [pickerEntries, setPickerEntries] = useState([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState('');
  const [pickerHasMore, setPickerHasMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const branchRequest = useRef(0);
  const directoryRequest = useRef(0);

  useEffect(() => {
    const requestId = ++branchRequest.current;
    setBranches([]);
    setBranch('');
    setBranchTotal(0);
    setBranchesHasMore(false);
    setBranchesError('');
    setBranchesLoading(false);
    setBranchesLoadingMore(false);
    const validGithub = /^https:\/\/github\.com\/[^/\s]+\/[^/\s]+(?:\.git)?\/?$/.test(source.trim());
    if (!open || kind !== 'github' || !validGithub) return undefined;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setBranchesLoading(true);
      try {
        const payload = await api.githubBranches(source.trim(), { offset: 0, limit: 10 });
        if (cancelled || requestId !== branchRequest.current) return;
        setBranches(payload.branches || []);
        setBranchTotal(payload.total || 0);
        setBranchesHasMore(Boolean(payload.hasMore));
        setBranch(payload.defaultBranch || payload.latestBranch || '');
      } catch (loadError) {
        if (!cancelled && requestId === branchRequest.current) setBranchesError(loadError.message);
      } finally {
        if (!cancelled && requestId === branchRequest.current) setBranchesLoading(false);
      }
    }, branchReload ? 0 : 700);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, kind, source, branchReload]);

  const loadMoreBranches = async () => {
    const requestId = branchRequest.current;
    const offset = branches.length;
    setBranchesLoadingMore(true);
    setBranchesError('');
    try {
      const payload = await api.githubBranches(source.trim(), { offset, limit: 10 });
      if (requestId !== branchRequest.current) return;
      setBranches((current) => {
        const existing = new Set(current.map((item) => item.name));
        return [...current, ...(payload.branches || []).filter((item) => !existing.has(item.name))];
      });
      setBranchTotal(payload.total || 0);
      setBranchesHasMore(Boolean(payload.hasMore));
    } catch (loadError) {
      if (requestId === branchRequest.current) setBranchesError(loadError.message);
    } finally {
      if (requestId === branchRequest.current) setBranchesLoadingMore(false);
    }
  };

  const loadDirectory = async (directory = '') => {
    const requestId = ++directoryRequest.current;
    setPickerOpen(true);
    setPickerLoading(true);
    setPickerError('');
    setPickerEntries([]);
    try {
      const payload = await api.serverDirectories(directory);
      if (requestId !== directoryRequest.current) return;
      setPickerPath(payload.path);
      setPickerParent(payload.parent || '');
      setPickerEntries(payload.directories || []);
      setPickerHasMore(Boolean(payload.hasMore));
    } catch (loadError) {
      if (requestId === directoryRequest.current) setPickerError(loadError.message);
    } finally {
      if (requestId === directoryRequest.current) setPickerLoading(false);
    }
  };

  const close = () => {
    if (busy) return;
    directoryRequest.current += 1;
    setPickerOpen(false);
    setOpen(false);
    setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api.importProject({ kind, source, project, branch });
      setOpen(false);
      setSource('');
      setProject('');
      setBranch('');
      await onImported(result);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="icon-button is-small project-import-trigger"
        title="导入项目并启动完整审计"
        aria-label="导入项目并启动完整审计"
        onClick={() => setOpen(true)}
      >
        <Plus size={15} aria-hidden="true" />
      </button>
      {open ? (
        <>
          <button type="button" className="project-import-backdrop" aria-label="关闭项目导入" onClick={close} />
          <section className="project-import-dialog" role="dialog" aria-modal="true" aria-labelledby="project-import-title">
            <header className="project-import-head">
              <div>
                <h2 id="project-import-title">导入审计项目</h2>
                <p>导入后立即启动环境构建、挖掘、蓝队验证、红队验证和挖掘修复学习。</p>
              </div>
              <button type="button" className="icon-button is-small" aria-label="关闭项目导入" disabled={busy} onClick={close}>
                <X size={16} aria-hidden="true" />
              </button>
            </header>
            <form onSubmit={submit}>
              <div className="project-import-types" role="group" aria-label="项目来源">
                <button type="button" className={cx(kind === 'github' && 'is-active')} aria-pressed={kind === 'github'} disabled={busy} onClick={() => { setKind('github'); setError(''); }}>
                  <Github size={16} aria-hidden="true" />GitHub 仓库
                </button>
                <button type="button" className={cx(kind === 'local' && 'is-active')} aria-pressed={kind === 'local'} disabled={busy} onClick={() => { setKind('local'); setError(''); }}>
                  <FolderOpen size={16} aria-hidden="true" />本地目录
                </button>
              </div>
              <div className="project-import-field">
                <label htmlFor="project-import-source">{kind === 'github' ? '公开仓库地址' : '服务器上的绝对目录路径'}</label>
                <div className="project-import-source-row">
                  <input
                    id="project-import-source"
                    required
                    autoFocus
                    disabled={busy}
                    value={source}
                    onChange={(event) => setSource(event.target.value)}
                    placeholder={kind === 'github' ? 'https://github.com/所有者/仓库' : '/home/user/project'}
                    aria-label={kind === 'github' ? '公开仓库地址' : '本地目录路径'}
                  />
                  {kind === 'local' ? (
                    <button type="button" className="button is-small project-directory-picker-trigger" disabled={busy} onClick={() => loadDirectory(source.startsWith('/') ? source : '')}>
                      <FolderOpen size={14} aria-hidden="true" />选择目录
                    </button>
                  ) : null}
                </div>
              </div>
              {kind === 'local' && pickerOpen ? (
                <section className="directory-browser" aria-label="服务器目录选择器">
                  <header className="directory-browser-head">
                    <strong>选择服务器目录</strong>
                    <button type="button" className="icon-button is-small" aria-label="关闭目录选择器" onClick={() => { directoryRequest.current += 1; setPickerOpen(false); }}>
                      <X size={14} aria-hidden="true" />
                    </button>
                  </header>
                  <div className="directory-browser-current" title={pickerPath}>{pickerPath || '正在读取…'}</div>
                  <div className="directory-browser-nav">
                    <button type="button" className="button is-small" disabled={pickerLoading || !pickerParent} onClick={() => loadDirectory(pickerParent)}>
                      <ArrowUp size={13} aria-hidden="true" />上一级
                    </button>
                    <button type="button" className="button is-small" disabled={pickerLoading} onClick={() => loadDirectory('')}>
                      <Home size={13} aria-hidden="true" />主目录
                    </button>
                  </div>
                  <div className="directory-browser-list" aria-busy={pickerLoading}>
                    {pickerLoading ? <p className="directory-browser-empty">正在读取目录…</p> : null}
                    {pickerError ? <p className="directory-browser-error" role="alert">{pickerError}</p> : null}
                    {!pickerLoading && !pickerError && !pickerEntries.length ? <p className="directory-browser-empty">当前目录没有可见子目录，可以直接选择当前目录。</p> : null}
                    {!pickerLoading && !pickerError ? pickerEntries.map((entry) => (
                      <button type="button" className="directory-browser-entry" key={entry.path} onClick={() => loadDirectory(entry.path)}>
                        <FolderOpen size={15} aria-hidden="true" /><span>{entry.name}</span>
                      </button>
                    )) : null}
                  </div>
                  {pickerHasMore ? <p className="directory-browser-more">仅显示前 300 个子目录，其他目录可在路径输入框中直接填写。</p> : null}
                  <footer className="directory-browser-actions">
                    <button type="button" className="button is-primary is-small" disabled={pickerLoading || !pickerPath} onClick={() => { setSource(pickerPath); setPickerOpen(false); }}>
                      选择当前目录
                    </button>
                  </footer>
                </section>
              ) : null}
              <label className="project-import-field">
                <span>项目标识（可选）</span>
                <input
                  disabled={busy}
                  value={project}
                  onChange={(event) => setProject(event.target.value)}
                  placeholder="默认使用目录或仓库名称"
                  aria-label="项目标识"
                />
                <small>小写字母、数字、点、下划线和连字符；用于隔离报告与仓库专属经验。</small>
              </label>
              {kind === 'github' ? (
                <div className="project-import-field">
                  <label htmlFor="project-import-branch">分支</label>
                  <div className="project-import-branch-row">
                    {branches.length ? (
                      <select id="project-import-branch" aria-label="GitHub 分支" disabled={busy} value={branch} onChange={(event) => setBranch(event.target.value)}>
                        {branch && !branches.some((item) => item.name === branch) ? <option value={branch}>{branch}（默认）</option> : null}
                        {branches.map((item) => {
                          const labels = [];
                          if (item.isDefault) labels.push('默认');
                          if (item.isLatest) labels.push('本页最新');
                          return <option key={item.name} value={item.name}>{item.name}{labels.length ? `（${labels.join('、')}）` : ''}</option>;
                        })}
                      </select>
                    ) : (
                      <input
                        id="project-import-branch"
                        disabled={busy || branchesLoading}
                        value={branch}
                        onChange={(event) => setBranch(event.target.value)}
                        placeholder={branchesLoading ? '正在读取远程分支…' : '使用默认分支，也可以手动填写'}
                        aria-label="GitHub 分支"
                      />
                    )}
                    <button
                      type="button"
                      className="icon-button is-small"
                      title="重新读取远程分支"
                      aria-label="重新读取远程分支"
                      disabled={busy || branchesLoading || !source.trim()}
                      onClick={() => setBranchReload((value) => value + 1)}
                    >
                      <RefreshCw size={14} className={cx(branchesLoading && 'is-spinning')} aria-hidden="true" />
                    </button>
                  </div>
                  {branches.length ? (
                    <div className="project-branch-pagination">
                      <small>已显示 {branches.length} / {branchTotal} 条，每页按提交时间排序。</small>
                      {branchesHasMore ? (
                        <button type="button" className="button is-small" disabled={busy || branchesLoadingMore} onClick={loadMoreBranches}>
                          <RefreshCw size={12} className={cx(branchesLoadingMore && 'is-spinning')} aria-hidden="true" />
                          {branchesLoadingMore ? '正在加载…' : `加载更多（第 ${branches.length + 1}–${Math.min(branches.length + 10, branchTotal)} 条）`}
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  {branchesError ? <small className="project-import-branch-error" role="alert">自动读取失败：{branchesError}；{branches.length ? '可重试' : '可手动填写分支'}。</small> : null}
                </div>
              ) : null}
              <p className="project-import-note">
                {kind === 'github'
                  ? '仅克隆公开 GitHub 仓库，不收集访问令牌。已有目录不会被强制更新。'
                  : '直接审计服务器当前目录，不复制源码，也不切换分支。'}
              </p>
              {error ? <div className="project-import-error" role="alert">{error}</div> : null}
              <footer className="project-import-actions">
                <button type="button" className="button" disabled={busy} onClick={close}>取消</button>
                <button type="submit" className="button is-primary" disabled={busy} aria-busy={busy}>
                  <RefreshCw size={14} className={cx(busy && 'is-spinning')} aria-hidden="true" />
                  {busy ? '正在导入并启动…' : '导入并启动完整审计'}
                </button>
              </footer>
            </form>
          </section>
        </>
      ) : null}
    </>
  );
}
