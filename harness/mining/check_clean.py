#!/usr/bin/env python3
"""Verify each task checkout in tasks-o.json is bench-ready."""
import json, os, subprocess
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
M = benchenv.opt('MINING_DIR') or _os.path.join(benchenv.need('BENCH_ARTIFACTS'), 'mining')  # checkouts, logs, validate.json, oracle copies
def g(repo,*a): return subprocess.run(['git','-C',repo,*a],capture_output=True,text=True).stdout.strip()
ok_all=True
import sys
for t in json.load(open(f'{M}/'+(sys.argv[1] if len(sys.argv)>1 else 'tasks-o.json'))):
    repo=f"{M}/{t['id']}/repo"; probs=[]
    if g(repo,'rev-parse','HEAD')!=t['base_sha']: probs.append('HEAD!=base')
    if g(repo,'status','--porcelain'): probs.append('dirty')
    for f in t['oracle_files']:
        inbase=subprocess.run(['git','-C',repo,'cat-file','-e',f"{t['base_sha']}:{f}"]).returncode==0
        p=f'{repo}/{f}'
        if inbase:
            if g(repo,'diff','--quiet',t['base_sha'],'--',f)!='' : probs.append(f'modified {f}')
            if open(p,'rb').read()==open(f"{M}/{t['id']}/oracle/{f}",'rb').read(): probs.append(f'hidden version present {f}')
        elif os.path.exists(p): probs.append(f'new test present {f}')
        if not os.path.exists(f"{M}/{t['id']}/oracle/{f}"): probs.append(f'oracle copy missing {f}')
    br=g(repo,'for-each-ref','--format=%(refname)')
    extra=[r for r in br.split() if not r.startswith('refs/tags/') and r not in ('refs/heads/main','refs/remotes/origin/HEAD','refs/remotes/origin/main')]
    if extra: probs.append(f'extra refs {extra}')
    venv=f'{repo}/.venv' if t['repo_alias']=='lcm-x' else f'{repo}/servers/engine/.venv'
    if not os.path.isdir(venv): probs.append('deps missing')
    if t['repo_alias']=='lcm-x' and not os.path.exists(f'{repo}/agent/context_engine.py'): probs.append('agent stub missing')
    print(t['id'],'OK' if not probs else probs); ok_all&=not probs
print('ALL OK' if ok_all else 'PROBLEMS')
