#!/usr/bin/env python3
"""Un-blind the Codex grades: judge/<Q>.out.md (JSON keyed A-F) + judge/<Q>.map.json -> per-arm quality and cost."""
import json, os, re, sys
from collections import defaultdict

A = sys.argv[1]
J = os.path.join(A, "judge")
cost = {}
for f in ("runs-broad.jsonl", "runs-broad-f.jsonl"):
    p = os.path.join(A, "runs", f)
    if os.path.exists(p):
        for l in open(p):
            r = json.loads(l)
            g = sum(v for k, v in (r.get("tools") or {}).items() if k.startswith("mcp__gitnexus"))
            cost[(r["id"], r["arm"])] = (r["cost_usd"] or 0, r["num_turns"] or 0, g)
agg = defaultdict(lambda: defaultdict(float))
print(f"{'Q':3} {'arm':6} {'trial':5} {'corr':>4} {'comp':>4} {'cost':>7} {'turns':>5} {'gnx':>3}  errors")
for q in sorted(x[:-len('.map.json')] for x in os.listdir(J) if x.endswith(".map.json")):
    out = os.path.join(J, f"{q}.out.md")
    if not os.path.exists(out):
        print(q, "no judge output"); continue
    txt = open(out).read()
    m = re.search(r"\{.*\}", txt, re.S)
    grades = json.loads(m.group(0)) if m else {}
    mp = json.load(open(os.path.join(J, f"{q}.map.json")))["map"]
    for lab, cell in sorted(mp.items(), key=lambda kv: (kv[1]["arm"], kv[1]["id"])):
        g = grades.get(lab, {})
        c, t, gx = cost.get((cell["id"], cell["arm"]), (0, 0, 0))
        a = agg[cell["arm"]]
        a["n"] += 1; a["corr"] += g.get("correctness", 0); a["comp"] += g.get("completeness", 0)
        a["cost"] += c; a["turns"] += t; a["used"] += 1 if gx else 0
        errs = "; ".join(g.get("errors", []))[:150]
        print(f"{q:3} {cell['arm']:6} {cell['id'][-1]:5} {g.get('correctness','?'):>4} {g.get('completeness','?'):>4} "
              f"{c:7.3f} {t:5} {gx:3}  {errs}")
print("\n=== per arm (means) ===")
for arm, a in sorted(agg.items()):
    n = a["n"] or 1
    print(f"{arm:6} n={int(a['n'])} correctness={a['corr']/n:.1f} completeness={a['comp']/n:.1f} "
          f"cost=${a['cost']/n:.3f} turns={a['turns']/n:.1f} used_gitnexus={int(a['used'])}/{int(a['n'])}")
