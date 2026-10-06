#!/usr/bin/env python3
"""Codex A/B summary: cost/tokens/tool use per arm + impact tasks auto-scored against ground-truth.json."""
import json, os, re, sys
from collections import defaultdict

A = sys.argv[1]
GT = json.load(open(os.path.join(A, "ground-truth.json")))
rows = {}
for l in open(os.path.join(A, "runs-codex", "runs-codex.jsonl")):
    r = json.loads(l)
    if r["rc"] == 0 and r["usage"]["input_tokens"] > 0:
        rows[(r["id"], r["arm"])] = r  # last valid row wins


def norm(n):
    n = re.sub(r"\(.*$", "", n.strip().strip("`"))
    return re.split(r"[.:#]+", n)[-1].strip()


def impact_score(r):
    items = GT[r["id"][:3]]["items"]
    preds = []
    for line in (r.get("answer") or "").splitlines():
        parts = [x.strip().strip("`") for x in line.split("::")]
        if len(parts) >= 3:
            preds.append((parts[1].lstrip("./"), norm(parts[2])))
    hit = sum(any(pp.endswith(tp) and pn in names for pp, pn in preds) for tp, names in items)
    good = sum(any(pp.endswith(tp) and pn in names for tp, names in items) for pp, pn in preds)
    return hit, len(items), good, len(preds)


agg = defaultdict(lambda: defaultdict(float))
for (tid, arm), r in sorted(rows.items()):
    g = agg[(arm, r["kind"])]
    g["n"] += 1; g["cost"] += r["cost_usd"]; g["wall"] += r["wall_s"]
    g["in"] += r["usage"]["input_tokens"]; g["out"] += r["usage"]["output_tokens"]
    g["cmds"] += r["items"].get("command_execution", 0); g["mcp"] += r["items"].get("mcp_tool_call", 0)
    g["list_repos"] += r["mcp"].get("gitnexus.list_repos", 0)
    if r["kind"] == "impact":
        h, t, gd, p = impact_score(r); g["hit"] += h; g["truth"] += t; g["good"] += gd; g["pred"] += p
for (arm, kind), g in sorted(agg.items(), key=lambda x: (x[0][1], x[0][0])):
    n = g["n"] or 1
    line = (f"{kind:7} {arm} n={int(g['n'])} cost=${g['cost']/n:.3f} wall={g['wall']/n:.0f}s in_tok={g['in']/n/1000:.0f}k "
            f"out_tok={g['out']/n/1000:.1f}k shell_cmds={g['cmds']/n:.1f} gitnexus_calls={g['mcp']/n:.1f} "
            f"(list_repos {g['list_repos']/n:.1f})")
    if kind == "impact":
        line += f" recall={int(g['hit'])}/{int(g['truth'])} precision={int(g['good'])}/{int(g['pred'])}"
    print(line)
