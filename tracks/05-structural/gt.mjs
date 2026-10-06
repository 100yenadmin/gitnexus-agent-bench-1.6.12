// P3 ground truth (route map / tool map / API consumers), TypeScript AST + language service, no GitNexus.
// Usage (cwd = checkout root): node gt.mjs > gt.json
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const require = createRequire(path.join(root, 'gitnexus/package.json'));
const ts = require('typescript');
const out = {};

// 1. HTTP routes registered in gitnexus/src/server: <obj>.<verb>('<path starting with />', ...)
const verbs = new Set(['get', 'post', 'put', 'delete', 'patch', 'all']);
const routes = [];
const walkDir = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) =>
  e.isDirectory() ? walkDir(path.join(d, e.name)) : e.name.endsWith('.ts') ? [path.join(d, e.name)] : []);
for (const f of walkDir(path.join(root, 'gitnexus/src/server'))) {
  const sf = ts.createSourceFile(f, fs.readFileSync(f, 'utf8'), ts.ScriptTarget.Latest, true);
  const visit = (n) => {
    if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && verbs.has(n.expression.name.text)
        && n.arguments.length >= 2 && ts.isStringLiteralLike(n.arguments[0]) && n.arguments[0].text.startsWith('/')) {
      const { line } = sf.getLineAndCharacterOfPosition(n.getStart(sf));
      routes.push({ method: n.expression.name.text.toUpperCase(), path: n.arguments[0].text, file: path.relative(root, f), line: line + 1 });
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
}
out.routes = routes;

// 2. MCP tool names: objects with a string `name` inside the exported GITNEXUS_TOOLS array literal.
{
  const f = path.join(root, 'gitnexus/src/mcp/tools.ts');
  const sf = ts.createSourceFile(f, fs.readFileSync(f, 'utf8'), ts.ScriptTarget.Latest, true);
  const names = [];
  const visit = (n) => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === 'GITNEXUS_TOOLS' && n.initializer) {
      let init = n.initializer;
      while (init && (ts.isAsExpression(init) || ts.isSatisfiesExpression?.(init))) init = init.expression;
      if (ts.isArrayLiteralExpression(init)) for (const el of init.elements) {
        if (!ts.isObjectLiteralExpression(el)) continue;
        for (const p of el.properties) if (ts.isPropertyAssignment(p) && p.name.getText(sf) === 'name' && ts.isStringLiteralLike(p.initializer)) names.push(p.initializer.text);
      }
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  out.tools = names;
}

// 3. API consumers in gitnexus-web/src: the function in backend-client.ts that requests the endpoint, plus every
//    non-test file that references that function (one level).
{
  const webRoot = path.join(root, 'gitnexus-web');
  const files = walkDir(path.join(webRoot, 'src')).filter((f) => !/\.(test|spec)\.tsx?$/.test(f))
    .concat(fs.readdirSync(path.join(webRoot, 'src'), { recursive: true }).filter((x) => String(x).endsWith('.tsx')).map((x) => path.join(webRoot, 'src', String(x))).filter((f) => !/\.(test|spec)\.tsx$/.test(f)));
  const uniq = [...new Set(files)];
  const host = {
    getScriptFileNames: () => uniq, getScriptVersion: () => '0',
    getScriptSnapshot: (f) => (fs.existsSync(f) ? ts.ScriptSnapshot.fromString(fs.readFileSync(f, 'utf8')) : undefined),
    getCurrentDirectory: () => webRoot, getCompilationSettings: () => ({ jsx: ts.JsxEmit.ReactJSX, allowJs: false, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler }),
    getDefaultLibFileName: (o) => ts.getDefaultLibFilePath(o), fileExists: ts.sys.fileExists, readFile: ts.sys.readFile,
    readDirectory: ts.sys.readDirectory, directoryExists: ts.sys.directoryExists, getDirectories: ts.sys.getDirectories,
  };
  const ls = ts.createLanguageService(host, ts.createDocumentRegistry());
  const client = path.join(webRoot, 'src/services/backend-client.ts');
  const sf = ls.getProgram().getSourceFile(client);
  const consumers = {};
  for (const ep of ['/api/query', '/api/repos', '/api/file', '/api/search', '/api/grep']) {
    const fns = [];
    const visit = (n, fn) => {
      const isFn = (ts.isFunctionDeclaration(n) && n.name) ? n
        : (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))) ? n
        : (ts.isMethodDeclaration(n) && n.name && ts.isIdentifier(n.name)) ? n : fn;
      if (ts.isTemplateExpression(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isStringLiteral(n)) {
        const txt = n.getText(sf);
        if (new RegExp(ep.replace('/', '\\/') + '(?![\\w-])').test(txt) && fn) fns.push(fn);
      }
      ts.forEachChild(n, (c) => visit(c, isFn));
    };
    visit(sf, null);
    const set = new Set(['gitnexus-web/src/services/backend-client.ts']);
    const fnNames = [...new Set(fns.map((f) => f.name.text))];
    for (const f of [...new Set(fns)]) {
      for (const g of ls.findReferences(client, f.name.getStart(sf)) || []) for (const r of g.references) {
        if (r.isDefinition) continue;
        const rsf = ls.getProgram().getSourceFile(r.fileName);
        const tok = rsf && ts.getTokenAtPosition(rsf, r.textSpan.start);
        if (tok && tok.parent && (ts.isImportSpecifier(tok.parent) || ts.isExportSpecifier(tok.parent))) continue;
        set.add(path.relative(root, r.fileName));
      }
    }
    consumers[ep] = { functions: fnNames, files: [...set].sort() };
  }
  out.consumers = consumers;
}
process.stdout.write(JSON.stringify(out, null, 1) + '\n');
