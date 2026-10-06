#!/usr/bin/env python3
"""Score the A/B runs. Usage: score.py <artifacts_dir>  -> prints per-task rows + per-arm summary, writes scores.json"""
import json, os, re, sys
from collections import defaultdict

A = sys.argv[1]
GT = json.load(open(os.path.join(A, "ground-truth.json")))
rows = []
for name in ("runs.jsonl", "runs-gnxf.jsonl", "runs-impact.jsonl"):
    p = os.path.join(A, "runs", name)
    if os.path.exists(p):
        rows += [json.loads(l) for l in open(p) if l.strip()]
# keep the LAST row per (id, arm) so a re-run replaces an errored one
last = {}
for r in rows:
    last[(r["id"], r["arm"])] = r
rows = list(last.values())


def norm_name(n):
    n = n.strip().strip("`").strip()
    n = re.sub(r"\(.*$", "", n)               # drop call parens / signature
    n = re.split(r"[.:#]+", n)[-1]             # Class.method / mod::fn -> last part
    return n.strip()


def score_para(r):
    ans = (r.get("answer") or "").strip()
    names = []
    for line in ans.splitlines():
        if "::" in line:
            names.append(norm_name(line.split("::", 1)[1]))
    tgt = r["target"]
    return {"top1": bool(names) and names[0] == tgt, "in3": tgt in names[:3], "n_cands": len(names)}


LINE = re.compile(r"([\w./@-]+\.[A-Za-z0-9]+):(\d+)")


def score_callers(r):
    gt = GT[r["id"]]
    ans = r.get("answer") or ""
    d_ok, calls = False, []
    for line in ans.splitlines():
        m = LINE.search(line)
        if not m:
            continue
        path, ln = m.group(1).lstrip("./"), int(m.group(2))
        if line.strip().upper().startswith("DEF"):
            d_ok = path.endswith(gt["def"][0]) and abs(ln - gt["def"][1]) <= 3
        elif line.strip().upper().startswith("CALL"):
            calls.append((path, ln))
    truth = [tuple(x) for x in gt["calls"]]
    hit_truth = sum(any(p.endswith(tp) and abs(l - tl) <= 3 for p, l in calls) for tp, tl in truth)
    good_pred = sum(any(p.endswith(tp) and abs(l - tl) <= 3 for tp, tl in truth) for p, l in calls)
    return {"def_ok": d_ok, "recall": f"{hit_truth}/{len(truth)}", "precision": f"{good_pred}/{len(calls)}",
            "exact": d_ok and hit_truth == len(truth) and good_pred == len(calls)}


def score_impact(r):
    items = GT[r["id"]]["items"]
    preds = []
    for line in (r.get("answer") or "").splitlines():
        parts = [x.strip().strip("`") for x in line.split("::")]
        if len(parts) >= 3:
            preds.append((parts[1].lstrip("./"), norm_name(parts[2])))
    hit = sum(any(pp.endswith(tp) and pn in names for pp, pn in preds) for tp, names in items)
    good = sum(any(pp.endswith(tp) and pn in names for tp, names in items) for pp, pn in preds)
    return {"recall": f"{hit}/{len(items)}", "precision": f"{good}/{len(preds)}",
            "exact": hit == len(items) and good == len(preds)}


out = []
for r in sorted(rows, key=lambda x: (x["id"], x["arm"])):
    s = (score_para(r) if r["kind"] == "para" else score_impact(r) if r["kind"] == "impact" else score_callers(r))
    gnx_calls = sum(v for k, v in (r.get("tools") or {}).items() if k.startswith("mcp__gitnexus"))
    out.append({**{k: r[k] for k in ("id", "kind", "alias", "target", "arm", "is_error", "num_turns", "wall_s", "cost_usd")},
                "tools": r.get("tools"), "gnx_calls": gnx_calls, **s})
json.dump(out, open(os.path.join(A, "scores.json"), "w"), indent=1)

for o in out:
    extra = (f"top1={o['top1']!s:5} in3={o['in3']!s:5}" if o["kind"] == "para"
             else f"recall={o['recall']} prec={o['precision']} exact={o['exact']}" if o["kind"] == "impact"
             else f"def={o['def_ok']!s:5} recall={o['recall']} prec={o['precision']} exact={o['exact']}")
    print(f"{o['id']} {o['arm']:4} {extra}  turns={o['num_turns']} wall={o['wall_s']}s cost=${(o['cost_usd'] or 0):.3f} gnx={o['gnx_calls']} err={o['is_error']}")

print("\n=== per arm ===")
agg = defaultdict(lambda: defaultdict(float))
for o in out:
    g = agg[(o["arm"], o["kind"])]
    g["n"] += 1; g["cost"] += o["cost_usd"] or 0; g["wall"] += o["wall_s"] or 0; g["turns"] += o["num_turns"] or 0
    g["used_gnx"] += 1 if o["gnx_calls"] else 0; g["err"] += 1 if o["is_error"] else 0
    if o["kind"] == "para":
        g["top1"] += o["top1"]; g["in3"] += o["in3"]
    else:
        g["def_ok"] += o.get("def_ok", 0); g["exact"] += o["exact"]
        h, t = map(int, o["recall"].split("/")); g["hit"] += h; g["truth"] += t
        gp, pc = map(int, o["precision"].split("/")); g["good"] += gp; g["pred"] += pc
for (arm, kind), g in sorted(agg.items(), key=lambda x: (x[0][1], x[0][0])):
    n = int(g["n"])
    base = f"{kind:7} {arm:4} n={n} used_gitnexus={int(g['used_gnx'])}/{n} errors={int(g['err'])} "
    base += f"mean_cost=${g['cost']/n:.3f} mean_wall={g['wall']/n:.1f}s mean_turns={g['turns']/n:.1f}"
    if kind == "para":
        base += f" top1={int(g['top1'])}/{n} in3={int(g['in3'])}/{n}"
    else:
        base += (f" def_ok={int(g['def_ok'])}/{n} call_recall={int(g['hit'])}/{int(g['truth'])} "
                 f"call_precision={int(g['good'])}/{int(g['pred'])} exact={int(g['exact'])}/{n}")
    print(base)
