#!/usr/bin/env python3
"""List first-parent fix candidates on origin/main after the live index commit (d62fbea7)."""
import json, subprocess, sys
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
S = _os.path.join(benchenv.opt('HERMES_MINING_DIR') or _os.path.join(benchenv.need('HERMES_ARTIFACTS'), 'mining'), '_src/hermes-agent.git')
IDX = 'd62fbea7e110c6008e1ffe1b226d1f593ba4bc28'
def g(*a): return subprocess.run(['git', '-C', S, *a], capture_output=True, text=True).stdout
def is_test(p):
    n = p.split('/')[-1]
    return p.startswith('tests/') or '/tests/' in p or n.startswith('test_') or n.endswith('_test.py')
shas = g('rev-list', '--first-parent', '--reverse', f'{IDX}..4787e4d56fc8d9265d4c7d3c0fe5accee86b4078').split()
out = []
for i, s in enumerate(shas, 1):
    subj = g('log', '-1', '--format=%s', s).strip()
    ns = g('diff', '--numstat', f'{s}^1', s).strip().splitlines()
    files = []
    tot = 0
    for l in ns:
        a, d, p = l.split('\t', 2)
        if a == '-': a = d = 0
        files.append((p, int(a), int(d))); tot += int(a) + int(d)
    src = [p for p, _, _ in files if p.endswith('.py') and not is_test(p)]
    tests = [p for p, _, _ in files if is_test(p) and p.endswith('.py')]
    other = [p for p, _, _ in files if not p.endswith('.py')]
    pk = sorted({p.split('/')[0] if '/' in p else '<root>' for p in src})
    out.append(dict(n=i, sha=s, subj=subj, tot=tot, src=src, tests=tests, other=other, pkgs=pk,
                    parents=len(g('log', '-1', '--format=%P', s).split())))
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for r in out:
    if r['src'] and r['tests'] and r['tot'] <= 400:
        print(f"{r['n']:3d} {r['sha'][:10]} tot={r['tot']:3d} pk={','.join(r['pkgs'])} src={len(r['src'])} t={len(r['tests'])} o={len(r['other'])} | {r['subj'][:90]}")
