#!/usr/bin/env python3
"""Join run rows (results.jsonl) with deterministic grades (regrade.jsonl) across run dirs; print per task x arm and
per arm summaries. Rows listed in --exclude (comma-separated run names, or <dirname>/<run>) are dropped (e.g. contaminated runs).
Usage: report.py <runs_dir>[,<runs_dir>...] [--exclude run1,run2] [--json out.json]
--json also writes per task x arm cells and per-arm summaries (clean = oracle and regression both pass).
"""
import json, os, sys
from collections import defaultdict

_H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(_H, "runner"), os.path.join(_H, "common")]
from bench import parse_claude  # noqa: E402  re-parse streams so every row uses the current parser (turn sums, CLI counts)

dirs = sys.argv[1].split(",")
excl = set(sys.argv[sys.argv.index("--exclude") + 1].split(",")) if "--exclude" in sys.argv else set()
rows = {}
for d in dirs:
    grades = {}
    rg = os.path.join(d, "regrade.jsonl")
    if os.path.exists(rg):
        for l in open(rg):
            g = json.loads(l); grades[g["run"]] = g
    for l in open(os.path.join(d, "results.jsonl")):
        r = json.loads(l)
        if r["run"] in excl or f"{os.path.basename(d.rstrip('/'))}/{r['run']}" in excl:  # "<dir>/<run>" scopes to one dir
            continue
        r["grade"] = grades.get(r["run"], {})
        st = os.path.join(d, "runs", r["run"], "stream.jsonl")
        if os.path.exists(st) and r.get("engine", "claude") == "claude":
            pc = parse_claude(st)
            r["turns"], r["gnx_cli"], r["cost_usd"] = pc["turns"], pc["gnx_cli"], pc["cost_usd"] or r.get("cost_usd")
        rows[(d, r["run"])] = r
cell = defaultdict(list)
for (d, n), r in rows.items():
    cell[(r["task"], r["arm"])].append(r)
fmt = lambda x, f="{:.2f}": "-" if x is None else f.format(x)
print(f"{'task':10} {'arm':9} {'n':>2} {'pass':>5} {'tsc':>4} {'cost$':>6} {'turns':>5} {'wall_s':>6} {'gnx':>4} {'skills':>6} {'churn':>9}")
arm_agg = defaultdict(lambda: defaultdict(list))
cells = []
for (task, arm), rs in sorted(cell.items()):
    passes = [r["grade"].get("oracle") for r in rs if "oracle" in r["grade"]]
    regs = [r["grade"].get("regression") for r in rs if "regression" in r["grade"]]
    cost = [r.get("cost_usd") or 0 for r in rs]
    turns = [r.get("turns") or 0 for r in rs]
    wall = [r.get("wall_s") or 0 for r in rs]
    gnx = [(r.get("gnx_calls") or 0) + (r.get("gnx_cli") or 0) for r in rs]
    sk = sum(1 for r in rs if r.get("skills"))
    churn = [(r.get("churn") or {}).get("ins", 0) + (r.get("churn") or {}).get("del", 0) for r in rs]
    m = lambda xs: sum(xs) / len(xs) if xs else None
    print(f"{task:10} {arm:9} {len(rs):2} {sum(bool(p) for p in passes)}/{len(passes):<3} {sum(bool(p) for p in regs)}/{len(regs):<2} "
          f"{fmt(m(cost)):>6} {fmt(m(turns), '{:.0f}'):>5} {fmt(m(wall), '{:.0f}'):>6} {fmt(m(gnx), '{:.1f}'):>4} {sk:>6} {fmt(m(churn), '{:.0f}'):>9}")
    a = arm_agg[arm]
    a["pass"] += [bool(p) for p in passes]; a["cost"] += cost; a["turns"] += turns; a["wall"] += wall; a["gnx"] += gnx
    clean = [bool(r["grade"].get("oracle")) and r["grade"].get("regression") is not False for r in rs if "oracle" in r["grade"]]
    a["clean"] += clean
    cells.append(dict(task=task, arm=arm, n=len(rs), graded=len(passes), oracle=sum(bool(p) for p in passes),
                      regression=sum(bool(p) for p in regs), regression_graded=len(regs), clean=sum(clean),
                      cost=m(cost), turns=m(turns), wall=m(wall), gnx=m(gnx), skills=sk, churn=m(churn),
                      runs=[r["run"] for r in rs]))
print("\nper arm:")
arms_out = {}
for arm, a in sorted(arm_agg.items()):
    n = len(a["cost"])
    arms_out[arm] = dict(runs=n, graded=len(a["pass"]), resolved=sum(a["pass"]), clean=sum(a["clean"]),
                         cost=sum(a["cost"]) / n, cost_total=sum(a["cost"]), turns=sum(a["turns"]) / n,
                         wall=sum(a["wall"]) / n, gnx=sum(a["gnx"]) / n)
    print(f"{arm:9} runs={n} resolved={sum(a['pass'])}/{len(a['pass'])} cost=${sum(a['cost'])/n:.2f} "
          f"turns={sum(a['turns'])/n:.0f} wall={sum(a['wall'])/n:.0f}s gnx_calls={sum(a['gnx'])/n:.1f}")
if "--json" in sys.argv:
    json.dump(dict(dirs=dirs, excluded=sorted(excl), cells=cells, arms=arms_out),
              open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
