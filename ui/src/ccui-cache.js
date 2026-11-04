import { api } from './api.js';

export const traceVersion = trace => `${trace?.updatedAt || ''}:${trace?.size || 0}`;

export function createCcuiCache(fetchSession, { now = Date.now, ttl = 30000, limit = 24 } = {}) {
  const values = new Map();
  const pending = new Map();
  const generations = new Map();
  const keyOf = (project, runId, options) => JSON.stringify([project, runId, options.node || 'orchestrator', options.trace || '']);
  function peek(project, runId, options = {}) {
    const key = keyOf(project, runId, options);
    const entry = values.get(key);
    return entry && entry.version === (options.version || '') && now() - entry.at < ttl ? entry.payload : null;
  }
  function load(project, runId, options = {}) {
    const key = keyOf(project, runId, options);
    const cached = !options.force && !options.refresh && peek(project, runId, options);
    if (cached) return Promise.resolve(cached);
    const requestKey = JSON.stringify([key, options.version || '', Boolean(options.force)]);
    if (pending.has(requestKey)) return pending.get(requestKey);
    const generation = (generations.get(key) || 0) + 1;
    generations.set(key, generation);
    const promise = Promise.resolve().then(() => fetchSession(project, runId, options)).then(payload => {
      if (generations.get(key) === generation) {
        if (payload.available && payload.reachable) {
          values.delete(key);
          values.set(key, {payload, version: options.version || '', at: now()});
          while (values.size > limit) values.delete(values.keys().next().value);
        } else values.delete(key);
      }
      return payload;
    }).finally(() => {
      pending.delete(requestKey);
      if (![...pending.keys()].some(item => JSON.parse(item)[0] === key)) generations.delete(key);
    });
    pending.set(requestKey, promise);
    return promise;
  }
  return { peek, load };
}

export const ccuiSessions = createCcuiCache((project, runId, options) => api.runCcui(project, runId, options));
