#!/usr/bin/env python3
"""Engine-direct rename check: apply the GitNexus rename tool's own edit list (as returned to the Haiku H2 run,
dry_run=false, on that run's index) to a fresh APFS clone of the P2 base, then run the v2 TypeScript oracle.
Usage: apply_and_check.py   (writes $BENCH_ARTIFACTS/probes/p2/direct/engine-direct.json)
Needs the H2 runs' transcripts (runs-p2/runs/<task>-H2-t1/stream.jsonl), which are not published; the edit lists it
extracted are published as probes/p2/direct/engine-direct.json."""
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "common"))
import benchenv  # noqa: E402
B = benchenv.need('BENCH_ARTIFACTS')
BASE = os.path.join(benchenv.need('BENCH_ROOT'), 'tasks/gnxu/gnxu-base')
SCR = os.path.join(benchenv.need('BENCH_ROOT'), 'probe-scratch/p2-direct')
RENAME_GT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rename_gt_v2.mjs')
TASK = {'close': 'p2-close', 'declare': 'p2-declare', 'drainFinalizerPending': 'p2-drainFinalizerPending',
        'facts': 'p2-facts', 'getPhaseOutput': 'p2-getPhaseOutput', 'resolve': 'p2-resolve'}

def tool_result(stream):
    for line in open(stream):
        try: e = json.loads(line)
        except Exception: continue
        m = e.get('message') or {}
        if isinstance(m.get('content'), list):
            for c in m['content']:
                if c.get('type') == 'tool_result':
                    cont = c.get('content')
                    txt = cont if isinstance(cont, str) else ' '.join(x.get('text', '') for x in cont if isinstance(x, dict))
                    i = txt.find('{')
                    if '"old_name"' in txt and i >= 0:
                        try:
                            d, _ = json.JSONDecoder().raw_decode(txt[i:])
                            if d.get('changes'): return d
                        except Exception: pass

out = {}
os.makedirs(SCR, exist_ok=True)
for name, task in TASK.items():
    d = tool_result(f'{B}/runs-p2/runs/{task}-H2-t1/stream.jsonl')
    dst = os.path.join(SCR, name)
    if os.path.exists(dst): shutil.rmtree(dst)
    subprocess.run(['cp', '-c', '-R', BASE, dst], check=True)
    applied = skipped = 0
    for ch in d['changes']:
        p = os.path.join(dst, ch['file_path']); lines = open(p).read().split('\n')
        for ed in ch['edits']:
            i = ed['line'] - 1
            if 0 <= i < len(lines) and ed['old_text'].strip() and ed['old_text'].strip() in lines[i]:
                lines[i] = lines[i].replace(ed['old_text'].strip(), ed['new_text'].strip(), 1); applied += 1
            else:
                skipped += 1
        open(p, 'w').write('\n'.join(lines))
    r = subprocess.run([benchenv.opt('NODE_BIN', 'node'), RENAME_GT, 'check', f'{B}/probes/p2/spec_v2.json', name],
                       cwd=os.path.join(dst, 'gitnexus'), capture_output=True, text=True, timeout=1800)
    res = None
    for ln in r.stdout.splitlines()[::-1]:
        try: res = json.loads(ln); break
        except Exception: pass
    out[name] = dict(edits=sum(len(c['edits']) for c in d['changes']), applied=applied, skipped=skipped,
                     passed=(r.returncode == 0), checks=(res or {}).get('checks'), errors=(res or {}).get('errors'),
                     detail={k: (res or {}).get(k) for k in ('refs', 'old_idents', 'new_idents', 'decl_found')})
    print(name, json.dumps(out[name]), flush=True)
    shutil.rmtree(dst, ignore_errors=True)
json.dump(out, open(f'{B}/probes/p2/direct/engine-direct.json', 'w'), indent=1)
