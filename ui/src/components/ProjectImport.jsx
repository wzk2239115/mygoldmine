import { createPortal } from 'react-dom';
import { useEffect, useRef, useState } from 'react';
import { ArrowUp, ChevronRight, Search, FolderOpen, Github, Home, Info, Plus, RefreshCw, X } from 'lucide-react';
import { api } from '../api.js';
import { cx } from '../utils.js';

export default function ProjectImport({ onImported }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState('github');
  const [source, setSource] = useState('');
  const [project, setProject] = useState('');
  const [commit, setCommit] = useState('');
  const [commits, setCommits] = useState([]);
  const [commitsLoading, setCommitsLoading] = useState(false);
  const [commitsLoadingMore, setCommitsLoadingMore] = useState(false);
  const [commitsError, setCommitsError] = useState('');
  const [commitsHasMore, setCommitsHasMore] = useState(false);
  const [commitReload, setCommitReload] = useState(0);
  const sourceByKind = useRef({ github: '', local: '' });
  const [pickerQuery, setPickerQuery] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerPath, setPickerPath] = useState('');
  const [pickerParent, setPickerParent] = useState('');
  const [pickerEntries, setPickerEntries] = useState([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState('');
  const [pickerHasMore, setPickerHasMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [importInfo, setImportInfo] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const infoEnd = useRef(null);
  useEffect(() => {
    if (!busy) return undefined;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);
  useEffect(() => {
    const log = infoEnd.current?.parentElement;
    if (log) log.scrollTop = log.scrollHeight;
  }, [importInfo]);
  const importController = useRef(null);
  const commitRequest = useRef(0);
  const directoryRequest = useRef(0);

  useEffect(() => {
    const requestId = ++commitRequest.current;
    setCommits([]);
    setCommit('');
    setCommitsHasMore(false);
    setCommitsError('');
    setCommitsLoading(false);
    setCommitsLoadingMore(false);
    const validGithub = /^https:\/\/github\.com\/[^/\s]+\/[^/\s]+(?:\.git)?\/?$/.test(source.trim());
    if (!open || kind !== 'github' || !validGithub) return undefined;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setCommitsLoading(true);
      try {
        const payload = await api.githubCommits(source.trim(), { page: 1, limit: 10 });
        if (cancelled || requestId !== commitRequest.current) return;
        setCommits(payload.commits || []);
            setCommitsHasMore(Boolean(payload.hasMore));
        setCommit(payload.commits?.[0]?.sha || '');
      } catch (loadError) {
        if (!cancelled && requestId === commitRequest.current) setCommitsError(loadError.message);
      } finally {
        if (!cancelled && requestId === commitRequest.current) setCommitsLoading(false);
      }
    }, commitReload ? 0 : 150);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, kind, source, commitReload]);

  const loadMoreCommits = async () => {
    const requestId = commitRequest.current;
    const offset = commits.length;
    setCommitsLoadingMore(true);
    setCommitsError('');
    try {
      const payload = await api.githubCommits(source.trim(), { page: Math.floor(offset / 10) + 1, limit: 10 });
      if (requestId !== commitRequest.current) return;
      setCommits((current) => {
        const existing = new Set(current.map((item) => item.sha));
        return [...current, ...(payload.commits || []).filter((item) => !existing.has(item.sha))];
      });
        setCommitsHasMore(Boolean(payload.hasMore));
    } catch (loadError) {
      if (requestId === commitRequest.current) setCommitsError(loadError.message);
    } finally {
      if (requestId === commitRequest.current) setCommitsLoadingMore(false);
    }
  };

  const loadDirectory = async (directory = '') => {
    const requestId = ++directoryRequest.current;
    setPickerOpen(true);
    setPickerQuery('');
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

  const changeKind = (nextKind) => {
    if (nextKind === kind) return;
    sourceByKind.current[kind] = source;
    const nextSource = sourceByKind.current[nextKind];
    setKind(nextKind);
    setSource(nextSource);
    setError('');
    setImportInfo([]);
    directoryRequest.current += 1;
    setPickerOpen(false);
    if (nextKind === 'local') loadDirectory(nextSource.startsWith('/') ? nextSource : '');
  };
  const visibleDirectories = pickerEntries.filter((entry) => entry.name.toLocaleLowerCase().includes(pickerQuery.trim().toLocaleLowerCase()));

  const close = () => {
    if (busy) { importController.current?.abort(); return; }
    directoryRequest.current += 1;
    setPickerOpen(false);
    setOpen(false);
    setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    importController.current = new AbortController();
    setBusy(true);
    setElapsed(0);
    setImportInfo([]);
    setError('');
    try {
      const result = await api.importWithProgress({ kind, source, project, commit: kind === 'github' ? commit : '' }, (item) => {
        setImportInfo((current) => [...current, item].slice(-150));
      }, importController.current.signal);
      setOpen(false);
      setSource('');
      setProject('');
      setCommit('');
      await onImported(result);
    } catch (submitError) {
      setError(importController.current?.signal.aborted ? '已请求取消导入，服务器正在停止任务并清理本次新建内容。' : submitError.message);
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
      {open ? createPortal(
        <>
          <button type="button" className="project-import-backdrop" aria-label="关闭项目导入" onClick={close} />
          <section className="project-import-dialog" role="dialog" aria-modal="true" aria-labelledby="project-import-title">
            <header className="project-import-head">
              <div>
                <h2 id="project-import-title">导入审计项目</h2>
                <p>导入后立即启动环境构建、安全审计、蓝队验证、红队验证和经验学习。</p>
              </div>
              <button type="button" className="icon-button is-small" aria-label="关闭项目导入" onClick={close}>
                <X size={16} aria-hidden="true" />
              </button>
            </header>
            <form onSubmit={submit}>
              <div className="project-import-body">
              <div className="project-import-types" role="group" aria-label="项目来源">
                <button type="button" className={cx(kind === 'github' && 'is-active')} aria-pressed={kind === 'github'} disabled={busy} onClick={() => changeKind('github')}>
                  <Github size={16} aria-hidden="true" />GitHub 仓库
                </button>
                <button type="button" className={cx(kind === 'local' && 'is-active')} aria-pressed={kind === 'local'} disabled={busy} onClick={() => changeKind('local')}>
                  <FolderOpen size={16} aria-hidden="true" />本地目录
                </button>
              </div>
              <div className="project-import-field">
                <label htmlFor="project-import-source">{kind === 'github' ? '公开仓库地址' : '服务器上的绝对目录路径'}</label>
                <div className="project-import-source-row">
                  <input
                    id="project-import-source"
                    required
                    pattern={kind === 'local' ? '/.*' : undefined}
                    title={kind === 'local' ? '请输入服务器上的绝对路径，例如 /home/wzk/project' : undefined}
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
              {kind === 'local' ? <p className="directory-server-hint">浏览的是服务器上的目录，可直接填写路径或在下方选择。</p> : null}
              {kind === 'local' && pickerOpen ? (
                <section className="directory-browser" aria-label="服务器目录选择器">
                  <header className="directory-browser-head">
                    <strong>选择服务器目录</strong>
                    <button type="button" className="icon-button is-small" aria-label="关闭目录选择器" onClick={() => { directoryRequest.current += 1; setPickerOpen(false); }}>
                      <X size={14} aria-hidden="true" />
                    </button>
                  </header>
                  <nav className="directory-breadcrumbs" aria-label="当前目录路径" title={pickerPath}>
                    <button type="button" disabled={pickerLoading} onClick={() => loadDirectory('/')}>/</button>
                    {pickerPath.split('/').filter(Boolean).map((part, index, parts) => <span key={index}>
                      <ChevronRight size={11} aria-hidden="true" />
                      <button type="button" disabled={pickerLoading} onClick={() => loadDirectory('/' + parts.slice(0, index + 1).join('/'))}>{part}</button>
                    </span>)}
                  </nav>
                  <div className="directory-browser-nav">
                    <button type="button" className="button is-small" disabled={pickerLoading || !pickerParent} onClick={() => loadDirectory(pickerParent)}>
                      <ArrowUp size={13} aria-hidden="true" />上一级
                    </button>
                    <button type="button" className="button is-small" disabled={pickerLoading} onClick={() => loadDirectory('')}>
                      <Home size={13} aria-hidden="true" />主目录
                    </button>
                  </div>
                  <label className="directory-search"><Search size={14} aria-hidden="true" /><input aria-label="筛选当前目录中的子目录" placeholder="筛选当前目录中的子目录…" value={pickerQuery} disabled={pickerLoading} onChange={(event) => setPickerQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') event.preventDefault(); }} /></label>
                  <div className="directory-browser-list" aria-busy={pickerLoading}>
                    {pickerLoading ? <p className="directory-browser-empty">正在读取目录…</p> : null}
                    {pickerError ? <p className="directory-browser-error" role="alert">{pickerError}</p> : null}
                    {!pickerLoading && !pickerError && !visibleDirectories.length ? <p className="directory-browser-empty">{pickerQuery ? '没有匹配的子目录，请调整筛选。' : '没有可见子目录，可以选择当前目录。'}</p> : null}
                    {!pickerLoading && !pickerError ? visibleDirectories.map((entry) => (
                      <button type="button" className="directory-browser-entry" title={entry.path} key={entry.path} onClick={() => loadDirectory(entry.path)}>
                        <FolderOpen size={15} aria-hidden="true" /><span>{entry.name}</span><ChevronRight size={13} aria-hidden="true" />
                      </button>
                    )) : null}
                  </div>
                  {pickerHasMore ? <p className="directory-browser-more">仅显示前 300 个子目录，其他目录可在路径输入框中直接填写。</p> : null}
                  <footer className="directory-browser-actions">
                    <span className="directory-selection-path" title={pickerPath}>{pickerPath || '尚未选择目录'}</span>
                    <button type="button" className="button is-primary is-small" disabled={pickerLoading || !pickerPath} onClick={() => { setSource(pickerPath); setPickerOpen(false); }}>
                      使用此目录
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
                  <label htmlFor="project-import-commit">提交版本</label>
                  <div className="project-import-branch-row">
                    <select id="project-import-commit" aria-label="提交版本" disabled={busy || commitsLoading || !commits.length} value={commit} onChange={(event) => setCommit(event.target.value)}>
                      {!commits.length ? <option value="">{commitsLoading ? '正在读取提交版本…' : '输入仓库地址后读取提交版本'}</option> : null}
                      {commits.map((item, index) => <option key={item.sha} value={item.sha}>
                        {item.sha.slice(0, 8)} · {item.committedAt ? new Date(item.committedAt).toLocaleString('zh-CN', { hour12: false }) : ''} · {item.message}{index === 0 ? '（最新）' : ''}
                      </option>)}
                    </select>
                    <button type="button" className="icon-button is-small" title="刷新提交版本" aria-label="刷新提交版本" disabled={busy || commitsLoading || !source.trim()} onClick={() => setCommitReload((value) => value + 1)}>
                      <RefreshCw size={14} className={cx(commitsLoading && 'is-spinning')} aria-hidden="true" />
                    </button>
                  </div>
                  {commits.length ? <div className="project-branch-pagination">
                    <small>已显示 {commits.length} 条提交，按提交历史分页；默认选择最新版本。</small>
                    {commitsHasMore ? <button type="button" className="button is-small" disabled={busy || commitsLoadingMore} onClick={loadMoreCommits}>{commitsLoadingMore ? '正在加载…' : '加载更多提交'}</button> : null}
                  </div> : null}
                  {commitsError ? <small className="project-import-branch-error" role="alert">读取提交版本失败：{commitsError}，请重试。</small> : null}
                </div>
              ) : null}
              <p className="project-import-note">
                {kind === 'github'
                  ? '仅下载所选公开提交版本，不收集访问令牌。已有完整源码不会被覆盖，未完成下载会备份后重试。'
                  : '直接审计服务器当前目录，不复制源码，也不切换分支。'}
              </p>
              {error ? <div className="project-import-error" role="alert">{error}</div> : null}

              {busy || importInfo.length ? (
                <section className="project-import-progress" aria-label="导入进度" aria-busy={busy}>
                  <header><Info size={15} aria-hidden="true" /><strong>{error ? '导入未完成' : busy ? '正在导入' : '导入状态'}</strong><span>已用时 {elapsed} 秒</span></header>
                  <div className="project-import-log" role="log" aria-live="polite" aria-relevant="additions">
                    {importInfo.map((item, index) => <div key={index}><time>{new Date(item.at).toLocaleTimeString('zh-CN', { hour12: false })}</time><pre>{item.message.replace(/\x1b\[[0-9;]*m/g, '').replace(/\r/g, '\n')}</pre></div>)}
                    {error ? <p role="alert">{error}</p> : null}
                    <div ref={infoEnd} />
                  </div>
                </section>
              ) : null}
              </div>
              <footer className="project-import-actions">
                <button type="button" className="button" onClick={close}>取消</button>
                <button type="submit" className="button is-primary" disabled={busy || pickerLoading || (kind === 'github' ? (commitsLoading || !commit) : !source.startsWith('/'))} aria-busy={busy}>
                  <RefreshCw size={14} className={cx(busy && 'is-spinning')} aria-hidden="true" />
                  {busy ? '正在导入并启动…' : '导入并启动完整审计'}
                </button>
              </footer>
            </form>
          </section>
        </>, document.body
      ) : null}
    </>
  );
}
