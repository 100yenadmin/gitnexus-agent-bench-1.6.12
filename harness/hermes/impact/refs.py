#!/usr/bin/env python3
"""Completeness check: enumerate every textual (NAME-token) reference to each target's name across the in-scope files
and pre-classify it: comment, string (incl. f-string text; read for getattr/dynamic use), def (a definition of any same-named symbol), gt (a pyright breakage line, +-0), import, or
residual (needs reading). Strings and comments are excluded by tokenize. Residuals are printed with context for manual
adjudication. Names bound by `from <target module> import <name> as <alias>` are enumerated too (field `alias`).
Usage: refs.py gt.json out.jsonl [name-filter]"""
import io, json, re, sys, tokenize, collections, ast
_WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
BASE = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact')
A = _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'impact')
files = [l.strip() for l in open(f'{A}/scope-files.txt') if l.strip()]
gt = json.load(open(sys.argv[1]))
flt = sys.argv[3] if len(sys.argv) > 3 else None
names = {t['name'] for t in gt if not flt or t['name'] == flt}
occ = collections.defaultdict(list)
srcl = {}
def modname(f):
    m = f[:-3].replace('/', '.')
    return m[:-9] if m.endswith('.__init__') else m
def resolve_from(f, node):
    if node.level:
        pkg = modname(f).split('.')
        if not f.endswith('__init__.py'): pkg = pkg[:-1]
        if node.level > 1: pkg = pkg[:len(pkg) - (node.level - 1)]
        return '.'.join(pkg + ([node.module] if node.module else []))
    return node.module
# module-level function targets: (module, name); `from module import name as alias` makes alias a reference too
modtargets = {(modname(t['file']), t['name']) for t in gt if not t['cls'] and (not flt or t['name'] == flt)}
for f in files:
    s = open(f'{BASE}/{f}', encoding='utf-8').read()
    if not any(n in s for n in names): continue
    srcl[f] = s.splitlines()
    implines = set(); aliases = {}
    for n in ast.walk(ast.parse(s)):
        if isinstance(n, (ast.Import, ast.ImportFrom)): implines.update(range(n.lineno, n.end_lineno + 1))
        if isinstance(n, ast.ImportFrom):
            m = resolve_from(f, n)
            for a in n.names:
                if a.asname and a.asname != a.name and (m, a.name) in modtargets: aliases[a.asname] = a.name
    try: toks = list(tokenize.generate_tokens(io.StringIO(s).readline))
    except Exception as e: print('tokenize fail', f, e, file=sys.stderr); continue
    for i, tk in enumerate(toks):
        if tk.type in (tokenize.STRING, tokenize.COMMENT, getattr(tokenize, 'FSTRING_MIDDLE', -1), getattr(tokenize, 'TSTRING_MIDDLE', -1)):
            lit = tk.string.strip().lstrip('rbfuRBFU').strip('\'"') if tk.type == tokenize.STRING else None
            for w in set(_WORD.findall(tk.string)) & names:
                # a string whose whole value is the name is a dynamic-lookup candidate (getattr/registry key): needs a
                # verdict; prose that merely mentions the name is documentation
                kind = 'comment' if tk.type == tokenize.COMMENT else ('string-exact' if lit == w else 'string')
                occ[w].append(dict(file=f, line=tk.start[0], col=tk.start[1], prev='', prev2='', nxt='', text=tk.line.rstrip('\n')[:240],
                                   imp=False, kind=kind))
            continue
        if tk.type == tokenize.NAME and tk.string in aliases and tk.start[0] not in implines:
            occ[aliases[tk.string]].append(dict(file=f, line=tk.start[0], col=tk.start[1], prev=toks[i - 1].string, prev2=toks[i - 2].string if i > 1 else '',
                                                nxt=toks[i + 1].string if i + 1 < len(toks) else '', text=tk.line.rstrip('\n'), imp=False, alias=tk.string))
            continue
        if tk.type == tokenize.NAME and tk.string in names:
            prev = toks[i - 1].string if i else ''
            prev2 = toks[i - 2].string if i > 1 else ''
            nxt = toks[i + 1].string if i + 1 < len(toks) else ''
            occ[tk.string].append(dict(file=f, line=tk.start[0], col=tk.start[1], prev=prev, prev2=prev2, nxt=nxt, text=tk.line.rstrip('\n'), imp=tk.start[0] in implines))
out = open(sys.argv[2], 'w')
for t in gt:
    if t['name'] not in names or 'sites' not in t: continue
    sites = {(s['file'], s['line']) for s in t['sites']}
    for o in occ[t['name']]:
        if o.get('kind'): c = o['kind']
        elif o['prev'] in ('def', 'class'): c = 'def'
        elif (o['file'], o['line']) in sites: c = 'gt'
        elif o['imp']: c = 'import'
        else: c = 'residual'
        out.write(json.dumps(dict(target=f"{t['cls'] + '.' if t['cls'] else ''}{t['name']}", tfile=t['file'], tline=t['line'], target_cls=t['cls'], cls=c, **o)) + '\n')
