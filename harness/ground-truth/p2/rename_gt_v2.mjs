// Rename-probe ground truth / oracle v2, TypeScript language service over tsconfig.test.json (src + tests).
// v2: identifiers are attributed by the symbol they RESOLVE to (aliases followed through imports/re-exports), so a
// rename that also renames a re-export and its downstream users (a valid full rename) passes, as does TS's own
// rename that keeps the old public name as an alias; true namesakes (other symbols) must stay untouched either way.
//   gt mode (base checkout):    node rename_gt.mjs gt targets.json > spec.json
//     per target: rename locations (TS's own rename engine), identifier counts of the old and new names, baseline
//     diagnostics count, and the reference count of the target symbol.
//   check mode (patched repo):  node rename_gt.mjs check spec.json <target-name>   (exit 0 = pass)
//     pass = no new type errors vs baseline, the renamed symbol (declared at the target file under newName) has the
//     same number of references as at base, identifiers named old == namesakes only, identifiers named new == the
//     rename locations (nothing else was renamed to the new name).
// cwd = <checkout>/gitnexus
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(path.resolve('package.json'));
const ts = require('typescript');
const root = process.cwd();
const cfg = ts.getParsedCommandLineOfConfigFile(path.join(root, 'tsconfig.test.json'), {}, {
  ...ts.sys, onUnRecoverableConfigFileDiagnostic: (d) => { throw new Error(String(d.messageText)); },
});
const files = cfg.fileNames;
const host = {
  getScriptFileNames: () => files, getScriptVersion: () => '0',
  getScriptSnapshot: (f) => (fs.existsSync(f) ? ts.ScriptSnapshot.fromString(fs.readFileSync(f, 'utf8')) : undefined),
  getCurrentDirectory: () => root, getCompilationSettings: () => cfg.options,
  getDefaultLibFileName: (o) => ts.getDefaultLibFilePath(o), fileExists: ts.sys.fileExists, readFile: ts.sys.readFile,
  readDirectory: ts.sys.readDirectory, directoryExists: ts.sys.directoryExists, getDirectories: ts.sys.getDirectories,
};
const ls = ts.createLanguageService(host, ts.createDocumentRegistry());
const program = ls.getProgram();
const checker = program.getTypeChecker();
function resolveSym(id) {
  let s = checker.getSymbolAtLocation(id);
  if (!s && id.parent && ts.isShorthandPropertyAssignment(id.parent)) s = checker.getShorthandAssignmentValueSymbol(id.parent);
  for (let i = 0; s && (s.flags & ts.SymbolFlags.Alias) && i < 10; i++) {
    try { s = checker.getAliasedSymbol(s); } catch { break; }
  }
  return s;
}
function identNodes(name) { // code identifiers named `name` in own files, as nodes
  const out = [];
  for (const sf of program.getSourceFiles()) {
    if (!own(sf)) continue;
    const visit = (x) => { if (ts.isIdentifier(x) && x.text === name) out.push(x); ts.forEachChild(x, visit); };
    visit(sf);
  }
  return out;
}
function identAt(sf, pos) {
  let node = null;
  const find = (x) => { if (node || pos < x.getFullStart() || pos >= x.getEnd()) return;
    if (ts.isIdentifier(x) && x.getStart(sf) === pos) { node = x; return; } ts.forEachChild(x, find); };
  find(sf);
  return node;
}
// The target = every symbol TypeScript's rename engine ties to the declaration (the symbol itself, related interface or
// base members, alias chains), resolved through aliases.
function targetSet(d) {
  const set = new Set();
  const n0 = identAt(d.sf, d.pos); const s0 = n0 && resolveSym(n0); if (s0) set.add(s0);
  for (const l of ls.findRenameLocations(d.sf.fileName, d.pos, false, false, { providePrefixAndSuffixTextForRename: true }) || []) {
    const sf = program.getSourceFile(l.fileName); const node = sf && identAt(sf, l.textSpan.start);
    const sym = node && resolveSym(node); if (sym) set.add(sym);
  }
  return set;
}
const rel = (f) => path.relative(path.dirname(root), f);
const own = (sf) => files.includes(sf.fileName) && !sf.isDeclarationFile;

function idents(name) { // code identifiers (JSDoc is not visited by forEachChild) as "file:start" keys
  const out = [];
  for (const sf of program.getSourceFiles()) {
    if (!own(sf)) continue;
    const visit = (x) => { if (ts.isIdentifier(x) && x.text === name) out.push(`${rel(sf.fileName)}:${x.getStart(sf)}`); ts.forEachChild(x, visit); };
    visit(sf);
  }
  return out;
}
const identCount = (name) => idents(name).length;
function errorCount() {
  let n = 0;
  for (const sf of program.getSourceFiles()) if (own(sf)) n += program.getSemanticDiagnostics(sf).length + program.getSyntacticDiagnostics(sf).length;
  return n;
}
function findDecl(file, cls, name) { // the function/method named `name` (inside class `cls` if given) in `file`
  const sf = program.getSourceFile(path.join(path.dirname(root), file));
  if (!sf) return null;
  let hit = null;
  const visit = (n, inCls) => {
    if (hit) return;
    if (ts.isClassDeclaration(n) && n.name) { ts.forEachChild(n, (c) => visit(c, n.name.text)); return; }
    let id = null;
    if ((ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n)) && n.name && ts.isIdentifier(n.name)) id = n.name;
    else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))) id = n.name;
    if (id && id.text === name && (cls ? inCls === cls : !inCls)) { hit = { sf, pos: id.getStart(sf) }; return; }
    ts.forEachChild(n, (c) => visit(c, inCls));
  };
  visit(sf, null);
  return hit;
}
function refCount(d) {
  let n = 0;
  for (const g of ls.findReferences(d.sf.fileName, d.pos) || []) for (const r of g.references) if (!r.isDefinition) n++;
  return n;
}

const [mode, arg, which] = process.argv.slice(2);
if (mode === 'gt') {
  const out = [];
  const errors = errorCount();
  for (const t of JSON.parse(fs.readFileSync(arg, 'utf8'))) {
    const d = findDecl(t.file, t.cls, t.name);
    if (!d) { out.push({ ...t, error: 'declaration not found' }); continue; }
    const locs = (ls.findRenameLocations(d.sf.fileName, d.pos, false, false, { providePrefixAndSuffixTextForRename: true }) || [])
      .map((l) => { const sf = program.getSourceFile(l.fileName); const { line } = sf.getLineAndCharacterOfPosition(l.textSpan.start);
                    return { file: rel(l.fileName), line: line + 1, key: `${rel(l.fileName)}:${l.textSpan.start}`,
                             prefix: l.prefixText || '', suffix: l.suffixText || '' }; });
    const keys = new Set(locs.map((l) => l.key));
    const old = idents(t.name);
    const inCode = old.filter((k) => keys.has(k)).length;  // rename locations that are code identifiers (not JSDoc links)
    const S = targetSet(d);
    const oldNodes = identNodes(t.name);
    const v2_target_idents = oldNodes.filter((x) => S.has(resolveSym(x))).length;
    out.push({ ...t, baseline_errors: errors, refs: refCount(d), v2_target_idents, v2_namesake_idents: oldNodes.length - v2_target_idents, rename_locations: locs.length, rename_code_locations: inCode,
               jsdoc_locations: locs.length - inCode, aliased_locations: locs.filter((l) => l.prefix || l.suffix).length,
               old_idents: old.length, namesake_idents: old.length - inCode, new_idents_at_base: identCount(t.newName),
               files: [...new Set(locs.map((l) => l.file))].length, locations: locs });
  }
  process.stdout.write(JSON.stringify(out, null, 1) + '\n');
} else if (mode === 'check') {
  const t = JSON.parse(fs.readFileSync(arg, 'utf8')).find((x) => x.name === which);
  const res = { target: which };
  res.errors = errorCount();
  const d = findDecl(t.file, t.cls, t.newName);
  res.decl_found = !!d;
  res.refs = d ? refCount(d) : -1;
  res.old_idents = identCount(t.name);
  res.new_idents = identCount(t.newName);
  // Aliased imports keep their local alias, so the new name appears once per rename location minus nothing:
  // TS rename of `import { a as b }` rewrites only `a`, which is one rename location.
  const S = d ? targetSet(d) : new Set();
  const oldNodes = identNodes(t.name), newNodes = identNodes(t.newName);
  res.v2_old_namesakes = oldNodes.filter((x) => !S.has(resolveSym(x))).length;  // old-name identifiers of OTHER symbols
  res.v2_old_aliases = oldNodes.length - res.v2_old_namesakes;                  // old name kept as an alias of the target
  res.v2_new_foreign = newNodes.filter((x) => !S.has(resolveSym(x))).length;    // new-name identifiers of OTHER symbols
  res.checks = {
    no_new_type_errors: res.errors <= t.baseline_errors,
    renamed_symbol_found: res.decl_found,
    all_references_kept: res.refs >= t.refs && res.refs <= t.refs + t.aliased_locations,
    // Slack = alias sites (e.g. a shorthand property key `{ old }` -> `{ old: renamed }` keeps one old-name key).
    namesakes_untouched: res.v2_old_namesakes >= t.v2_namesake_idents && res.v2_old_namesakes <= t.v2_namesake_idents + t.aliased_locations,
    nothing_else_renamed: res.v2_new_foreign <= t.aliased_locations && newNodes.length >= 1,
  };
  res.pass = Object.values(res.checks).every(Boolean);
  process.stdout.write(JSON.stringify(res) + '\n');
  process.exit(res.pass ? 0 : 1);
}
if (mode === 'apply') { // positive control only: write TS's own rename edits for one target to disk
  const t = JSON.parse(fs.readFileSync(arg, 'utf8')).find((x) => x.name === which);
  const d = findDecl(t.file, t.cls, t.name);
  const locs = ls.findRenameLocations(d.sf.fileName, d.pos, false, false, { providePrefixAndSuffixTextForRename: true }) || [];
  const byFile = new Map();
  for (const l of locs) { if (!byFile.has(l.fileName)) byFile.set(l.fileName, []); byFile.get(l.fileName).push(l); }
  for (const [f, ls2] of byFile) {
    let text = fs.readFileSync(f, 'utf8');
    for (const l of ls2.sort((a, b) => b.textSpan.start - a.textSpan.start)) {
      text = text.slice(0, l.textSpan.start) + (l.prefixText || '') + t.newName + (l.suffixText || '') + text.slice(l.textSpan.start + l.textSpan.length);
    }
    fs.writeFileSync(f, text);
  }
  process.stdout.write(`applied ${locs.length} edits in ${byFile.size} files\n`);
}
