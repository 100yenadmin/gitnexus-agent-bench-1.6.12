#!/usr/bin/env python3
"""Replace each raw per-run pyright JSON in runs/ (~9.5 MB each) by a compact diff vs its platform baseline:
runs/<tag>[.<platform>].pyright-diff.json = {summary, added: [{file,line,rule,message}], removed_keys}. Raw baselines
are kept gzipped (baseline-<platform>.json.gz)."""
import json, os, glob, collections, gzip, shutil
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'impact')
BASE = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact')
SCR = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact-scratch')
def load(path, root):
    d = json.load(open(path)); c = collections.Counter(); m = collections.defaultdict(list)
    for x in d['generalDiagnostics']:
        if x['severity'] != 'error': continue
        k = (os.path.relpath(x['file'], root), x['range']['start']['line'] + 1, x.get('rule', '?')); c[k] += 1; m[k].append(x['message'])
    return c, m, d['summary']
bases = {p: load(f'{A}/baseline-{p}.json', BASE) for p in ('Darwin', 'Linux', 'Windows')}
for pj in sorted(glob.glob(f'{A}/runs/*.pyright.json')):
    name = os.path.basename(pj)[:-len('.pyright.json')]
    tag, plat = (name.rsplit('.', 1) if name.rsplit('.', 1)[-1] in bases else (name, 'Darwin'))
    if os.path.getsize(pj) == 0: os.remove(pj); continue
    c, m, s = load(pj, f'{SCR}/{tag}'); bc = bases[plat][0]
    added = [dict(file=k[0], line=k[1], rule=k[2], message=msg) for k in sorted(c) if c[k] > bc.get(k, 0) for msg in m[k]]
    removed = [list(k) for k in sorted(bc) if c.get(k, 0) < bc[k]]
    json.dump(dict(platform=plat, summary=s, added=added, removed_keys=removed), open(f'{A}/runs/{tag}.{plat}.pyright-diff.json', 'w'), indent=1)
    os.remove(pj)
    if os.path.exists(pj + '.err') and os.path.getsize(pj + '.err') == 0: os.remove(pj + '.err')
for p in ('Darwin', 'Linux', 'Windows'):
    src = os.path.realpath(f'{A}/baseline-{p}.json')
    with open(src, 'rb') as fi, gzip.open(f'{A}/baseline-{p}.json.gz', 'wb') as fo: shutil.copyfileobj(fi, fo)
print('done')
