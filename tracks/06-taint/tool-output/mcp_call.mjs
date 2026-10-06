// Minimal MCP stdio client: node mcp_call.mjs <launcher> <tool> '<json args>'  (env passes BENCH_GN_HOME etc.)
import { spawn } from 'node:child_process';
const [launcher, tool, args] = process.argv.slice(2);
const p = spawn(launcher, ['mcp'], { stdio: ['pipe', 'pipe', 'inherit'], env: process.env });
let buf = '', id = 0; const pending = new Map();
p.stdout.on('data', (d) => { buf += d; let i; while ((i = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, i); buf = buf.slice(i + 1);
  try { const m = JSON.parse(line); if (m.id !== undefined && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } } catch {} } });
const rpc = (method, params) => new Promise((res) => { const i = ++id; pending.set(i, res); p.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: i, method, params }) + '\n'); });
const note = (method, params) => p.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
await rpc('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'bench', version: '1' } });
note('notifications/initialized', {});
const r = await rpc('tools/call', { name: tool, arguments: JSON.parse(args || '{}') });
const c = r.result?.content?.map((x) => x.text).join('\n') ?? JSON.stringify(r.error ?? r);
process.stdout.write(c + '\n');
p.kill();
