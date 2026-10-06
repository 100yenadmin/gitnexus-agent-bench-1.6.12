// Ground truth for the impact probe: for each target, add a required trailing parameter `__benchProbe: never` IN
// MEMORY (no file writes) and record the type errors that appear vs the unmodified baseline. Those error lines are
// exactly the places that must be updated. Usage (cwd = <checkout>/gitnexus): node gt.mjs targets.json > gt.json
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(path.resolve('package.json'));
const ts = require('typescript');
const root = process.cwd();
const targets = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const cfg = ts.getParsedCommandLineOfConfigFile(path.join(root, 'tsconfig.json'), {}, {
  ...ts.sys, onUnRecoverableConfigFileDiagnostic: (d) => { throw new Error(String(d.messageText)); },
});
const files = cfg.fileNames;
const overrides = new Map();
const versions = new Map();
const host = {
  getScriptFileNames: () => files, getScriptVersion: (f) => String(versions.get(f) || 0),
  getScriptSnapshot: (f) => {
    const t = overrides.has(f) ? overrides.get(f) : (fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : undefined);
    return t === undefined ? undefined : ts.ScriptSnapshot.fromString(t);
  },
  getCurrentDirectory: () => root, getCompilationSettings: () => cfg.options,
  getDefaultLibFileName: (o) => ts.getDefaultLibFilePath(o), fileExists: ts.sys.fileExists, readFile: ts.sys.readFile,
  readDirectory: ts.sys.readDirectory, directoryExists: ts.sys.directoryExists, getDirectories: ts.sys.getDirectories,
};
const ls = ts.createLanguageService(host, ts.createDocumentRegistry());
const rel = (f) => path.relative(path.dirname(root), f);
const diags = () => {
  const p = ls.getProgram(); const out = new Map();
  for (const sf of p.getSourceFiles()) {
    if (!files.includes(sf.fileName)) continue;
    for (const d of p.getSemanticDiagnostics(sf)) {
      if (!d.file || d.start === undefined) continue;
      const { line } = d.file.getLineAndCharacterOfPosition(d.start);
      const k = `${rel(d.file.fileName)}:${line + 1}:TS${d.code}`;
      out.set(k, (out.get(k) || 0) + 1);
    }
  }
  return out;
};
const base = diags();
process.stderr.write(`baseline errors: ${base.size}\n`);
const result = [];
for (const t of targets) {
  const abs = path.join(path.dirname(root), t.file);
  const src = fs.readFileSync(abs, 'utf8');
  const sf = ts.createSourceFile(abs, src, ts.ScriptTarget.Latest, true);
  let fn = null;
  const visit = (n) => {
    if (fn) return;
    let name = null, f = null;
    if ((ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n)) && n.name) { name = n.name; f = n; }
    else if (ts.isVariableDeclaration(n) && n.initializer && (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))) { name = n.name; f = n.initializer; }
    if (name && name.getText(sf) === t.name && sf.getLineAndCharacterOfPosition(name.getStart(sf)).line + 1 === t.line) { fn = f; return; }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  if (!fn) { result.push({ ...t, error: 'declaration not found' }); continue; }
  const ps = fn.parameters;
  const pos = ps.length ? ps[ps.length - 1].end : ps.pos;
  const ins = ps.length ? ', __benchProbe: never' : '__benchProbe: never';
  overrides.set(abs, src.slice(0, pos) + ins + src.slice(pos));
  versions.set(abs, (versions.get(abs) || 0) + 1);
  const after = diags();
  overrides.delete(abs); versions.set(abs, versions.get(abs) + 1);
  const added = [...after.keys()].filter((k) => !base.has(k) || after.get(k) > base.get(k)).sort();
  const sites = added.map((k) => { const [file, line, code] = k.split(':'); return { file, line: Number(line), code }; });
  process.stderr.write(`${t.name}: ${sites.length} new error sites\n`);
  result.push({ ...t, sites });
}
process.stdout.write(JSON.stringify(result, null, 1) + '\n');
