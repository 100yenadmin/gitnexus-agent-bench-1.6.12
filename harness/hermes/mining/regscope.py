#!/usr/bin/env python3
"""Regression scope for a Track H task: test files inside the touched packages' test dirs
(tests/<pkg>/, or tests/*.py for root modules) that reference a touched source module by its
dotted name or an import of its stem, read at the FIX commit. When that finds fewer than MIN files,
the scope widens one hop: tests referencing the source modules (same packages) that import a touched
module. If that still finds fewer than MIN files, the scope is every test file in the touched packages'
test dirs. Oracle files are excluded (they run as the oracle).
usage: regscope.py <repo or mirror> <fix_sha> <oracle files comma-sep> [out-file]  (prints the list)
"""
import re, subprocess, sys
repo, fix, oracle = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
g = lambda *a: subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True).stdout
def is_test(p):
    n = p.split('/')[-1]
    return p.startswith('tests/') or '/tests/' in p or n.startswith('test_')
src = [l.split('\t')[-1] for l in g('diff', '--name-status', f'{fix}^1', fix).splitlines()
       if l.endswith('.py') and not is_test(l.split('\t')[-1]) and l[0] != 'D']
pkgs = sorted({p.split('/')[0] if '/' in p else '' for p in src})
MIN = 20
def patterns(paths):
  pats = []
  for p in paths:
    mod = p[:-3].replace('/', '.')
    if mod.endswith('.__init__'): mod = mod[:-9]
    stem = mod.split('.')[-1]
    pats.append(re.escape(mod) + r'\b')
    if '.' in mod:  # from gateway import run_inbound_consumer
        parent = mod.rsplit('.', 1)[0]
        pats.append(rf'from\s+{re.escape(parent)}\s+import\s+[^\n]*\b{re.escape(stem)}\b')
    else:
        pats.append(rf'^\s*(?:import|from)\s+{re.escape(stem)}\b')
  return re.compile('|'.join(pats), re.M)
alltree = g('ls-tree', '-r', '--name-only', fix).split()
text = {}
def read(f):
    if f not in text: text[f] = g('show', f'{fix}:{f}')
    return text[f]
def scope(paths):
    rx = patterns(paths); out = []
    for f in alltree:
        if not f.startswith('tests/') or not (f.endswith('.py') and f.split('/')[-1].startswith('test_')) or f in oracle:
            continue
        top = f.split('/')[1] if f.count('/') >= 2 else ''
        if top in pkgs and rx.search(read(f)):
            out.append(f)
    return out
out = scope(src); hop = 0
if len(out) < MIN:
    rx0 = patterns(src)
    importers = [f for f in alltree if f.endswith('.py') and not is_test(f) and f not in src
                 and (f.split('/')[0] if '/' in f else '') in pkgs and rx0.search(read(f))]
    out = scope(src + importers); hop = len(importers)
if len(out) < MIN:
    out = [f for f in alltree if f.startswith('tests/') and f.split('/')[-1].startswith('test_') and f.endswith('.py')
           and f not in oracle and (f.split('/')[1] if f.count('/') >= 2 else '') in pkgs]
    hop = 'whole-dirs'
if len(sys.argv) > 4:
    open(sys.argv[4], 'w').write('\n'.join(out) + '\n')
print(' '.join(out))
print(f'# pkgs={pkgs} src={src} importers={hop} n={len(out)}', file=sys.stderr)
