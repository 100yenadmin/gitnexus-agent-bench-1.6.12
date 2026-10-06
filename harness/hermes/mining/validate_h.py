#!/usr/bin/env python3
"""Validate one mined Track H task (hermes-agent): mining checkout at base, deps, base+oracle must FAIL,
fix must PASS twice, regression must PASS at fix. Mirrors Track O's _scripts/validate.py.
usage: validate_h.py <id> <fix_sha> [--oracle-files a,b] [--regression 'tests/x/ tests/y/'] [--rerun]
"""
import argparse, json, os, re, subprocess, time
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = benchenv.need('HERMES_ARTIFACTS')
M = benchenv.opt('HERMES_MINING_DIR') or _os.path.join(A, 'mining')
S = '$HARNESS/hermes/mining'  # kept as a placeholder inside generated commands; benchenv exports HARNESS
IDX = 'd62fbea7e110c6008e1ffe1b226d1f593ba4bc28'
SETUP = f'bash {S}/hermes_setup.sh'
PYT = f'bash {S}/hermes_pytest.sh'
def sh(cmd, cwd, log=None, timeout=1800):
    t = time.time()
    try:
        p = subprocess.run(['bash', '-c', cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        rc, out = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out = 'timeout', (e.stdout or b'').decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
    if log:
        open(log, 'w').write(f'$ {cmd}\n# exit={rc} secs={time.time()-t:.1f}\n' + out)
    return rc, out, time.time() - t
def is_test(p):
    n = p.split('/')[-1]
    return p.startswith('tests/') or '/tests/' in p or n.startswith('test_') or n.endswith('_test.py')
def tail(out):
    return [l for l in out.splitlines() if re.match(r'^(FAILED|ERROR)', l)][:15] + out.strip().splitlines()[-1:]
ap = argparse.ArgumentParser()
ap.add_argument('id'); ap.add_argument('fix')
ap.add_argument('--oracle-files'); ap.add_argument('--regression'); ap.add_argument('--keep', action='store_true')
a = ap.parse_args()
d = f'{M}/{a.id}'; repo = f'{d}/repo'; logs = f'{d}/logs'
os.makedirs(logs, exist_ok=True)
res = json.load(open(f'{d}/validate.json')) if os.path.exists(f'{d}/validate.json') else {}
if not os.path.exists(repo):
    rc, out, _ = sh(f'bash {S}/mkcheckout.sh {repo} {a.fix}', M, f'{logs}/checkout.log')
    assert rc == 0, out
fix = sh(f'git rev-parse {a.fix}', repo)[1].strip()
base = sh(f'git rev-parse {fix}^1', repo)[1].strip()
res.update(id=a.id, fix=fix, base=base,
           dist_all=int(sh(f'git rev-list --count {IDX}..{base}', repo)[1]),
           dist_first_parent=int(sh(f'git rev-list --first-parent --count {IDX}..{base}', repo)[1]))
rc, out, _ = sh(f'git diff --name-status {base} {fix}', repo)
rows = [l.split('\t') for l in out.strip().splitlines() if l]
res['diff'] = [r[0] + ' ' + r[-1] for r in rows]
tests = sorted(r[-1] for r in rows if is_test(r[-1]) and r[-1].endswith('.py') and r[0][0] != 'D')
oracle = a.oracle_files.split(',') if a.oracle_files else [t for t in tests if t.split('/')[-1].startswith('test_')]
res['tests_changed'] = tests; res['oracle_files'] = oracle
ocmd = f'{PYT} -q {" ".join(oracle)}'
res['oracle_cmd'] = ocmd
lockdiff = bool(sh(f'git diff --quiet {base} {fix} -- uv.lock pyproject.toml || echo changed', repo)[1].strip())
res['lock_changed'] = lockdiff
# --- base + oracle files: must FAIL
sh(f'git checkout -q --detach {base} && git clean -fdq', repo)
rc, out, _ = sh(SETUP, repo, f'{logs}/setup.log'); res['setup_rc'] = rc
for f in oracle:
    sh(f'mkdir -p "$(dirname {f})" && git show {fix}:{f} > {f}', repo)
rc, out, s = sh(ocmd, repo, f'{logs}/base_with_tests.log')
res.update(base_rc=rc, base_secs=round(s, 1), base_tail=tail(out),
           base_import_err=bool(re.search(r'ImportError|ModuleNotFoundError|cannot import name|has no attribute|unexpected keyword argument|NameError', out)))
sh('git checkout -q -- . && git clean -fdq', repo)
# --- fix: oracle PASSES twice, regression PASSES
sh(f'git checkout -q --detach {fix}', repo)
if lockdiff:
    sh(SETUP, repo, f'{logs}/setup_fix.log')
for i in (1, 2):
    rc, out, s = sh(ocmd, repo, f'{logs}/fix_oracle_run{i}.log')
    res[f'fix_rc{i}'] = rc; res[f'fix_secs{i}'] = round(s, 1); res[f'fix_tail{i}'] = out.strip().splitlines()[-1:]
if a.regression:
    rcmd = f'{PYT} --suite {a.regression} -q'
    res['regression_cmd'] = rcmd
    rc, out, s = sh(rcmd, repo, f'{logs}/fix_regression.log', timeout=1500)
    res.update(reg_rc=rc, reg_secs=round(s, 1), reg_tail=out.strip().splitlines()[-12:])
# --- back to base; keep the fix-version oracle files
sh(f'git checkout -q --detach {base}', repo)
if lockdiff:
    sh(SETUP, repo, f'{logs}/setup_base_again.log')
for f in oracle:
    os.makedirs(os.path.dirname(f'{d}/oracle/{f}'), exist_ok=True)
    sh(f'git show {fix}:{f} > "{d}/oracle/{f}"', repo)
res['final_status'] = sh('git status --porcelain --untracked-files=normal; git rev-parse HEAD', repo)[1].strip()
json.dump(res, open(f'{d}/validate.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('diff',)}, indent=1))
