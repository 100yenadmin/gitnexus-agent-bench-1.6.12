#!/usr/bin/env python3
"""Hand-made answers to test score_h_impact.py: perfect (exact GT lines, mixed path spellings: plain, ./-prefixed,
absolute under the task base), jitter (each line shifted +-1/+-2 where that does not collide with another GT line),
wrong (namesake/other-symbol references and declarations, none within +-2 of a GT site), partial (first half of GT +
2 wrong), and one missing answer file. Writes scorer-test/ in the bench runs layout (results.jsonl + runs/<run>/)."""
import json, os, shutil
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'impact')
T = f'{A}/scorer-test'
shutil.rmtree(T, ignore_errors=True); os.makedirs(f'{T}/runs')
gt = json.load(open(f'{A}/gt.json'))
R = [json.loads(l) for l in open(f'{A}/defs-final.jsonl')]
res = open(f'{T}/results.jsonl', 'w')
for g in gt:
    tgt = f"{g['cls'] + '.' if g['cls'] else ''}{g['name']}"
    sites = [(s['file'], s['line']) for s in g['sites']]
    near = lambda f, l: any(f == sf and abs(l - sl) <= 2 for sf, sl in sites)
    spell = lambda i, f: f if i % 3 == 0 else ('./' + f if i % 3 == 1 else f'{g_base}/{f}')
    g_base = _os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/h/impact')
    perfect = [dict(path=spell(i, f), line=l) for i, (f, l) in enumerate(sites)]
    jitter = []
    for i, (f, l) in enumerate(sites):
        d = [1, -1, 2, -2][i % 4]
        ok = all(not (f == sf and sl == l + d) for sf, sl in sites) and all(not (j['path'] == f and j['line'] == l + d) for j in jitter)
        jitter.append(dict(path=f, line=l + d if ok else l))
    wrong = [dict(path=r['file'], line=r['line']) for r in R if r['target'] == tgt and r['cls'] in ('residual', 'res-skip-attr', 'def')
             and not (r.get('defs') and [r['tfile'], r['tline']] in r['defs']) and not near(r['file'], r['line'])][:12] or [dict(path=g['file'], line=g['line'])]
    partial = [dict(path=f, line=l) for f, l in sites[:max(1, len(sites) // 2)]] + wrong[:2]
    for arm, ans in (('perfect', perfect), ('jitter', jitter), ('wrong', wrong), ('partial', partial)):
        run = f"{g['id']}-{arm}"; os.makedirs(f'{T}/runs/{run}')
        json.dump({'locations': ans}, open(f'{T}/runs/{run}/qa-answer.json', 'w'), indent=1)
        res.write(json.dumps(dict(run=run, task=g['id'], arm=arm, engine='test', cost_usd=0, wall_s=0)) + '\n')
run = 'h-impact-_norm-missing'; os.makedirs(f'{T}/runs/{run}')
res.write(json.dumps(dict(run=run, task='h-impact-_norm', arm='missing', engine='test')) + '\n')
