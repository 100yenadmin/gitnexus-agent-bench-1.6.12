#!/usr/bin/env python3
"""Ground truth for the hermes impact track (Python analogue of P1's gt.mjs).
For each target: APFS-clone the base checkout to a scratch dir, add a new required parameter `bench_probe` to the
target's signature, run the pinned pyright (run_pyright.sh, same file scope + venv as the baseline), and record every
error key (file, line, rule) whose count rose vs baseline.json. Those lines are the sites that must be updated.
Probe kinds: "positional" = appended required positional parameter (signature has no defaults / *args / kw-only);
"kwonly" = required keyword-only parameter (signature already has defaults or kw-only params, where a trailing
required positional would be a SyntaxError). Targets with **kwargs are rejected.
Platforms: pyright narrows sys.platform/os.name guards to one platform per run, leaving code under the other guards
unchecked, so each probe runs under --pythonplatform Darwin, Linux and Windows (each vs its own baseline) and the sites
are the union. A site is kept only when a new error on that line names the probe parameter (`bench_probe`, i.e. a
missing-argument or incompatible-callable error); cascade errors (e.g. lost Optional narrowing after the failed call)
are dropped and listed under `secondary`.
Usage: gt.py targets.json out.json [parallel=5]"""
import ast, json, os, shutil, subprocess, sys, collections, concurrent.futures as cf
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'impact')
BASE = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact')
SCR = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact-scratch')
HERE = _os.path.dirname(_os.path.abspath(__file__))  # run_pyright.sh lives here; outputs go to A
PROBE = 'bench_probe'
PLATFORMS = ['Darwin', 'Linux', 'Windows']

def keys(path, root):
    import gzip
    d = json.load(gzip.open(path + '.gz', 'rt') if not os.path.exists(path) and os.path.exists(path + '.gz') else open(path)); out = collections.Counter(); msgs = collections.defaultdict(list)
    for x in d['generalDiagnostics']:
        if x['severity'] != 'error': continue
        f = os.path.relpath(x['file'], root)
        k = (f, x['range']['start']['line'] + 1, x.get('rule', '?'))
        out[k] += 1; msgs[k].append(x['message'])
    out.msgs = msgs
    return out, d['summary']

def find_def(tree, t):
    def walk(node, cls):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if n.name == t['name'] and n.lineno == t['line'] and cls == t.get('cls'): return n
                r = walk(n, None)
                if r: return r
            elif isinstance(n, ast.ClassDef):
                r = walk(n, n.name)
                if r: return r
            else:
                r = walk(n, cls)
                if r: return r
    return walk(tree, None)

def patch(src, fn):
    lines = src.splitlines(keepends=True)
    off = [0]
    for l in lines: off.append(off[-1] + len(l))
    pos = lambda ln, col: off[ln - 1] + len(lines[ln - 1].encode('utf-8')[:col].decode('utf-8'))
    a = fn.args
    if a.kwarg: raise ValueError('has **kwargs')
    posargs = a.posonlyargs + a.args
    if a.kwonlyargs:
        last = a.kwonlyargs[-1]; ins, kind = f', {PROBE}', 'kwonly'
    elif a.vararg:
        last = a.vararg; ins, kind = f', {PROBE}', 'kwonly'
    elif a.defaults:
        last = posargs[-1]; ins, kind = f', *, {PROBE}', 'kwonly'
    elif posargs:
        last = posargs[-1]; ins, kind = f', {PROBE}', 'positional'
    else:
        last = None; kind = 'positional'
    if last is not None:
        end = last
        if a.kwonlyargs and last is a.kwonlyargs[-1] and a.kw_defaults[-1] is not None: end = a.kw_defaults[-1]
        elif last is not a.vararg and posargs and last is posargs[-1] and a.defaults: end = a.defaults[-1]
        p = pos(end.end_lineno, end.end_col_offset)
        return src[:p] + ins + src[p:], kind
    p = src.index('(', pos(fn.lineno, fn.col_offset))
    return src[:p + 1] + PROBE + src[p + 1:], kind

def run(t, base_keys):
    tag = f"{t['cls'] + '.' if t.get('cls') else ''}{t['name']}@{t['file'].replace('/', '_')}_{t['line']}"
    d = os.path.join(SCR, tag)
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(SCR, exist_ok=True)
    subprocess.run(['cp', '-c', '-R', BASE, d], check=True)
    shutil.rmtree(os.path.join(d, '.gitnexus'), ignore_errors=True)
    f = os.path.join(d, t['file']); src = open(f, encoding='utf-8').read()
    fn = find_def(ast.parse(src), t)
    if fn is None: return dict(t, error='declaration not found')
    try: new, kind = patch(src, fn)
    except ValueError as e: return dict(t, error=str(e))
    open(f, 'w', encoding='utf-8').write(new)
    diff = subprocess.run(['git', '-C', d, 'diff', '--', t['file']], capture_output=True, text=True).stdout
    os.makedirs(os.path.join(A, 'runs'), exist_ok=True)
    sites, secondary, removed, fa = {}, set(), {}, {}
    for plat in PLATFORMS:
        out = os.path.join(A, 'runs', f'{tag}.{plat}.pyright.json')
        subprocess.run([os.path.join(HERE, 'run_pyright.sh'), d, out, plat], check=True, capture_output=True)
        after, summ = keys(out, d); fa[plat] = summ['filesAnalyzed']
        bk = base_keys[plat]
        for k in after:
            if after[k] > bk.get(k, 0):
                if any(PROBE in m for m in after.msgs[k]):
                    sites.setdefault((k[0], k[1]), {'codes': set(), 'platforms': set()})
                    sites[(k[0], k[1])]['codes'].add(k[2]); sites[(k[0], k[1])]['platforms'].add(plat)
                else:
                    secondary.add((k[0], k[1], k[2], plat))
        removed[plat] = [list(k) for k in sorted(bk) if after.get(k, 0) < bk[k]]
    shutil.rmtree(d, ignore_errors=True)
    sl = [dict(file=f, line=l, code=','.join(sorted(v['codes'])), platforms=sorted(v['platforms'])) for (f, l), v in sorted(sites.items())]
    print(f"{tag}: {len(sl)} sites ({kind}; not on all platforms: {sum(1 for x in sl if len(x['platforms']) < len(PLATFORMS))}; secondary: {len(secondary)})", file=sys.stderr, flush=True)
    return dict(t, probe=kind, sites=sl, secondary=[list(x) for x in sorted(secondary)], removed=removed, files_analyzed=fa)

def main():
    targets = json.load(open(sys.argv[1])); par = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    base_keys = {}
    for plat in PLATFORMS:
        base_keys[plat], summ = keys(os.path.join(A, f'baseline-{plat}.json'), BASE)
        print(f'baseline {plat}: {len(base_keys[plat])} error keys ({summ})', file=sys.stderr, flush=True)
    with cf.ThreadPoolExecutor(par) as ex:
        res = list(ex.map(lambda t: run(t, base_keys), targets))
    json.dump(res, open(sys.argv[2], 'w'), indent=1)

if __name__ == '__main__':
    main()
