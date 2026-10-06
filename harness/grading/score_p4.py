#!/usr/bin/env python3
"""Score the seeded taint probe: a reported flow matches a seeded flow when its source is in the seeded module within
+-2 lines of the seeded source line (sources are distinct; S1 and decoy D1 share a sink). Decoy hits: D1 by source line,
D2 by sink line. Reports elsewhere are counted as 'other' (pre-existing code; listed, not scored).
Usage: score_p4.py <tasks-p4.json> <runs_dir>[,<runs_dir>...]"""
import json, os, sys
from collections import defaultdict
_H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(_H, "runner"), os.path.join(_H, "common")]
import benchenv  # noqa: E402  (also lets task files use the $BENCH_ROOT/... placeholders)
from bench import parse_claude  # noqa: E402

def loc(x):
    try:
        p = str(x.get("path", "")).strip().lstrip("./"); i = p.find("gitnexus/src/")
        return (p[i:] if i >= 0 else p), int(x.get("line"))
    except Exception:
        return None, None

def main():
    task = benchenv.load_tasks(sys.argv[1])[0]; gt = json.load(open(task["gt"])); F = gt["file"]
    agg = defaultdict(lambda: defaultdict(list)); per_run = []
    for rd in sys.argv[2].split(","):
        for l in open(os.path.join(rd, "results.jsonl")):
            r = json.loads(l)
            if r.get("task") != task["id"]: continue
            try: flows = json.load(open(os.path.join(rd, "runs", r["run"], "qa-answer.json"))).get("flows") or []
            except Exception: flows = None
            hit, d1, d2, other = set(), 0, 0, []
            for f in flows or []:
                sp, sl = loc(f.get("source") or {}); kp, kl = loc(f.get("sink") or {})
                m = [g["id"] for g in gt["flows"] if sp == F and sl is not None and abs(sl - g["source_line"]) <= 2]
                if m: hit.update(m); continue
                if sp == F and sl is not None and abs(sl - gt["decoys"][0]["source_line"]) <= 2: d1 += 1; continue
                if kp == F and kl is not None and abs(kl - gt["decoys"][1]["sink_line"]) <= 2: d2 += 1; continue
                if kp == F and kl is not None and any(abs(kl - g["sink_line"]) <= 2 for g in gt["flows"]):
                    # right sink, source not pinned to the seeded handler: credit by sink when unambiguous (S2, S3)
                    s = [g["id"] for g in gt["flows"] if abs(kl - g["sink_line"]) <= 2 and g["id"] != "S1"]
                    if s: hit.update(s); continue
                other.append(f"{sp}:{sl}->{kp}:{kl}")
            st = os.path.join(rd, "runs", r["run"], "stream.jsonl")
            if r.get("engine") == "claude" and os.path.exists(st):
                pc = parse_claude(st); r["turns"], r["gnx_cli"] = pc["turns"], pc["gnx_cli"]
            gnx = (r.get("gnx_calls") or 0) + (r.get("gnx_cli") or 0)
            g = agg[r["arm"]]
            g["recall"].append(len(hit) / 3); g["d1"].append(d1); g["d2"].append(d2); g["other"].append(len(other))
            g["cost"].append(r.get("cost_usd") or 0); g["turns"].append(r.get("turns") or 0); g["gnx"].append(gnx)
            per_run.append(dict(run=r["run"], arm=r["arm"], found=sorted(hit), d1=d1, d2=d2, other=other, missing=flows is None,
                                cost=r.get("cost_usd") or 0, turns=r.get("turns") or 0, gnx=gnx))
            print(f"{r['run']:28} found={sorted(hit)} decoyD1={d1} decoyD2={d2} other={len(other)} {other[:3]} "
                  f"{'MISSING' if flows is None else ''} cost={r.get('cost_usd') or 0:.2f} turns={r.get('turns')} gnx={gnx}")
    m = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    print("\nper arm:")
    for arm, g in sorted(agg.items()):
        print(f"{arm:5} n={len(g['recall'])} recall={m(g['recall']):.2f} decoyD1/run={m(g['d1']):.2f} decoyD2/run={m(g['d2']):.2f} "
              f"other/run={m(g['other']):.1f} cost=${m(g['cost']):.2f} turns={m(g['turns']):.1f} gnx={m(g['gnx']):.1f}")

    if "--json" in sys.argv:
        json.dump(dict(per_run=per_run, arms={(k if isinstance(k, str) else "|".join(k)): dict({x: (sum(v) / len(v) if v else None) for x, v in g.items()}, n=len(next(iter(g.values()))))
                                              for k, g in agg.items()}),
                  open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)

if __name__ == "__main__":
    main()
