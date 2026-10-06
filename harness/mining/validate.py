#!/usr/bin/env python3
"""Validate one mined task: clone, base+tests must fail, fix must pass twice, regression passes.
usage: validate.py <repo_alias> <id> <pr> [--oracle-files a,b] [--oracle-cmd CMD] [--regression-cmd CMD] [--keep-on-fail]
"""
import argparse, json, os, re, shutil, subprocess, sys, time
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
M = benchenv.opt('MINING_DIR') or _os.path.join(benchenv.need('BENCH_ARTIFACTS'), 'mining')  # checkouts, logs, validate.json, oracle copies
# Commands keep the literal $HARNESS placeholder (benchenv exports HARNESS, so bash expands it here; task loaders expand it too).
S = '$HARNESS/mining'
REPOS = {
  'lcm-x': dict(gh='electricsheephq/lcm-x', src=f'{M}/_src/lcm-x',
     setup=f'bash {S}/lcmx_setup.sh',
     oracle=f'bash {S}/lcmx_pytest.sh -q {{files}}',
     regression=f'bash {S}/lcmx_pytest.sh tests/ -q -n 8'),
  'worldos': dict(gh='electricsheephq/WorldOS', src=f'{M}/_src/worldos',
     setup='uv sync -q --directory servers/engine --group dev',
     oracle='uv run -q --directory servers/engine --group dev pytest -q -p no:cacheprovider {files}',
     regression='uv run -q --directory servers/engine --group dev pytest -q -p no:cacheprovider'),
}
def sh(cmd, cwd, log=None, timeout=1800):
    t=time.time()
    p=subprocess.run(['bash','-c',cmd],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    out=p.stdout+p.stderr
    if log:
        open(log,'w').write(f'$ {cmd}\n# exit={p.returncode} secs={time.time()-t:.1f}\n'+out)
    return p.returncode, out, time.time()-t
def is_test(p):
    return '/tests/' in p or p.startswith('tests/') or p.split('/')[-1].startswith('test_') or 'integration_tests/' in p
ap=argparse.ArgumentParser()
ap.add_argument('alias'); ap.add_argument('id'); ap.add_argument('pr',type=int)
ap.add_argument('--oracle-files'); ap.add_argument('--oracle-cmd'); ap.add_argument('--regression-cmd')
ap.add_argument('--setup-cmd'); ap.add_argument('--strip', default='')
a=ap.parse_args()
R=REPOS[a.alias]; d=f'{M}/{a.id}'; repo=f'{d}/repo'; logs=f'{d}/logs'
info=json.loads(subprocess.run(['gh','pr','view',str(a.pr),'-R',R['gh'],'--json','mergeCommit,files,url,title,commits'],capture_output=True,text=True).stdout)
fix=info['mergeCommit']['oid']
if os.path.exists(d): shutil.rmtree(d)
os.makedirs(logs)
sh(f'git clone -q --no-local {R["src"]} {repo} && git remote set-url origin https://github.com/{R["gh"]}.git', M)
rc,out,_=sh(f'git rev-parse {fix}^1 && git rev-list --count {fix}^1..{fix} && git log -1 --format=%P {fix}', repo)
base=out.split()[0]
prfiles={f['path'] for f in info['files']}
rc,out,_=sh(f'git diff --name-status {base} {fix}', repo)
difffiles={l.split('\t')[-1] for l in out.strip().split('\n') if l}
mism=sorted(prfiles ^ difffiles)
tests=sorted(f for f in difffiles if is_test(f))
oracle_files=a.oracle_files.split(',') if a.oracle_files else [f for f in tests if f.endswith('.py') and f.split('/')[-1].startswith('test_')]
def fmt(files):
    if a.alias=='worldos':
        files=[f[len('servers/engine/'):] if f.startswith('servers/engine/') else '../../'+f for f in files]
    return ' '.join(files)
ocmd=a.oracle_cmd or R['oracle'].format(files=fmt(oracle_files))
rcmd=a.regression_cmd or R['regression']
scmd=a.setup_cmd or R['setup']
res=dict(id=a.id,pr=a.pr,base=base,fix=fix,mismatch=mism,tests=tests,oracle_files=oracle_files,oracle_cmd=ocmd,regression_cmd=rcmd,setup_cmd=scmd)
sh(f'git checkout -q --detach {base}', repo)
rc,out,s=sh(scmd, repo, f'{logs}/setup.log'); res['setup_rc']=rc
# base + tests
existing=[]
for f in tests:
    r2,_,_=sh(f'git cat-file -e {fix}:{f}', repo)
    if r2==0: sh(f'mkdir -p "$(dirname {f})" && git show {fix}:{f} > {f}', repo)
    else: sh(f'rm -f {f}', repo)
rc,out,s=sh(ocmd, repo, f'{logs}/base_with_tests.log'); res['base_rc']=rc; res['base_secs']=round(s,1)
res['base_tail']=[l for l in out.splitlines() if re.match(r'^(FAILED|ERROR)',l)][:15]+out.strip().splitlines()[-1:]
res['base_import_err']=bool(re.search(r'ImportError|ModuleNotFoundError|cannot import name|has no attribute|unexpected keyword argument|NameError',out))
sh('git checkout -q -- . && git clean -fdq', repo)
sh(f'git checkout -q --detach {fix}', repo)
for i in (1,2):
    rc,out,s=sh(ocmd, repo, f'{logs}/fix_oracle_run{i}.log'); res[f'fix_rc{i}']=rc; res[f'fix_secs{i}']=round(s,1); res[f'fix_tail{i}']=out.strip().splitlines()[-1:]
rc,out,s=sh(rcmd, repo, f'{logs}/fix_regression.log', timeout=1200); res['reg_rc']=rc; res['reg_secs']=round(s,1); res['reg_tail']=out.strip().splitlines()[-1:]
# restore base, remove hidden tests
sh(f'git checkout -q --detach {base}', repo)
os.makedirs(f'{d}/oracle',exist_ok=True)
for f in tests:
    r2,_,_=sh(f'git cat-file -e {fix}:{f}', repo)
    if r2==0: sh(f'mkdir -p "$(dirname {d}/oracle/{f})" && git show {fix}:{f} > "{d}/oracle/{f}"', repo)
rc,out,_=sh('git status --porcelain && git branch -a', repo); res['final_status']=out.strip()
json.dump(res,open(f'{d}/validate.json','w'),indent=1)
print(json.dumps(res,indent=1))
