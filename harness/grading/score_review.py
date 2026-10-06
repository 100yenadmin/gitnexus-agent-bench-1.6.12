#!/usr/bin/env python3
"""Score review runs against upstream's hidden labels with upstream's own rules (port of
eval/workflow_bench/review_scoring.py: same path + line-overlap match, ranked max-cardinality pairing, severity
weights, blocker recall, verdict correctness, clean_pass). Lenient parsing: an unparseable output scores as an empty
review with verdict "missing" (counted, not dropped).
Usage: score_review.py <tasks-review.json> <runs_dir>[,<runs_dir>...]
"""
import json, os, posixpath, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common"))
import benchenv  # noqa: E402  (task 'labels' may use $GITNEXUS_SRC)

BLOCKING = {"critical", "high"}
WEIGHT = {"critical": 8.0, "high": 5.0, "medium": 2.0, "low": 1.0}


def norm_path(p):
    p = posixpath.normpath(str(p or "").strip().lstrip("./"))
    return p


def load_actual(path):
    try:
        d = json.load(open(path))
    except Exception:
        return "missing", []
    out = []
    for f in d.get("findings") or []:
        try:
            line = int(f.get("line")); end = int(f.get("end_line") or line)
        except Exception:
            continue
        sev = str(f.get("severity", "")).lower()
        out.append(dict(path=norm_path(f.get("path")), line=line, end_line=max(end, line),
                        severity=sev if sev in WEIGHT else "low", category=str(f.get("category", "")).lower(),
                        evidence=str(f.get("evidence", ""))))
    return str(d.get("verdict", "missing")).lower(), out


def score(verdict, actual, expected):
    cands = []
    for ai, a in enumerate(actual):
        for ei, e in enumerate(expected):
            if a["path"] != e["path"] or not (a["line"] <= e["line_end"] and a["end_line"] >= e["line_start"]):
                continue
            s = (int(a["category"] == e["category"]), int(a["severity"] == e["severity"]), -abs(a["line"] - e["line_start"]),
                 -(e["line_end"] - e["line_start"]), a["path"], a["category"], a["line"])
            cands.append((s, ai, ei))
    cands.sort(reverse=True)
    edges = defaultdict(list)
    for _s, ai, ei in cands:
        edges[ai].append(ei)
    owners = {}

    def augment(ai, seen):
        for ei in edges[ai]:
            if ei in seen:
                continue
            seen.add(ei)
            if ei not in owners or augment(owners[ei], seen):
                owners[ei] = ai
                return True
        return False

    for ai in sorted(edges):
        augment(ai, set())
    pairs = [(ai, ei) for ei, ai in owners.items()]
    tp = len(pairs); fp = len(actual) - tp; fn = len(expected) - tp
    exp_w = sum(WEIGHT[e["severity"]] for e in expected)
    m_w = sum(min(WEIGHT[actual[a]["severity"]], WEIGHT[expected[e]["severity"]]) for a, e in pairs)
    matched = {a for a, _ in pairs}
    fp_w = sum(WEIGHT[actual[i]["severity"]] for i in range(len(actual)) if i not in matched)
    wp = m_w / (m_w + fp_w) if m_w + fp_w else None
    wr = m_w / exp_w if exp_w else None
    wf1 = (2 * wp * wr / (wp + wr)) if wp is not None and wr is not None and wp + wr else (0.0 if expected else None)
    blockers = [i for i, e in enumerate(expected) if e["severity"] in BLOCKING]
    mb = {e for a, e in pairs if actual[a]["severity"] in BLOCKING}
    correct_verdict = (not expected and verdict == "approve") or (
        bool(expected) and verdict == ("request_changes" if any(e["severity"] in BLOCKING for e in expected) else "comment"))
    return dict(tp=tp, fp=fp, fn=fn, recall=(tp / (tp + fn) if tp + fn else None),
                precision=(tp / (tp + fp) if tp + fp else None), weighted_f1=wf1,
                blocker_recall=(sum(i in mb for i in blockers) / len(blockers) if blockers else None),
                verdict_correct=correct_verdict, clean_pass=(not expected and not actual and verdict == "approve"),
                n_findings=len(actual))


def main():
    tasks = {t["id"]: t for t in benchenv.load_tasks(sys.argv[1])}
    rows = {}
    for rd in sys.argv[2].split(","):
        for l in open(os.path.join(rd, "results.jsonl")):
            r = json.loads(l)
            if r.get("task") in tasks:
                r["_dir"] = rd
                rows[r["run"]] = r
    agg = defaultdict(lambda: defaultdict(list)); per_run = []
    print(f"{'run':34} {'tp':>3} {'fp':>3} {'fn':>3} {'wF1':>5} {'blkR':>5} verdict  cost")
    for name, r in sorted(rows.items()):
        t = tasks[r["task"]]
        labels = json.load(open(t["labels"]))["findings"]
        exp = [dict(path=norm_path(x["path"]), line_start=int(x["line_start"]), line_end=int(x["line_end"]),
                    severity=x["severity"].lower(), category=x["category"].lower()) for x in labels]
        verdict, act = load_actual(os.path.join(r["_dir"], "runs", name, "review-output.json"))
        s = score(verdict, act, exp)
        a = agg[r["arm"]]
        for k in ("tp", "fp", "fn", "n_findings"):
            a[k].append(s[k])
        a["cost"].append(r.get("cost_usd") or 0)
        a["verdict_correct"].append(int(s["verdict_correct"]))
        if exp:
            a["wf1"].append(s["weighted_f1"] or 0); a["recall"].append(s["recall"] or 0)
            if s["blocker_recall"] is not None:
                a["blocker_recall"].append(s["blocker_recall"])
        else:
            a["clean_pass"].append(int(s["clean_pass"])); a["clean_fp"].append(s["fp"])
        per_run.append(dict(run=name, task=r["task"], arm=r["arm"], defect=bool(exp), verdict=verdict, cost=r.get("cost_usd") or 0,
                            turns=r.get("turns") or 0, gnx=(r.get("gnx_calls") or 0) + (r.get("gnx_cli") or 0), **s))
        wf = f"{s['weighted_f1']:.2f}" if s["weighted_f1"] is not None else "  -  "
        br = f"{s['blocker_recall']:.2f}" if s["blocker_recall"] is not None else "  -  "
        print(f"{name:34} {s['tp']:3} {s['fp']:3} {s['fn']:3} {wf:>5} {br:>5} {verdict:8} {r.get('cost_usd') or 0:.2f}")
    print("\nper arm (defect cases: recall / weighted F1 / blocker recall; clean cases: pass rate / mean FPs)")
    m = lambda xs: (sum(xs) / len(xs)) if xs else float("nan")
    for arm, a in sorted(agg.items()):
        print(f"{arm:8} n={len(a['cost'])} recall={m(a['recall']):.2f} wF1={m(a['wf1']):.2f} blockerR={m(a['blocker_recall']):.2f} "
              f"TP={sum(a['tp'])} FP={sum(a['fp'])} FN={sum(a['fn'])} verdict_ok={m(a['verdict_correct']):.2f} "
              f"clean_pass={m(a['clean_pass']):.2f} clean_FPs={m(a['clean_fp']):.1f} cost=${m(a['cost']):.2f}")

    if "--json" in sys.argv:
        json.dump(dict(per_run=per_run, arms={(k if isinstance(k, str) else "|".join(k)): dict({x: (sum(v) / len(v) if v else None) for x, v in g.items()}, n=len(next(iter(g.values()))))
                                              for k, g in agg.items()}),
                  open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
