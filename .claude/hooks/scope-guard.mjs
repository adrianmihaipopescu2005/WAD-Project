#!/usr/bin/env node
// PreToolUse hook: keeps fe-* agents out of backend/ + adr/backend/ and be-* agents out of frontend/ + adr/frontend/.
// adr/shared/ is open to both. Usage: node scope-guard.mjs [frontend|backend]
// Without an argument the scope is derived from `agent_type` (fe-* / be-*); the main session is never restricted.
import path from 'node:path';

const SCOPES = { frontend: 'backend', backend: 'frontend' };
const FORBIDDEN_DIRS = { frontend: ['backend', 'adr/backend'], backend: ['frontend', 'adr/frontend'] };
// FE agents may read the blueprints for route names, form fields and template context.
const READ_EXCEPTIONS = { frontend: ['backend/app/blueprints'] };
const READ_TOOLS = new Set(['Read', 'Grep', 'Glob']);

const allow = () => process.exit(0);
const deny = (reason) => {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason },
  }));
  process.exit(0);
};

let raw = '';
for await (const chunk of process.stdin) raw += chunk;

let input;
try { input = JSON.parse(raw); } catch { input = null; }

const scope = process.argv[2] ?? scopeFromAgent(input?.agent_type);
if (!scope) allow();
if (!SCOPES[scope]) deny(`scope-guard: unknown scope "${scope}"`);
if (!input) deny('scope-guard: could not parse hook input');

const forbiddenName = SCOPES[scope];
const root = norm(process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd());
const cwd = norm(input.cwd || root);
const forbiddenDirs = FORBIDDEN_DIRS[scope].map((d) => `${root}/${d}`);
const exceptions = (READ_EXCEPTIONS[scope] ?? []).map((p) => `${root}/${p}`);
const tool = input.tool_name;
const ti = input.tool_input ?? {};
const msg = `${scope === 'frontend' ? 'fe' : 'be'}-* agents may not access ${forbiddenName}/ or adr/${forbiddenName}/`;

if (tool === 'Bash') {
  const cmd = String(ti.command ?? '').replace(/\\/g, '/');
  const re = new RegExp(`(^|[\\s"'=:/(])${forbiddenName}(/|[\\s"';)|&]|$)`, 'i');
  if (re.test(cmd)) deny(`${msg} (Bash command references ${forbiddenName}/)`);
  allow();
}

const targets = [];
for (const key of ['file_path', 'notebook_path']) if (ti[key]) targets.push(resolve(ti[key]));
if (tool === 'Glob' || tool === 'Grep') {
  const searchRoot = resolve(ti.path || '.');
  // A search rooted above the forbidden folder would read inside it.
  const hit = forbiddenDirs.find((d) => d.startsWith(searchRoot + '/'));
  if (hit) {
    deny(`${msg}. Search root ${ti.path || '.'} contains ${hit.slice(root.length + 1)}/ — pass an explicit path such as "${scope}/", "adr/${scope}/" or "adr/shared/".`);
  }
  targets.push(searchRoot);
  if (tool === 'Glob' && ti.pattern) targets.push(resolve(path.posix.join(searchRoot, String(ti.pattern))));
} else if (ti.path) {
  targets.push(resolve(ti.path));
}

for (const t of targets) {
  if (!forbiddenDirs.some((d) => inside(t, d))) continue;
  if (READ_TOOLS.has(tool) && exceptions.some((e) => inside(t, e))) continue;
  deny(msg);
}
allow();

function scopeFromAgent(type) {
  if (typeof type !== 'string') return undefined;
  if (type.startsWith('fe-')) return 'frontend';
  if (type.startsWith('be-')) return 'backend';
  return undefined;
}

// Normalize to lowercase forward-slash absolute paths; maps Git Bash /c/... to c:/...
function norm(p) {
  let s = String(p).replace(/\\/g, '/');
  s = s.replace(/^\/([a-zA-Z])\//, '$1:/');
  return path.posix.normalize(s).replace(/\/+$/, '').toLowerCase();
}

function resolve(p) {
  const s = norm(p);
  const abs = /^[a-z]:\//.test(s) || s.startsWith('/') ? s : `${cwd}/${s}`;
  return path.posix.normalize(abs).replace(/\/+$/, '');
}

function inside(p, dir) {
  return p === dir || p.startsWith(dir + '/');
}
