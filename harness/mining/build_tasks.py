#!/usr/bin/env python3
"""Assemble mining/tasks-o.json from validate.json + _statements/<id>.txt + META."""
import json, re, subprocess, sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402
M = benchenv.opt('MINING_DIR') or _os.path.join(benchenv.need('BENCH_ARTIFACTS'), 'mining')  # checkouts, logs, validate.json, oracle copies
ALIAS={'lcmx':('lcm-x','https://github.com/electricsheephq/lcm-x'),'worldos':('worldos','https://github.com/electricsheephq/WorldOS')}
META=json.load(open(sys.argv[1] if len(sys.argv)>1 else _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'meta.json')))
OUT=sys.argv[2] if len(sys.argv)>2 else f'{M}/tasks-o.json'
out=[]
for tid,meta in META.items():
    v=json.load(open(f'{M}/{tid}/validate.json'))
    alias,url=ALIAS[tid.split('-')[0]]
    st=open(f'{M}/_statements/{tid}.txt').read().strip()
    def summ(log):
        t=open(f'{M}/{tid}/logs/{log}').read()
        last=[l for l in t.strip().splitlines() if re.search(r'\b(passed|failed|error)\b',l)]
        return last[-1].strip('= ') if last else '?'
    bl=open(f'{M}/{tid}/logs/base_with_tests.log').read()
    errs=sorted(set(re.findall(r'^E\s+(\w+(?:Error|Exception))',bl,re.M)))
    rlog=meta.get('regression_log','fix_regression.log')
    rt=open(f'{M}/{tid}/logs/{rlog}').read()
    secs=float(re.search(r'secs=([\d.]+)',rt).group(1))
    out.append(dict(id=tid,repo_alias=alias,repo_url=url,base_sha=v['base'],fix_sha=v['fix'],pr_number=v['pr'],
        pr_url=f'{url}/pull/{v["pr"]}',**{'class':meta['class']},statement=st,setup_cmd=v['setup_cmd'],
        oracle_files=[f for f in v['tests'] if not f.endswith('/')],oracle_cmd=v['oracle_cmd'],
        regression_cmd=meta.get('regression_cmd',v['regression_cmd']),
        base_fail_evidence=f"base+hidden tests: {summ('base_with_tests.log')} (exit {v['base_rc']}; failure types: {', '.join(errs) or 'assert'})",
        fix_pass_evidence=f"fix run1: {summ('fix_oracle_run1.log')}; run2: {summ('fix_oracle_run2.log')}",
        regression_secs=round(secs,1),notes=meta.get('notes','')))
json.dump(out,open(OUT,'w'),indent=2)
print(len(out),'tasks written')
for t in out: print(t['id'],t['class'],t['pr_number'],len(t['statement'].split()),'words |',t['base_fail_evidence'][:90])
