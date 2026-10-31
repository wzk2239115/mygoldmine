import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { deriveBoundary, parseAgentTopology } from '../server/agent-topology.mjs';

function writeRaw(lines) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-topology-'));
  const file = path.join(dir, 'raw.jsonl');
  fs.writeFileSync(file, lines.map((line) => (typeof line === 'string' ? line : JSON.stringify(line))).join('\n'));
  return { dir, file };
}

test('parses parallel Agent calls and their results', () => {
  const { dir, file } = writeRaw([
    {
      type: 'assistant',
      message: {
        content: [{
          type: 'tool_use',
          id: 'call-config',
          name: 'Agent',
          input: {
            subagent_type: 'infra-analyst',
            description: 'Analyze config trust boundary',
            prompt: '负责 config 信任边界，读取 .env 与 cordis.patch.yml'
          }
        }]
      }
    },
    {
      type: 'assistant',
      message: {
        content: [{
          type: 'tool_use',
          id: 'call-mcp',
          name: 'Agent',
          input: {
            subagent_type: 'infra-analyst',
            description: 'Analyze MCP boundary',
            prompt: '负责 MCP server 的 command/args/env'
          }
        }]
      }
    },
    'not json',
    {
      type: 'user',
      timestamp: '2026-10-30T09:00:00Z',
      message: {
        content: [{
          type: 'tool_result',
          tool_use_id: 'call-config',
          content: [{ text: '配置边界完成，含 2 条 finding、1 条 hypothesis。' }]
        }]
      }
    }
  ]);

  try {
    const topology = parseAgentTopology(file);
    assert.equal(topology.summary.total, 2);
    assert.equal(topology.summary.completed, 1);
    assert.equal(topology.summary.running, 1);
    assert.deepEqual(topology.agents.map((agent) => agent.boundary), ['config', 'mcp']);
    assert.equal(topology.agents[0].status, 'completed');
    assert.equal(topology.agents[0].findings, 2);
    assert.equal(topology.agents[0].hypotheses, 1);
    assert.match(topology.agents[0].summary, /配置边界完成/);
    assert.equal(topology.agents[1].status, 'running');
    assert.equal(topology.agents[1].summary, '');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('supports Task tool and marks errors', () => {
  const { dir, file } = writeRaw([
    {
      type: 'assistant',
      message: {
        content: [{
          type: 'tool_use',
          id: 'call-sandbox',
          name: 'Task',
          input: { description: 'Analyze sandbox boundary' }
        }]
      }
    },
    {
      type: 'user',
      message: {
        content: [{
          type: 'tool_result',
          tool_use_id: 'call-sandbox',
          is_error: true,
          content: [{ text: 'sandbox policy read failed' }]
        }]
      }
    }
  ]);

  try {
    const topology = parseAgentTopology(file);
    assert.equal(topology.agents.length, 1);
    assert.equal(topology.agents[0].agent, 'general-purpose');
    assert.equal(topology.agents[0].boundary, 'sandbox');
    assert.equal(topology.agents[0].status, 'error');
    assert.equal(topology.summary.failed, 1);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('deriveBoundary recognizes harness trust boundaries', () => {
  assert.equal(deriveBoundary('Analyze process-exec boundary'), 'process-exec');
  assert.equal(deriveBoundary('Analyze control plane boundary'), 'control-plane');
  assert.equal(deriveBoundary('Analyze filesystem boundary'), 'filesystem');
  assert.equal(deriveBoundary('Analyze config trust boundary', 'mentions shell and sandbox in prompts'), 'config');
  assert.equal(deriveBoundary('Analyze MCP boundary', 'reads resources and prompt injection'), 'mcp');
  assert.equal(deriveBoundary('random task'), 'general');
});

test('missing raw file returns an empty topology', () => {
  const topology = parseAgentTopology('/tmp/definitely-missing-agent-topology.jsonl');
  assert.deepEqual(topology.agents, []);
  assert.equal(topology.summary.total, 0);
});
