#!/usr/bin/env python3
"""Assemble mining/tasks-h.json (+ tasks-h-alternates.json) and artifacts/tasks-h-bench.json
(+ tasks-h-alternates-bench.json) from <id>/validate.json + _statements/<id>.txt + meta. Mirrors Track O's build_tasks.py."""
import json, re, shlex
import os as _os, sys as _sys
_HARNESS = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path[:0] = [_os.path.join(_HARNESS, "runner"), _os.path.join(_HARNESS, "common")]
import benchenv  # noqa: E402
A = benchenv.need('HERMES_ARTIFACTS')
M = benchenv.opt('HERMES_MINING_DIR') or _os.path.join(A, 'mining')
S = '$HARNESS/hermes/mining'  # kept as a placeholder inside generated commands; benchenv exports HARNESS
URL = 'https://github.com/NousResearch/hermes-agent'
PYT = f'bash {S}/hermes_pytest.sh'
SETUP = f'bash {S}/hermes_setup.sh'
HINT = ("To run tests, use the hermetic pytest wrapper from the repository root: "
        f"`{PYT} <pytest args>` (for example `{PYT} -q tests/agent/test_x.py`); it runs the checkout's prepared "
        "`.venv` in a scrubbed environment with a temporary HOME. The repository's own `scripts/run_tests.sh <paths>` "
        "also works (HERMES_PYTHON points at the checkout's `.venv/bin/python`).")
def summ(tid, log):
    t = open(f'{M}/{tid}/logs/{log}').read()
    last = [l for l in t.strip().splitlines() if re.search(r'\b(passed|failed|error)\b', l) and not l.startswith(('$', '#'))]
    return last[-1].strip('= ') if last else '?'
def build(meta_file, mining_out, bench_out):
    meta = json.load(open(meta_file)); out, bench = [], []
    for tid, mt in meta.items():
        v = json.load(open(f'{M}/{tid}/validate.json'))
        st = open(f'{M}/_statements/{tid}.txt').read().strip()
        bl = open(f'{M}/{tid}/logs/base_with_tests.log').read()
        errs = sorted(set(re.findall(r'^E\s+(\w+(?:Error|Exception))', bl, re.M)))
        rlog = open(f'{M}/{tid}/logs/fix_regression.log').read()
        m = re.search(r'secs=([\d.]+)', rlog); rsecs = float(m.group(1)) if m else -1.0
        rfiles = f'{M}/{tid}/regression-files.txt'
        rfiles_ph = f'$HERMES_ARTIFACTS/mining/{tid}/regression-files.txt' if not benchenv.opt('HERMES_MINING_DIR') else rfiles
        nfiles = len([l for l in open(rfiles) if l.strip()])
        desel = ''.join(' ' + shlex.quote('--deselect=' + d) for d in mt.get('deselect', []))
        rcmd = f'{PYT} --suite --files-from {rfiles_ph} -q{desel}'
        ocmd = v['oracle_cmd']
        pr = mt['pr']
        out.append(dict(id=tid, repo_alias='hermes-agent', repo_url=URL, base_sha=v['base'], fix_sha=v['fix'],
            pr_number=pr, pr_url=f'{URL}/pull/{pr}', **{'class': mt['class']}, statement=st, setup_cmd=SETUP,
            oracle_files=v['oracle_files'], oracle_cmd=ocmd, regression_cmd=rcmd,
            base_fail_evidence=f"base+hidden tests: {summ(tid, 'base_with_tests.log')} (exit {v['base_rc']}; failure types: {', '.join(errs) or 'assert'})",
            fix_pass_evidence=f"fix run1: {summ(tid, 'fix_oracle_run1.log')}; run2: {summ(tid, 'fix_oracle_run2.log')}",
            regression_secs=round(rsecs, 1), regression_files=nfiles,
            regression_evidence=f"fix: {summ(tid, 'fix_regression.log')} ({nfiles} files, per-file runner)",
            base_distance=dict(first_parent=v['dist_first_parent'], all_commits=v['dist_all'],
                               note='commits from d62fbea7 (live index) to base_sha'),
            notes=mt.get('notes', '')))
        bench.append(dict(id=tid, track='H', **{'class': mt['class']}, repo='hermes-agent', pr=f'{URL}/pull/{pr}',
            base=f'$BENCH_ROOT/tasks/h/{tid}', owner_md=True,
            task=st + '\n\n' + HINT,
            oracle=dict(files=[dict(src=f'$HERMES_ARTIFACTS/mining/{tid}/oracle/{f}', dst=f) for f in v['oracle_files']], cmd=ocmd, timeout=1500),
            regression=dict(cmd=rcmd, timeout=2400, rerun=f'{PYT} {{IDS}} -q'),
            env={'HERMES_PYTHON': '{RUNDIR}/.venv/bin/python'}))
    json.dump(out, open(mining_out, 'w'), indent=2)
    json.dump(bench, open(bench_out, 'w'), indent=1)
    for t in out:
        print(t['id'], t['class'], t['pr_number'], len(t['statement'].split()), 'words | d=', t['base_distance']['first_parent'],
              '|', t['base_fail_evidence'][:70], '| reg', t['regression_secs'], 's')
_HERE = _os.path.dirname(_os.path.abspath(__file__))
build(f'{_HERE}/meta.json', f'{M}/tasks-h.json', f'{A}/tasks-h-bench.json')
build(f'{_HERE}/meta_alternates.json', f'{M}/tasks-h-alternates.json', f'{A}/tasks-h-alternates-bench.json')
