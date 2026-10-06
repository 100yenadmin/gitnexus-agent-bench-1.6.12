#!/usr/bin/env python3
"""Un-blind round-2 grades (judge2.py): judge-<set>/<Q>.out.md + <Q>.map.json -> per-arm quality and cost."""
import json, os, re, sys
from collections import defaultdict

A = sys.argv[1]
SRC = {"codex": os.path.join(A, "runs-codex", "runs-codex.jsonl"), "aug": os.path.join(A, "runs", "runs-aug.jsonl")}
for name, src in SRC.items():
    J = os.path.join(A, f"judge-{name}")
    if not os.path.isdir(J):
        continue
    cost = {}
    for l in open(src):
        r = json.loads(l)
        if r.get("rc") == 0:
            cost[(r["id"], r["arm"])] = r.get("cost_usd") or 0
    agg = defaultdict(lambda: defaultdict(float))
    print(f"\n##### set={name}")
    print(f"{'Q':3} {'arm':6} {'trial':5} {'corr':>4} {'comp':>4} {'cost':>7}  errors")
    for q in sorted(x[:-len(".map.json")] for x in os.listdir(J) if x.endswith(".map.json")):
        out = os.path.join(J, f"{q}.out.md")
        txt = open(out).read() if os.path.exists(out) else ""
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            print(q, "no judge output"); continue
        grades = json.loads(m.group(0))
        mp = json.load(open(os.path.join(J, f"{q}.map.json")))["map"]
        for lab, cell in sorted(mp.items(), key=lambda kv: (kv[1]["arm"], kv[1]["id"])):
            g = grades.get(lab, {})
            c = cost.get((cell["id"], cell["arm"]), 0)
            a = agg[cell["arm"]]
            a["n"] += 1; a["corr"] += g.get("correctness", 0); a["comp"] += g.get("completeness", 0); a["cost"] += c
            print(f"{q:3} {cell['arm']:6} {cell['id'][-1]:5} {g.get('correctness','?'):>4} {g.get('completeness','?'):>4} "
                  f"{c:7.3f}  {'; '.join(g.get('errors', []))[:140]}")
    print(f"=== {name}: per arm (means)")
    for arm, a in sorted(agg.items()):
        n = a["n"] or 1
        print(f"{arm:6} n={int(a['n'])} correctness={a['corr']/n:.1f} completeness={a['comp']/n:.1f} cost=${a['cost']/n:.3f}")
