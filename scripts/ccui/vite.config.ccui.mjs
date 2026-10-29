// Wraps the CloudCLI vite config to build the client for mounting under the
// vul-ai-board's /ccui/ path prefix. The board server (ui/server/index.mjs)
// reverse-proxies /ccui/* and CloudCLI's API/WS endpoints to the CloudCLI
// server, so everything shares one exposed port (8787).
import upstream from '../../third_party/claudecodeui/vite.config.js';

export default function config(env) {
  const resolved = typeof upstream === 'function' ? upstream(env) : upstream;
  return {
    ...resolved,
    base: '/ccui/'
  };
}
