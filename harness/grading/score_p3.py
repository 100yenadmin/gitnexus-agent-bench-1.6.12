#!/usr/bin/env python3
"""Score P3 (route map / tool map / API consumers) answers against probes/p3/gt.json: set recall/precision per run.
Routes match on (METHOD, path); a ground-truth ALL route matches any method for its path. Usage: score_p3.py <tasks> <runs>"""
import json, os, sys
from collections import defaultdict
_H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(_H, "runner"), os.path.join(_H, "common")]
import benchenv  # noqa: E402  (also lets task files use the $BENCH_ROOT/... placeholders)
from bench import parse_claude  # noqa: E402

def norm_route(m, p):
    m, p = str(m).upper().strip(), str(p).strip()
    if m == "GET" and ("(?!" in p or p.strip("/") in ("*", "(.*)", ".*") or "spa fallback" in p.lower()):
        return ("GET", "/<SPA fallback regex>")  # the regex catch-all route (api.ts:296), however it is spelled
    return (m, "/" + p.strip("/"))

def main():
    tasks = {t["id"]: t for t in benchenv.load_tasks(sys.argv[1])}
    gt = json.load(open(next(iter(tasks.values()))["gt"]))
    agg = defaultdict(lambda: defaultdict(list)); per_run = []
    print(f"{'run':40} {'gt':>3} {'ans':>4} {'tp':>3} {'R':>5} {'P':>5} {'cost':>5} {'turns':>5} {'gnx':>4}  missed/extra")
    excl = set(sys.argv[sys.argv.index("--exclude") + 1].split(",")) if "--exclude" in sys.argv else set()
    for rd in sys.argv[2].split(","):
        for l in open(os.path.join(rd, "results.jsonl")):
            r = json.loads(l); t = tasks.get(r.get("task"))
            if not t or f"{os.path.basename(rd.rstrip('/'))}/{r['run']}" in excl: continue
            try: a = json.load(open(os.path.join(rd, "runs", r["run"], "qa-answer.json")))
            except Exception: a = None
            if t["sub"] == "routes":
                g = {norm_route(x["method"], x["path"]) for x in gt["routes"]}
                ans = {norm_route(x.get("method"), x.get("path")) for x in (a or {}).get("routes", []) if isinstance(x, dict)}
                alls = {p for m, p in g if m == "ALL"}
                ans = {(("ALL", p) if p in alls else (m, p)) for m, p in ans}
            elif t["sub"] == "tools":
                g = set(gt["tools"]); ans = {str(x).strip() for x in (a or {}).get("tools", [])}
            else:
                g = set(gt["consumers"][t["endpoint"]]["files"])
                ans = set()
                for x in (a or {}).get("files", []):
                    x = str(x).strip().lstrip("./"); i = x.find("gitnexus-web/src/"); ans.add(x[i:] if i >= 0 else "gitnexus-web/src/" + x.split("src/")[-1])
            tp = len(g & ans); R = tp / len(g); P = tp / len(ans) if ans else 0.0
            st = os.path.join(rd, "runs", r["run"], "stream.jsonl")
            if r.get("engine") == "claude" and os.path.exists(st):
                pc = parse_claude(st); r["turns"], r["gnx_cli"] = pc["turns"], pc["gnx_cli"]
            gnx = (r.get("gnx_calls") or 0) + (r.get("gnx_cli") or 0)
            ag = agg[(t["sub"], r["arm"])]
            for k, v in (("R", R), ("P", P), ("perfect", int(R == 1 and P == 1)), ("cost", r.get("cost_usd") or 0), ("turns", r.get("turns") or 0), ("gnx", gnx)):
                ag[k].append(v)
            per_run.append(dict(run=r["run"], task=r["task"], sub=t["sub"], arm=r["arm"], gt=len(g), ans=(len(ans) if a is not None else None), tp=tp,
                                recall=R, precision=P, cost=r.get("cost_usd") or 0, turns=r.get("turns") or 0, gnx=gnx,
                                missed=sorted(map(str, g - ans)), extra=sorted(map(str, ans - g))))
            ex = sorted(map(str, g - ans))[:1] + sorted(map(str, ans - g))[:1]
            print(f"{r['run']:40} {len(g):3} {len(ans) if a is not None else '-':>4} {tp:3} {R:5.2f} {P:5.2f} {r.get('cost_usd') or 0:5.2f} {r.get('turns') or 0:5} {gnx:4}  {ex}")
    m = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    print("\nper question type x arm:")
    for (sub, arm), g in sorted(agg.items()):
        print(f"{sub:10} {arm:4} n={len(g['R'])} recall={m(g['R']):.2f} precision={m(g['P']):.2f} perfect={m(g['perfect']):.2f} cost=${m(g['cost']):.2f} turns={m(g['turns']):.1f} gnx={m(g['gnx']):.1f}")

    if "--json" in sys.argv:
        json.dump(dict(per_run=per_run, arms={(k if isinstance(k, str) else "|".join(k)): dict({x: (sum(v) / len(v) if v else None) for x, v in g.items()}, n=len(next(iter(g.values()))))
                                              for k, g in agg.items()}),
                  open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)

if __name__ == "__main__":
    main()
