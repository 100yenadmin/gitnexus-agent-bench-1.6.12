#!/usr/bin/env python3
"""Score impact-probe answers against type-checker ground truth (probes/p1/gt.json): a listed location matches a
ground-truth error site on the same path within +-2 lines (one-to-one, nearest first). Missing/unparseable answers
score as empty (counted, not dropped). Usage: score_p1.py <tasks-p1.json> <runs_dir>[,<runs_dir>...]
"""
import json, os, posixpath, sys
from collections import defaultdict

_H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(_H, "runner"), os.path.join(_H, "common")]
import benchenv  # noqa: E402  (also lets task files use the $BENCH_ROOT/... placeholders)
from bench import parse_claude  # noqa: E402

TOL = 2


def norm(p):
    p = posixpath.normpath(str(p or "").strip().lstrip("./"))
    i = p.find("gitnexus/src/")
    return p[i:] if i >= 0 else p


def load(path):
    try:
        d = json.load(open(path))
    except Exception:
        return None
    out = set()
    for x in d.get("locations") or []:
        try:
            out.add((norm(x.get("path")), int(x.get("line"))))
        except Exception:
            continue
    return sorted(out)


def match(ans, gt):
    pairs = sorted((abs(al - gl), ai, gi) for ai, (ap, al) in enumerate(ans) for gi, (gp, gl) in enumerate(gt)
                   if ap == gp and abs(al - gl) <= TOL)
    ua, ug, tp = set(), set(), 0
    for _d, ai, gi in pairs:
        if ai not in ua and gi not in ug:
            ua.add(ai); ug.add(gi); tp += 1
    return tp, [gt[i] for i in range(len(gt)) if i not in ug], [ans[i] for i in range(len(ans)) if i not in ua]


def main():
    tasks = {t["id"]: t for t in benchenv.load_tasks(sys.argv[1])}
    gts = {}
    for t in tasks.values():
        for g in json.load(open(t["gt"])):
            gts[f"p1-{g['name']}"] = sorted({(s["file"], s["line"]) for s in g["sites"]})
    agg = defaultdict(lambda: defaultdict(list)); per_run = []
    print(f"{'run':44} {'gt':>3} {'ans':>4} {'tp':>3} {'R':>5} {'P':>5} {'cost':>5} {'turns':>5} {'gnx':>4}  missed/extra(e.g.)")
    for rd in sys.argv[2].split(","):
        for l in open(os.path.join(rd, "results.jsonl")):
            r = json.loads(l)
            if r.get("task") not in tasks:
                continue
            gt = gts[r["task"]]
            ans = load(os.path.join(rd, "runs", r["run"], "qa-answer.json"))
            st = os.path.join(rd, "runs", r["run"], "stream.jsonl")
            if r.get("engine") == "claude" and os.path.exists(st):
                pc = parse_claude(st); r["turns"], r["gnx_cli"] = pc["turns"], pc["gnx_cli"]
            a = ans or []
            tp, missed, extra = match(a, gt)
            R = tp / len(gt) if gt else 1.0
            P = tp / len(a) if a else (1.0 if not gt else 0.0)
            gnx = (r.get("gnx_calls") or 0) + (r.get("gnx_cli") or 0)
            g = agg[r["arm"]]
            g["R"].append(R); g["P"].append(P); g["perfect"].append(int(R == 1 and P == 1)); g["cost"].append(r.get("cost_usd") or 0)
            g["turns"].append(r.get("turns") or 0); g["gnx"].append(gnx); g["missing"].append(int(ans is None)); g["wall"].append(r.get("wall_s") or 0)
            per_run.append(dict(run=r["run"], task=r["task"], arm=r["arm"], gt=len(gt), ans=(len(a) if ans is not None else None), tp=tp,
                                recall=R, precision=P, cost=r.get("cost_usd") or 0, turns=r.get("turns") or 0, wall=r.get("wall_s") or 0, gnx=gnx))
            eg = (f"miss {missed[0][0][-34:]}:{missed[0][1]}" if missed else "") + (f" extra {extra[0][0][-34:]}:{extra[0][1]}" if extra else "")
            print(f"{r['run']:44} {len(gt):3} {len(a) if ans is not None else '-':>4} {tp:3} {R:5.2f} {P:5.2f} {r.get('cost_usd') or 0:5.2f} {r.get('turns') or 0:5} {gnx:4}  {eg}")
    print("\nper arm: mean recall / precision, all-correct rate, missing answers, mean cost / turns / wall / GitNexus calls")
    m = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    for arm, g in sorted(agg.items()):
        print(f"{arm:6} n={len(g['R']):3} recall={m(g['R']):.3f} precision={m(g['P']):.3f} perfect={m(g['perfect']):.2f} "
              f"missing={sum(g['missing'])} cost=${m(g['cost']):.2f} turns={m(g['turns']):.1f} wall={m(g['wall']):.0f}s gnx={m(g['gnx']):.1f}")

    if "--json" in sys.argv:
        json.dump(dict(per_run=per_run, arms={(k if isinstance(k, str) else "|".join(k)): dict({x: (sum(v) / len(v) if v else None) for x, v in g.items()}, n=len(next(iter(g.values()))))
                                              for k, g in agg.items()}),
                  open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
