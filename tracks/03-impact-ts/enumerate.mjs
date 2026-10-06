// Enumerate candidate impact-probe targets in gitnexus/src with the TypeScript language service (neutral: no
// GitNexus involvement). Usage (cwd = <checkout>/gitnexus): node enumerate.mjs > candidates.jsonl
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(path.resolve('package.json'));
const ts = require('typescript');
const root = process.cwd();
const cfg = ts.getParsedCommandLineOfConfigFile(path.join(root, 'tsconfig.json'), {}, {
  ...ts.sys, onUnRecoverableConfigFileDiagnostic: (d) => { throw new Error(String(d.messageText)); },
});
const files = cfg.fileNames.filter((f) => !f.endsWith('.d.ts'));
const versions = new Map(files.map((f) => [f, '0']));
const host = {
  getScriptFileNames: () => files, getScriptVersion: (f) => versions.get(f) || '0',
  getScriptSnapshot: (f) => (fs.existsSync(f) ? ts.ScriptSnapshot.fromString(fs.readFileSync(f, 'utf8')) : undefined),
  getCurrentDirectory: () => root, getCompilationSettings: () => cfg.options,
  getDefaultLibFileName: (o) => ts.getDefaultLibFilePath(o), fileExists: ts.sys.fileExists, readFile: ts.sys.readFile,
  readDirectory: ts.sys.readDirectory, directoryExists: ts.sys.directoryExists, getDirectories: ts.sys.getDirectories,
};
const ls = ts.createLanguageService(host, ts.createDocumentRegistry());
const program = ls.getProgram();
const rel = (f) => path.relative(path.dirname(root), f);

const decls = [];
for (const sf of program.getSourceFiles()) {
  if (!files.includes(sf.fileName)) continue;
  const visit = (n, cls) => {
    let name = null, kind = null, fn = null;
    if (ts.isFunctionDeclaration(n) && n.name && n.body) { name = n.name; kind = 'function'; fn = n; }
    else if (ts.isMethodDeclaration(n) && n.body && ts.isIdentifier(n.name)) { name = n.name; kind = 'method'; fn = n; }
    else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer &&
             (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer)) &&
             ts.isSourceFile(n.parent.parent.parent)) { name = n.name; kind = 'const-fn'; fn = n.initializer; }
    if (name) {
      const { line } = sf.getLineAndCharacterOfPosition(name.getStart(sf));
      decls.push({ name: name.text, kind, cls, file: sf.fileName, line: line + 1, pos: name.getStart(sf),
                   params: fn.parameters.length, rest: fn.parameters.some((p) => p.dotDotDotToken),
                   exported: !!(ts.getCombinedModifierFlags(n.kind === ts.SyntaxKind.VariableDeclaration ? n.parent.parent : n) & ts.ModifierFlags.Export) });
    }
    ts.forEachChild(n, (c) => visit(c, ts.isClassDeclaration(n) && n.name ? n.name.text : cls));
  };
  visit(sf, null);
}
const byName = new Map();
for (const d of decls) byName.set(d.name, (byName.get(d.name) || 0) + 1);
for (const d of decls) {
  if (d.name.length < 4 || d.rest) continue;
  const refs = ls.findReferences(d.file, d.pos) || [];
  const sites = [];
  for (const g of refs) for (const r of g.references) {
    if (r.isDefinition) continue;
    const sf = program.getSourceFile(r.fileName);
    let node = sf && ts.getTokenAtPosition(sf, r.textSpan.start);
    let p = node && node.parent, ctx = 'other';
    while (p && (ts.isPropertyAccessExpression(p) || ts.isElementAccessExpression(p)) ) { node = p; p = p.parent; }
    if (p && ts.isCallExpression(p) && p.expression === node) ctx = 'call';
    else if (p && (ts.isImportSpecifier(p) || ts.isExportSpecifier(p) || ts.isImportClause(p) || ts.isNamespaceImport(p))) ctx = 'import';
    else if (p && ts.isNewExpression(p)) ctx = 'new';
    const { line } = sf.getLineAndCharacterOfPosition(r.textSpan.start);
    sites.push({ file: rel(r.fileName), line: line + 1, ctx });
  }
  const live = sites.filter((s) => s.ctx !== 'import');
  if (!live.length) continue;
  process.stdout.write(JSON.stringify({
    name: d.name, kind: d.kind, cls: d.cls, file: rel(d.file), line: d.line, params: d.params, exported: d.exported,
    namesakes: byName.get(d.name) - 1, calls: live.filter((s) => s.ctx === 'call').length,
    nonCallRefs: live.filter((s) => s.ctx !== 'call').length, files: new Set(live.map((s) => s.file)).size,
    importRefs: sites.length - live.length, sites: live,
  }) + '\n');
}
