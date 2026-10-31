import { useEffect, useState } from 'react';
import { Activity, GitCommitHorizontal, Radar, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '../api.js';
import { cx } from '../utils.js';

const VERDICTS = ['critical', 'high', 'review', 'low'];

function shortSha(sha) {
  return (sha || '').slice(0, 12);
}

export default function WatchView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setData(await api.watch());
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const counts = data?.counts || {};
  const repos = data?.repos || [];
  const events = data?.brief?.top || [];

  return (
    <section className="arch-view watch-view">
      <header className="arch-head">
        <div>
          <span className="arch-kicker">continuous provenance</span>
          <h2>自动狩猎</h2>
          <p>连接仓库后建立基线，按每次提交审查变化；高风险更新进入待办队列，不直接下结论。</p>
        </div>
        <button type="button" className="button is-small" onClick={load} disabled={loading}>
          <RefreshCw size={14} className={cx(loading && 'is-spinning')} aria-hidden="true" />
          刷新
        </button>
      </header>

      <div className="arch-counts">
        {VERDICTS.map((verdict) => (
          <div key={verdict} className={cx('arch-count', `watch-count-${verdict}`)}>
            <strong>{counts[verdict] || 0}</strong>
            <span>{verdict}</span>
          </div>
        ))}
        <div className="arch-count">
          <strong>{repos.length}</strong>
          <span>watched repos</span>
        </div>
      </div>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <div className="watch-grid">
        <div className="arch-panel">
          <div className="arch-panel-head">
            <Radar size={16} aria-hidden="true" />
            <div>
              <strong>监控中的仓库</strong>
              <span>基线提交与最近一次检查</span>
            </div>
          </div>
          <div className="watch-repos">
            {repos.length ? repos.map((repo) => (
              <div key={repo.project} className="watch-repo">
                <div>
                  <strong>{repo.project}</strong>
                  <span>{repo.last_sha ? shortSha(repo.last_sha) : 'no baseline'}</span>
                </div>
                <div className="watch-repo-meta">
                  <span>{repo.recent?.length || 0} recent</span>
                  <span>{repo.last_checked ? new Date(repo.last_checked).toLocaleString() : 'never'}</span>
                </div>
              </div>
            )) : <p className="watch-empty">还没有连接仓库。运行 `python3 scripts/watch/watch.py add --path ...`。</p>}
          </div>
        </div>

        <div className="arch-panel">
          <div className="arch-panel-head">
            <ShieldAlert size={16} aria-hidden="true" />
            <div>
              <strong>值得看的更新</strong>
              <span>按风险和最近时间排序</span>
            </div>
          </div>
          <div className="watch-events">
            {events.length ? events.map((event) => (
              <article key={event.id} className="watch-event">
                <div className="watch-event-top">
                  <span className={cx('watch-verdict', `is-${event.verdict}`)}>{event.verdict}</span>
                  <span className="watch-event-project">{event.project}</span>
                  <span className="watch-event-sha"><GitCommitHorizontal size={13} aria-hidden="true" />{shortSha(event.sha)}</span>
                  <span className="watch-event-score">{event.score}</span>
                </div>
                <p>{event.subject || event.summary}</p>
                <div className="watch-event-foot">
                  <span>{event.report_md || ''}</span>
                  {event.seen ? <span className="watch-seen">seen</span> : <span className="watch-new">new</span>}
                </div>
              </article>
            )) : (
              <div className="watch-empty">
                <Activity size={20} aria-hidden="true" />
                <p>还没有新提交。基线已建立，下一次 `watch.py poll` 会在这里出现变化。</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
